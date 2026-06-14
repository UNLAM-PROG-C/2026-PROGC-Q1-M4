# Worker de Inferencia CNN vía CUDA + RabbitMQ

Worker distribuido para clasificación de imágenes mediante una CNN ejecutada con kernels CUDA nativos sobre GPU, integrado con RabbitMQ como bus de mensajería.

## Arquitectura

El worker consume mensajes desde una cola de RabbitMQ (`image_queue`), procesa cada imagen usando un motor de inferencia CUDA y publica el resultado en la cola indicada por la propiedad AMQP `reply_to` del mensaje entrante, utilizando el patrón _reply-to_ con `correlation_id` para correlacionar la respuesta con la solicitud.

```
RabbitMQ → [image_queue] → main.py → predictor.py → cuda_inference.py → GPU
                                     ↓
                     [reply_to queue] → RabbitMQ (vía reply_to + correlation_id)
```

## Estructura de archivos

| Archivo                      | Propósito |
|------------------------------|-----------|
| `main.py`                    | Punto de entrada. Conecta a RabbitMQ con reintentos (`CONNECTION_ATTEMPTS`/`RETRY_DELAY`), declara `image_queue` como durable, aplica `basic_qos(prefetch_count=1)` para fair dispatch, y consume mensajes. En el callback obtiene las predicciones de `Predictor`, las formatea con `LABELS` y publica la respuesta en la cola `reply_to` usando `correlation_id`. |
| `predictor.py`               | Orquesta la predicción: carga `model_params.pkl`, prepara la imagen via `ImageLoader` y delega la inferencia al motor CUDA. Expone: `predict_image(bytes)`, `predict_from_file(path)`, `get_model_info()`, `cleanup()`. |
| `cuda_inference.py`          | Motor de inferencia GPU nativo. Carga 8 kernels desde `kernels.fatbin`: preprocess, conv2d, relu, maxpool2d, matmul_bias, batch_norm, softmax. Incluye `preprocess_kernel` que convierte a grises, normaliza e invierte colores en GPU. Asigna pesos/sesgos en memoria GPU estática y ejecuta la red completa (4 Conv2D + 4 BatchNorm + 2 Dense + Softmax). |
| `image_loader.py`            | Carga y redimensionamiento a 28×28 (LANCZOS) en CPU. La conversión a grises, normalización e inversión de colores se realiza en GPU mediante kernel CUDA dentro de `cuda_inference.py`. |
| `model_params.pkl`           | Pesos y sesgos del CNN serializados con pickle. Contiene 11 bloques: 4 conv2d, 4 batch_normalization, 2 dense, 1 dense_1. |
| `kernels.fatbin`             | Código compilado CUDA _fatbin_ multi-arquitectura con los 8 kernels de inferencia (preprocess + CNN). |
| `Dockerfile.worker`          | Build multi-etapa con imagen `nvidia/cuda:12.1.1` (stage builder instala dependencias, stage runtime solo ejecuta). Crea usuario no-root `worker`. |
| `requirements.txt`           | Dependencias Python: numpy, Pillow, pycuda, pika. |

## Flujo de ejecución

1. **Conexión** a RabbitMQ con credenciales (`RABBITMQ_USER`/`RABBITMQ_PASS`), hasta `CONNECTION_ATTEMPTS` reintentos con `RETRY_DELAY` segundos entre cada uno. Declara la cola `image_queue` como durable y establece `basic_qos(prefetch_count=1)` para fair dispatch.
2. **Callback**: al recibir un mensaje (bytes de imagen), se invoca `analyze_image()` que inicializa el `Predictor` lazy en la primera llamada.
3. **Preprocesamiento**: `ImageLoader` convierte los bytes a numpy array y redimensiona a 28×28 (LANCZOS). Luego `CUDAInferenceEngine.forward()` ejecuta un kernel CUDA que convierte a grises, normaliza a [0,1] e invierte colores directamente en GPU.
4. **Inferencia CUDA**: `CUDAInferenceEngine.forward()` ejecuta la red completa en GPU:
   - **Bloque 1**: Conv2D (3×3, 1→32) → ReLU → BatchNorm (32) → Conv2D (3×3, 32→32) → ReLU → BatchNorm (32) → MaxPool2D (2×2)
   - **Bloque 2**: Conv2D (3×3, 32→64) → ReLU → BatchNorm (64) → Conv2D (3×3, 64→64) → ReLU → BatchNorm (64) → MaxPool2D (2×2)
   - **Clasificador**: Flatten → Dense (3136→512) → ReLU → BatchNorm (512) → Dense (512→10) → Softmax
   - Salida: vector de 10 probabilidades (Fashion MNIST).
5. **Formateo**: `main.py` recibe las probabilidades como `np.ndarray` y las formatea con `LABELS` generando una lista JSON de `{name, probability}`.
6. **Publicación**: el resultado se envía a la cola indicada en la propiedad `reply_to` del mensaje original, con el mismo `correlation_id` y `DELIVERY_MODE=2` (persistente). Luego se confirma el mensaje con `basic_ack`.

## Variables de entorno

| Variable            | Default     | Descripción |
|---------------------|-------------|-------------|
| `RABBITMQ_HOST`     | `localhost` | Host de RabbitMQ |
| `RABBITMQ_PORT`     | `5672`      | Puerto de RabbitMQ |
| `RABBITMQ_USER`     | `admin`     | Usuario de RabbitMQ |
| `RABBITMQ_PASS`     | `admin`     | Contraseña de RabbitMQ |
| `CONNECTION_ATTEMPTS` | `5`       | Número máximo de reintentos de conexión a RabbitMQ |
| `RETRY_DELAY`       | `3`         | Segundos de espera entre reintentos de conexión |

## Despliegue con Docker

```bash
docker build -t worker-cuda -f Dockerfile.worker .
docker run --rm --gpus all \
  -e RABBITMQ_HOST=rabbitmq \
  worker-cuda
```

Requiere tener NVIDIA Container Toolkit instalado y RabbitMQ accesible desde la red del contenedor.

## Dependencias

```
numpy>=1.23.0
Pillow>=9.0.0
pycuda>=2024.1
pika>=1.3.2
```

## Formato de mensaje de entrada

El `body` del mensaje de RabbitMQ debe contener los **bytes crudos de la imagen** (PNG, JPG, etc.). El worker no espera metadatos adicionales en el mensaje; la información de enrutamiento se obtiene de las propiedades AMQP (`reply_to`, `correlation_id`).

## Formato de respuesta

```json
[
  {"name": "Remera",     "probability": 0.15},
  {"name": "Pantalon",   "probability": 0.02},
  {"name": "Sueter",     "probability": 0.05},
  {"name": "Vestido",    "probability": 0.01},
  {"name": "Abrigo",     "probability": 0.00},
  {"name": "Sandalia",   "probability": 0.00},
  {"name": "Camisa",     "probability": 0.02},
  {"name": "Zapatilla",  "probability": 0.00},
  {"name": "Bolso",      "probability": 0.02},
  {"name": "Bota",       "probability": 0.73}
]
```

La respuesta es siempre una lista JSON con 10 objetos, uno por categoría. En caso de error interno, todas las probabilidades se devuelven en 0.0.

## Preprocesamiento de imágenes

1. **Carga desde bytes** vía `PIL.Image.open()` + `BytesIO`, o desde archivo con `ImageLoader.prepare_from_bytes()` / `ImageLoader.prepare_from_file()`.
2. **Redimensionamiento** a 28×28 píxeles (algoritmo LANCZOS) en CPU.
3. **Conversión a escala de grises, normalización e inversión de colores**: ejecutadas en GPU mediante el kernel CUDA `preprocess_kernel` dentro de `CUDAInferenceEngine.forward()`. Esto evita transferencias CPU→GPU adicionales y aprovecha el paralelismo de la GPU.

## Manejo de errores

- **Fallo de conexión a RabbitMQ**: el worker reintenta hasta `CONNECTION_ATTEMPTS` veces con `RETRY_DELAY` segundos entre cada intento. Si agota los reintentos, termina con código de salida 1.
- **Error durante inferencia**: se registra el traceback y se retorna una lista con todas las probabilidades en 0.0. El worker continúa escuchando nuevos mensajes.
- **Mensajes sin `reply_to`**: se rechazan (`basic_nack`) sin reencolar y se registra el error. El consumo continúa normalmente.
- **Excepción dentro del callback**: se captura con `try/except`, se hace `basic_nack` sin reencolar, y el worker **sigue consumiendo** mensajes. No detiene el consumo.
- **Limpieza de recursos GPU**: el método `Predictor.cleanup()` libera la memoria GPU asignada (`pycuda.driver.mem_alloc`).

## Información del modelo

- **Arquitectura**: CNN convolucional con 4 capas Conv2D (kernel 3×3, padding=1, stride=1), 4 capas BatchNormalization, 2 capas Dense y Softmax.
  - `conv2d`: 3×3×1 → 32 canales (salida 28×28×32)
  - `conv2d_1`: 3×3×32 → 32 canales (salida 28×28×32)
  - `maxpool2d`: 2×2 → 14×14×32
  - `conv2d_2`: 3×3×32 → 64 canales (salida 14×14×64)
  - `conv2d_3`: 3×3×64 → 64 canales (salida 14×14×64)
  - `maxpool2d`: 2×2 → 7×7×64 → Flatten → 3136
  - `dense`: 3136 → 512
  - `dense_1`: 512 → 10
  - Softmax: 10 probabilidades
- **Motor de inferencia**: CUDA nativo con 8 kernels cargados desde `kernels.fatbin` (preprocess, conv2d, relu, maxpool2d, matmul_bias, batch_norm, softmax).
- **Parámetros**: 11 bloques de pesos y sesgos serializados en `model_params.pkl` (4 conv2d, 4 batch_normalization, 2 dense, 1 dense_1).
- **Entrada física**: imagen redimensionada a 28×28 (LANCZOS) en CPU. El preprocesado (conversión a grises, normalización a [0,1] e inversión de colores) se realiza en GPU mediante `preprocess_kernel`. La CNN recibe internamente (28, 28, 1) float32, fondo negro/objeto blanco (estilo Fashion MNIST).
- **Salida**: vector de 10 probabilidades (Fashion MNIST).
