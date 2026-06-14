import numpy as np
from typing import Union, Tuple
from pathlib import Path
from PIL import Image

MAX_PIXEL_VALUE = 255


class ImageLoader:
    """Carga y redimensiona imágenes en CPU."""

    @staticmethod
    def prepare_from_bytes(
        image_bytes: bytes, target_size: Tuple[int, int] = (28, 28)
    ) -> np.ndarray:
        """Carga una imagen desde bytes y la redimensiona con LANCZOS.

        Args:
            image_bytes: Bytes de la imagen (PNG, JPG, etc.).
            target_size: Tupla (alto, ancho) destino (default 28×28).

        Returns:
            np.ndarray uint8 con la imagen redimensionada.
        """
        image = ImageLoader._load_image_from_bytes(image_bytes)
        return ImageLoader._resize_image(image, target_size)

    @staticmethod
    def prepare_from_file(
        image_path: Union[str, Path], target_size: Tuple[int, int] = (28, 28)
    ) -> np.ndarray:
        """Carga una imagen desde archivo y la redimensiona con LANCZOS.

        Args:
            image_path: Ruta al archivo de imagen.
            target_size: Tupla (alto, ancho) destino (default 28×28).

        Returns:
            np.ndarray uint8 con la imagen redimensionada.
        """
        image = ImageLoader._load_image(image_path)
        return ImageLoader._resize_image(image, target_size)

    @staticmethod
    def _load_image(image_path: Union[str, Path]) -> np.ndarray:
        """Lee una imagen del disco con PIL y la devuelve como np.ndarray.

        Args:
            image_path: Ruta al archivo de imagen.

        Returns:
            np.ndarray con la imagen en formato HWC (RGB) o HW (escala de grises).
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Imagen no encontrada: {image_path}")
            image = Image.open(image_path)
            return np.array(image)
        except Exception as e:
            raise Exception(f"Error al cargar imagen {image_path}: {str(e)}")

    @staticmethod
    def _load_image_from_bytes(image_bytes: bytes) -> np.ndarray:
        """Lee una imagen desde bytes con PIL y la devuelve como np.ndarray.

        Args:
            image_bytes: Bytes de la imagen.

        Returns:
            np.ndarray con la imagen en formato HWC (RGB) o HW (escala de grises).
        """
        try:
            from io import BytesIO
            image_stream = BytesIO(image_bytes)
            image = Image.open(image_stream)
            return np.array(image)
        except Exception as e:
            raise Exception(f"Error al cargar imagen desde bytes: {str(e)}")

    @staticmethod
    def _resize_image(image: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
        """Redimensiona una imagen con interpolación LANCZOS, manteniendo dtype uint8.

        Si la imagen está en float32 (ej. 0-1), la escala a uint8 (0-255) primero.

        Args:
            image: np.ndarray de entrada (H, W) o (H, W, C).
            target_size: Tupla (alto, ancho) destino.

        Returns:
            np.ndarray uint8 redimensionado.
        """
        pil_image = Image.fromarray(
            (image * MAX_PIXEL_VALUE).astype(np.uint8) if image.dtype == np.float32 else image
        )
        pil_image = pil_image.resize(
            (target_size[1], target_size[0]), Image.Resampling.LANCZOS
        )
        return np.array(pil_image)
