import numpy as np
import pycuda.driver as cuda
import pycuda.autoinit
import logging
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

FLOAT32_BYTES = 4
BLOCK_SIZE_2D = 16
BLOCK_SIZE_1D = 256

BATCH_SIZE = 1
DEFAULT_PADDING = 1
DEFAULT_STRIDE = 1
POOL_FACTOR = 2
DEFAULT_EPSILON = 1e-3

KERNEL_WEIGHT_AXIS = 0
KERNEL_OUT_CHANNELS_AXIS = 3
DENSE_INPUT_AXIS = 0
DENSE_OUTPUT_AXIS = 1
SINGLE_ROW_GRID = 1

FATBIN_PATH = "kernels.fatbin"

KERNEL_FUNCTIONS = {
  'preprocess': "preprocess_kernel",
  'normalize': "normalize_kernel",
  'relu': "relu_kernel",
  'conv2d': "conv2d_kernel",
  'maxpool2d': "maxpool2d_kernel",
  'matmul_bias': "matmul_kernel",
  'batch_norm': "batch_norm_kernel",
  'softmax': "softmax_kernel",
}

WEIGHTS_KEY = 'weights'
BIAS_KEY = 'bias'


def ceil_div(numerator, divisor):
  """División entera redondeada hacia arriba: útil para calcular tamaños de grid CUDA."""
  return (numerator + divisor - 1) // divisor


# ==================== MOTOR DE INFERENCIA CUDA ====================
class CUDAInferenceEngine:
  def __init__(self, model_params):
    """Inicializa el motor CUDA: carga kernels desde fatbin y asigna memoria GPU estática."""
    self.params = model_params
    self.gpu_memory = {}
    self.kernels = {}
    self._compile_kernels()
    self._allocate_gpu_memory()

  def _compile_kernels(self):
    """Carga los 8 kernels desde kernels.fatbin y los guarda en self.kernels."""
    logger.info("Cargando Fatbin multi-arquitectura...")
    try:
      cuda_module = cuda.module_from_file(FATBIN_PATH)
      self.kernels = {
        name: cuda_module.get_function(fn)
        for name, fn in KERNEL_FUNCTIONS.items()
      }
    except Exception as e:
      logger.error(f"Error cargando Fatbin: {str(e)}")
      raise

    logger.info("✓ Kernels CUDA cargados exitosamente")

  def _allocate_gpu_memory(self):
    """Transfiere pesos y sesgos del modelo (dict de numpy arrays) a memoria GPU estática."""
    logger.info("Asignando memoria GPU estática para pesos y sesgos...")
    for key, value in self.params.items():
      if isinstance(value, dict):
        self._allocate_layer(key, value)

  def _allocate_layer(self, key, value):
    """Copia a GPU cada numpy array de una capa del modelo."""
    for sub_key, arr in value.items():
      if isinstance(arr, np.ndarray):
        gpu_mem = cuda.mem_alloc(arr.nbytes)
        cuda.memcpy_htod(gpu_mem, np.ascontiguousarray(arr))
        self.gpu_memory[f"{key}_{sub_key}"] = gpu_mem
        logger.info(f"  ✓ Asignado {key}_{sub_key}: {arr.shape}")

  def _conv_output_dim(self, size, padding, kernel_size, stride):
    """Calcula el tamaño de salida de una dimensión convolucional."""
    return (size + POOL_FACTOR * padding - kernel_size) // stride + 1

  def _launch_conv2d(self, gpu_input, gpu_output, conv_layer, dims):
    """Invoca el kernel conv2d con las dimensiones ya calculadas."""
    height, width, in_channels, out_channels, kernel_size, stride, padding, grid = dims
    self.kernels['conv2d'](
      gpu_input,
      self.gpu_memory[f'{conv_layer}_weights'],
      self.gpu_memory[f'{conv_layer}_bias'],
      gpu_output,
      np.int32(BATCH_SIZE), np.int32(height), np.int32(width), np.int32(in_channels),
      np.int32(out_channels), np.int32(kernel_size), np.int32(stride), np.int32(padding),
      block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1),
      grid=grid
    )

  def conv2d_forward(self, gpu_input, input_shape, conv_layer, padding=DEFAULT_PADDING):
    """Ejecuta convolución 2D con padding en GPU.

    Args:
        gpu_input: Buffer GPU con entrada (H, W, C) float32.
        input_shape: Tupla (height, width, channels).
        conv_layer: Clave del diccionario de parámetros (ej. 'conv2d').
        padding: Padding a aplicar (default 1).

    Returns:
        Tupla (gpu_output, output_shape) con el resultado y su forma.
    """
    height, width, in_channels = input_shape
    weights = self.params[conv_layer][WEIGHTS_KEY]
    kernel_size = weights.shape[KERNEL_WEIGHT_AXIS]
    out_channels = weights.shape[KERNEL_OUT_CHANNELS_AXIS]
    stride = DEFAULT_STRIDE

    out_height = self._conv_output_dim(height, padding, kernel_size, stride)
    out_width = self._conv_output_dim(width, padding, kernel_size, stride)

    gpu_output = cuda.mem_alloc(int(out_height * out_width * out_channels * FLOAT32_BYTES))
    grid = (ceil_div(out_width, BLOCK_SIZE_2D), ceil_div(out_height, BLOCK_SIZE_2D), out_channels)

    dims = (height, width, in_channels, out_channels, kernel_size, stride, padding, grid)
    self._launch_conv2d(gpu_input, gpu_output, conv_layer, dims)
    return gpu_output, (out_height, out_width, out_channels)

  def relu_forward(self, gpu_input, num_elements):
    """Aplica ReLU elemento a elemento en GPU.

    Args:
        gpu_input: Buffer GPU de entrada float32.
        num_elements: Cantidad total de elementos.

    Returns:
        Buffer GPU con ReLU aplicado.
    """
    gpu_output = cuda.mem_alloc(int(num_elements * FLOAT32_BYTES))
    grid_size = ceil_div(num_elements, BLOCK_SIZE_1D)

    self.kernels['relu'](
      gpu_input, gpu_output, np.int32(num_elements),
      block=(BLOCK_SIZE_1D, 1, 1), grid=(grid_size, 1)
    )
    return gpu_output

  def maxpool2d_forward(self, gpu_input, input_shape):
    """Aplica max pooling 2×2 (stride 2) en GPU.

    Args:
        gpu_input: Buffer GPU de entrada float32.
        input_shape: Tupla (height, width, channels).

    Returns:
        Tupla (gpu_output, output_shape) con el resultado reducido a la mitad.
    """
    height, width, channels = input_shape
    out_height = height // POOL_FACTOR
    out_width = width // POOL_FACTOR

    output_size = out_height * out_width * channels
    gpu_output = cuda.mem_alloc(int(output_size * FLOAT32_BYTES))

    grid = (ceil_div(out_width, BLOCK_SIZE_2D), ceil_div(out_height, BLOCK_SIZE_2D), channels)

    self.kernels['maxpool2d'](
      gpu_input, gpu_output,
      np.int32(height), np.int32(width), np.int32(channels),
      block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1),
      grid=grid
    )
    return gpu_output, (out_height, out_width, channels)

  def dense_forward(self, gpu_input, dense_layer):
    """Ejecuta capa fully-connected (matmul + bias) en GPU.

    Args:
        gpu_input: Buffer GPU con vector de entrada aplanado.
        dense_layer: Clave del diccionario de parámetros (ej. 'dense').

    Returns:
        Tupla (gpu_output, output_features) con el resultado.
    """
    weights = self.params[dense_layer][WEIGHTS_KEY]
    input_features = weights.shape[DENSE_INPUT_AXIS]
    output_features = weights.shape[DENSE_OUTPUT_AXIS]

    gpu_output = cuda.mem_alloc(int(output_features * FLOAT32_BYTES))
    grid = (ceil_div(output_features, BLOCK_SIZE_2D), SINGLE_ROW_GRID)
    self._launch_dense(gpu_input, gpu_output, dense_layer, input_features, output_features, grid)
    return gpu_output, output_features

  def _launch_dense(self, gpu_input, gpu_output, dense_layer, input_features, output_features, grid):
    """Invoca el kernel matmul_bias de una capa densa."""
    self.kernels['matmul_bias'](
      gpu_input,
      self.gpu_memory[f'{dense_layer}_weights'],
      self.gpu_memory[f'{dense_layer}_bias'],
      gpu_output,
      np.int32(BATCH_SIZE), np.int32(input_features), np.int32(output_features),
      block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1),
      grid=grid
    )

  def softmax_forward(self, gpu_input, num_classes):
    """Aplica softmax con memoria compartida en GPU.

    Args:
        gpu_input: Buffer GPU con logits float32.
        num_classes: Cantidad de clases de salida.

    Returns:
        Tupla (gpu_output, num_classes) con probabilidades normalizadas.
    """
    gpu_output = cuda.mem_alloc(int(num_classes * FLOAT32_BYTES))
    shared_mem_size = int(BLOCK_SIZE_1D * FLOAT32_BYTES)

    self.kernels['softmax'](
      gpu_input, gpu_output,
      np.int32(BATCH_SIZE), np.int32(num_classes),
      block=(BLOCK_SIZE_1D, 1, 1), grid=(1, 1),
      shared=shared_mem_size
    )
    return gpu_output, num_classes

  def _launch_batch_norm(self, gpu_input, gpu_output, bn_layer, num_elements, channels, epsilon, grid_size):
    """Invoca el kernel batch_norm con sus cinco buffers de parámetros."""
    self.kernels['batch_norm'](
      gpu_input,
      self.gpu_memory[f'{bn_layer}_gamma'],
      self.gpu_memory[f'{bn_layer}_beta'],
      self.gpu_memory[f'{bn_layer}_moving_mean'],
      self.gpu_memory[f'{bn_layer}_moving_var'],
      gpu_output,
      np.int32(num_elements),
      np.int32(channels),
      np.float32(epsilon),
      block=(BLOCK_SIZE_1D, 1, 1),
      grid=(grid_size, 1)
    )

  def batch_norm_forward(self, gpu_input, bn_layer, num_elements, channels, epsilon=DEFAULT_EPSILON):
    """
    Aplica BatchNormalization: out = gamma * (x - mean) / sqrt(var + eps) + beta
    """
    gpu_output = cuda.mem_alloc(int(num_elements * FLOAT32_BYTES))
    grid_size = ceil_div(num_elements, BLOCK_SIZE_1D)
    self._launch_batch_norm(gpu_input, gpu_output, bn_layer, num_elements, channels, epsilon, grid_size)
    return gpu_output

  def preprocess_forward(self, gpu_input, width, height, channels):
    """Convierte imagen uint8 (H,W,C) a float32 normalizado [0,1] e invertido (1-x) en GPU.

    Args:
        gpu_input: Buffer GPU con imagen uint8 cruda (H, W, C).
        width, height, channels: Dimensiones de la imagen.

    Returns:
        Tupla (gpu_output, (H, W, 1)) con float32 listo para la red.
    """
    gpu_output = cuda.mem_alloc(width * height * FLOAT32_BYTES)
    grid = (ceil_div(width, BLOCK_SIZE_2D), ceil_div(height, BLOCK_SIZE_2D))
    self.kernels['preprocess'](
      gpu_input, gpu_output,
      np.int32(width), np.int32(height), np.int32(channels),
      block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1), grid=grid
    )
    return gpu_output, (height, width, 1)

  def _upload_image(self, image):
    """Copia la imagen cruda a GPU y devuelve el buffer junto con (width, height, channels)."""
    height, width = image.shape[:2]
    channels = 1 if len(image.shape) == 2 else image.shape[2]

    gpu_tensor = cuda.mem_alloc(image.nbytes)
    cuda.memcpy_htod(gpu_tensor, np.ascontiguousarray(image))
    return gpu_tensor, width, height, channels

  def _forward_and_free_shape(self, gpu_in, layer_func, *args):
    """Ejecuta una capa que devuelve forma, liberando el buffer de entrada."""
    gpu_out, new_shape = layer_func(gpu_in, *args)
    gpu_in.free()
    return gpu_out, new_shape

  def _forward_and_free(self, gpu_in, layer_func, *args):
    """Ejecuta una capa que no devuelve forma, liberando el buffer de entrada."""
    gpu_out = layer_func(gpu_in, *args)
    gpu_in.free()
    return gpu_out

  def _conv_block(self, gpu_tensor, shape, conv_layer, bn_layer):
    """Aplica conv2d → ReLU → batch norm y devuelve (gpu_tensor, shape)."""
    gpu_tensor, shape = self._forward_and_free_shape(gpu_tensor, self.conv2d_forward, shape, conv_layer)
    gpu_tensor = self._forward_and_free(gpu_tensor, self.relu_forward, int(np.prod(shape)))
    gpu_tensor = self._forward_and_free(
      gpu_tensor, self.batch_norm_forward, bn_layer, int(np.prod(shape)), shape[2])
    return gpu_tensor, shape

  def _feature_extractor(self, gpu_tensor, shape):
    """Ejecuta los dos bloques convolucionales con sus max pooling."""
    gpu_tensor, shape = self._conv_block(gpu_tensor, shape, 'conv2d', 'batch_normalization')
    gpu_tensor, shape = self._conv_block(gpu_tensor, shape, 'conv2d_1', 'batch_normalization_1')
    gpu_tensor, shape = self._forward_and_free_shape(gpu_tensor, self.maxpool2d_forward, shape)

    gpu_tensor, shape = self._conv_block(gpu_tensor, shape, 'conv2d_2', 'batch_normalization_2')
    gpu_tensor, shape = self._conv_block(gpu_tensor, shape, 'conv2d_3', 'batch_normalization_3')
    gpu_tensor, shape = self._forward_and_free_shape(gpu_tensor, self.maxpool2d_forward, shape)
    return gpu_tensor, shape

  def _classifier(self, gpu_tensor):
    """Ejecuta las capas densas + softmax y devuelve (gpu_tensor, num_classes)."""
    gpu_tensor, num_features = self._forward_and_free_shape(gpu_tensor, self.dense_forward, 'dense')
    gpu_tensor = self._forward_and_free(gpu_tensor, self.relu_forward, num_features)
    gpu_tensor = self._forward_and_free(
      gpu_tensor, self.batch_norm_forward, 'batch_normalization_4', num_features, num_features)

    gpu_tensor, num_classes = self._forward_and_free_shape(gpu_tensor, self.dense_forward, 'dense_1')
    gpu_tensor, num_classes = self._forward_and_free_shape(gpu_tensor, self.softmax_forward, num_classes)
    return gpu_tensor, num_classes

  def _read_predictions(self, gpu_tensor, num_classes):
    """Descarga las probabilidades finales de GPU a CPU y libera el buffer."""
    predictions = np.empty((num_classes,), dtype=np.float32)
    cuda.memcpy_dtoh(predictions, gpu_tensor)
    gpu_tensor.free()
    return predictions

  def forward(self, image):
    """
    Inferencia de una imagen.
    Args:
        image: array de numpy (H, W, C) uint8 crudo de ImageLoader.
    Returns:
        Vector con 10 probabilidades
    """
    gpu_tensor, width, height, channels = self._upload_image(image)

    preprocessed, shape = self.preprocess_forward(gpu_tensor, width, height, channels)
    gpu_tensor.free()
    gpu_tensor = preprocessed

    gpu_tensor, shape = self._feature_extractor(gpu_tensor, shape)
    gpu_tensor, num_classes = self._classifier(gpu_tensor)
    return self._read_predictions(gpu_tensor, num_classes)

  def cleanup(self):
    """Libera toda la memoria GPU asignada para los parámetros del modelo."""
    for mem in self.gpu_memory.values():
      mem.free()
    logger.info("✓ Memoria GPU liberada")
