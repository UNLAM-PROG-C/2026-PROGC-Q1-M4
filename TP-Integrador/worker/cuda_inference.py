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
            cuda_module = cuda.module_from_file("kernels.fatbin")
            self.kernels = {
                'preprocess': cuda_module.get_function("preprocess_kernel"),
                'normalize': cuda_module.get_function("normalize_kernel"),
                'relu': cuda_module.get_function("relu_kernel"),
                'conv2d': cuda_module.get_function("conv2d_kernel"),
                'maxpool2d': cuda_module.get_function("maxpool2d_kernel"),
                'matmul_bias': cuda_module.get_function("matmul_kernel"),
                'batch_norm': cuda_module.get_function("batch_norm_kernel"),
                'softmax': cuda_module.get_function("softmax_kernel"),
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
                for sub_key, arr in value.items():
                    if isinstance(arr, np.ndarray):
                        gpu_mem = cuda.mem_alloc(arr.nbytes)
                        cuda.memcpy_htod(gpu_mem, np.ascontiguousarray(arr))
                        self.gpu_memory[f"{key}_{sub_key}"] = gpu_mem
                        logger.info(f"  ✓ Asignado {key}_{sub_key}: {arr.shape}")

    def conv2d_forward(self, gpu_input, input_shape, conv_layer, padding=1):
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
        conv_params = self.params[conv_layer]
        kernel_size = conv_params['weights'].shape[0]
        out_channels = conv_params['weights'].shape[3]
        stride = 1

        out_height = (height + 2 * padding - kernel_size) // stride + 1
        out_width = (width + 2 * padding - kernel_size) // stride + 1

        output_size = out_height * out_width * out_channels
        gpu_output = cuda.mem_alloc(int(output_size * FLOAT32_BYTES))

        grid_x = (out_width + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D
        grid_y = (out_height + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D
        grid_z = out_channels

        self.kernels['conv2d'](
            gpu_input,
            self.gpu_memory[f'{conv_layer}_weights'],
            self.gpu_memory[f'{conv_layer}_bias'],
            gpu_output,
            np.int32(1), np.int32(height), np.int32(width), np.int32(in_channels),
            np.int32(out_channels), np.int32(kernel_size), np.int32(stride), np.int32(padding),
            block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1),
            grid=(grid_x, grid_y, grid_z)
        )
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
        grid_size = (num_elements + BLOCK_SIZE_1D - 1) // BLOCK_SIZE_1D

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
        out_height = height // 2
        out_width = width // 2

        output_size = out_height * out_width * channels
        gpu_output = cuda.mem_alloc(int(output_size * FLOAT32_BYTES))

        grid_x = (out_width + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D
        grid_y = (out_height + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D
        grid_z = channels

        self.kernels['maxpool2d'](
            gpu_input, gpu_output,
            np.int32(height), np.int32(width), np.int32(channels),
            block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1),
            grid=(grid_x, grid_y, grid_z)
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
        dense_params = self.params[dense_layer]
        weights = dense_params['weights']

        input_features = weights.shape[0]
        output_features = weights.shape[1]

        output_size = output_features
        gpu_output = cuda.mem_alloc(int(output_size * FLOAT32_BYTES))

        grid_x = (output_features + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D
        grid_y = 1

        self.kernels['matmul_bias'](
            gpu_input,
            self.gpu_memory[f'{dense_layer}_weights'],
            self.gpu_memory[f'{dense_layer}_bias'],
            gpu_output,
            np.int32(1), np.int32(input_features), np.int32(output_features),
            block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1),
            grid=(grid_x, grid_y)
        )
        return gpu_output, output_features

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
            np.int32(1), np.int32(num_classes),
            block=(BLOCK_SIZE_1D, 1, 1), grid=(1, 1),
            shared=shared_mem_size
        )
        return gpu_output, num_classes

    def batch_norm_forward(self, gpu_input, bn_layer, num_elements, channels, epsilon=1e-3):
        """
        Aplica BatchNormalization: out = gamma * (x - mean) / sqrt(var + eps) + beta
        """
        gpu_output = cuda.mem_alloc(int(num_elements * FLOAT32_BYTES))
        grid_size = (num_elements + BLOCK_SIZE_1D - 1) // BLOCK_SIZE_1D

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
        grid = ((width + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D,
                (height + BLOCK_SIZE_2D - 1) // BLOCK_SIZE_2D)
        self.kernels['preprocess'](
            gpu_input, gpu_output,
            np.int32(width), np.int32(height), np.int32(channels),
            block=(BLOCK_SIZE_2D, BLOCK_SIZE_2D, 1), grid=grid
        )
        return gpu_output, (height, width, 1)

    def forward(self, image):
        """
        Inferencia de una imagen.
        Args:
            image: array de numpy (H, W, C) uint8 crudo de ImageLoader.
        Returns:
            Vector con 10 probabilidades
        """
        height, width = image.shape[:2]
        channels = 1 if len(image.shape) == 2 else image.shape[2]

        gpu_tensor = cuda.mem_alloc(image.nbytes)
        cuda.memcpy_htod(gpu_tensor, np.ascontiguousarray(image))

        preprocessed, shape = self.preprocess_forward(gpu_tensor, width, height, channels)
        gpu_tensor.free()
        gpu_tensor = preprocessed

        def _forward_and_free_shape(gpu_in, layer_func, *args):
            gpu_out, new_shape = layer_func(gpu_in, *args)
            gpu_in.free()
            return gpu_out, new_shape

        def _forward_and_free(gpu_in, layer_func, *args):
            gpu_out = layer_func(gpu_in, *args)
            gpu_in.free()
            return gpu_out

        # ===== BLOQUE 1 =====
        gpu_tensor, shape = _forward_and_free_shape(gpu_tensor, self.conv2d_forward, shape, 'conv2d')
        gpu_tensor = _forward_and_free(gpu_tensor, self.relu_forward, int(np.prod(shape)))
        gpu_tensor = _forward_and_free(gpu_tensor, self.batch_norm_forward, 'batch_normalization', int(np.prod(shape)), shape[2])

        gpu_tensor, shape = _forward_and_free_shape(gpu_tensor, self.conv2d_forward, shape, 'conv2d_1')
        gpu_tensor = _forward_and_free(gpu_tensor, self.relu_forward, int(np.prod(shape)))
        gpu_tensor = _forward_and_free(gpu_tensor, self.batch_norm_forward, 'batch_normalization_1', int(np.prod(shape)), shape[2])

        gpu_tensor, shape = _forward_and_free_shape(gpu_tensor, self.maxpool2d_forward, shape)

        # ===== BLOQUE 2 =====
        gpu_tensor, shape = _forward_and_free_shape(gpu_tensor, self.conv2d_forward, shape, 'conv2d_2')
        gpu_tensor = _forward_and_free(gpu_tensor, self.relu_forward, int(np.prod(shape)))
        gpu_tensor = _forward_and_free(gpu_tensor, self.batch_norm_forward, 'batch_normalization_2', int(np.prod(shape)), shape[2])

        gpu_tensor, shape = _forward_and_free_shape(gpu_tensor, self.conv2d_forward, shape, 'conv2d_3')
        gpu_tensor = _forward_and_free(gpu_tensor, self.relu_forward, int(np.prod(shape)))
        gpu_tensor = _forward_and_free(gpu_tensor, self.batch_norm_forward, 'batch_normalization_3', int(np.prod(shape)), shape[2])

        gpu_tensor, shape = _forward_and_free_shape(gpu_tensor, self.maxpool2d_forward, shape)

        # ===== CAPAS DENSAS =====
        gpu_tensor, num_features = _forward_and_free_shape(gpu_tensor, self.dense_forward, 'dense')
        gpu_tensor = _forward_and_free(gpu_tensor, self.relu_forward, num_features)
        gpu_tensor = _forward_and_free(gpu_tensor, self.batch_norm_forward, 'batch_normalization_4', num_features, num_features)

        gpu_tensor, num_classes = _forward_and_free_shape(gpu_tensor, self.dense_forward, 'dense_1')
        gpu_tensor, num_classes = _forward_and_free_shape(gpu_tensor, self.softmax_forward, num_classes)

        # ===== CARGA DE RESULTADOS DESDE GPU =====
        predictions = np.empty((num_classes,), dtype=np.float32)
        cuda.memcpy_dtoh(predictions, gpu_tensor)
        gpu_tensor.free()

        return predictions

    def cleanup(self):
        """Libera toda la memoria GPU asignada para los parámetros del modelo."""
        for mem in self.gpu_memory.values():
            mem.free()
        logger.info("✓ Memoria GPU liberada")
