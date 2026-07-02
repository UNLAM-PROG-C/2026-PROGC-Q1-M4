import pickle
import numpy as np
import logging
from cuda_inference import CUDAInferenceEngine
from image_loader import ImageLoader

logger = logging.getLogger(__name__)

TARGET_SIZE = (28, 28)
INPUT_SHAPE = (28, 28, 1)
NUM_CLASSES = 10
MODEL_PARAMS_PATH = 'model_params.pkl'
INFERENCE_ENGINE_NAME = 'CUDA'


class Predictor:
  """
  Realiza predicciones con el motor de inferencia CUDA.
  """

  def __init__(self):
    """Carga los parámetros del modelo desde model_params.pkl e inicializa CUDAInferenceEngine."""
    try:
      logger.info("Cargando parámetros del modelo desde el disco...")
      with open(MODEL_PARAMS_PATH, 'rb') as f:
        model_params = pickle.load(f)

      logger.info("Inicializando predictor con motor CUDA...")
      self.cuda_engine = CUDAInferenceEngine(model_params)
      logger.info("✓ Predictor inicializado correctamente")

    except Exception as e:
      logger.error(f"Error inicializando predictor: {str(e)}")
      raise

  def predict_image(self, image_bytes: bytes) -> np.ndarray:
    """
    Predice la clase de una imagen usando motor CUDA.

    Args:
        image_bytes: Imagen como bytes.

    Returns:
        Array numpy con 10 probabilidades (raw output de la red).
    """
    image = ImageLoader.prepare_from_bytes(image_bytes, target_size=TARGET_SIZE)
    return self.cuda_engine.forward(image)

  def predict_from_file(self, image_path: str) -> np.ndarray:
    """
    Predice la clase de una imagen desde archivo usando motor CUDA.

    Args:
        image_path: Ruta al archivo de imagen.

    Returns:
        Array numpy con 10 probabilidades (raw output de la red).
    """
    image = ImageLoader.prepare_from_file(image_path, target_size=TARGET_SIZE)
    return self.cuda_engine.forward(image)

  def get_model_info(self) -> dict:
    """
    Obtiene información del modelo.

    Returns:
        Diccionario con información del modelo.
    """
    return {
      "input_shape": INPUT_SHAPE,
      "num_classes": NUM_CLASSES,
      "inference_engine": INFERENCE_ENGINE_NAME,
    }

  def cleanup(self):
    """Libera recursos CUDA. Es vital llamar a esto al cerrar tu aplicación."""
    if hasattr(self, 'cuda_engine'):
      self.cuda_engine.cleanup()
      logger.info("✓ Recursos CUDA liberados")
