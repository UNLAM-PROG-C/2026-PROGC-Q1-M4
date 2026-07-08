# TP Integrador - IdentifAI

IdentifAI es una plataforma web distribuida para el reconocimiento de objetos en imágenes. El usuario carga una imagen desde el frontend y el sistema infiere la clase del objeto utilizando una IA entrenada por el equipo, devolviendo las probabilidades asociadas a cada categoría.

## Funcionalidad

El proyecto permite subir, arrastrar o pegar una imagen desde una interfaz web y enviarla al backend para su análisis. La imagen es procesada por un worker Python que ejecuta inferencia con un modelo de inteligencia artificial entrenado sobre Fashion MNIST, devolviendo una lista de resultados con sus probabilidades.

## Arquitectura

La solución está organizada como una arquitectura de microservicios contenedorizada:

* **Frontend**: aplicación web en HTML, CSS y JavaScript que permite cargar imágenes y visualizar los resultados.
* **Backend**: servicio Java que expone endpoints HTTP, recibe la imagen y la publica en RabbitMQ.
* **RabbitMQ**: broker de mensajería utilizado para desacoplar el backend del procesamiento de imágenes.
* **Worker Python**: consumidor de la cola que procesa la imagen, ejecuta la inferencia con CUDA/PyCUDA y responde el resultado.
* **Kubernetes + KEDA**: orquestación y balanceo de carga de workers. KEDA escala los workers según la cantidad de mensajes pendientes en la cola `image_queue`, levantando Jobs bajo demanda.

Flujo principal:

1. El frontend envía la imagen al backend.
2. El backend publica los bytes de la imagen en RabbitMQ.
3. KEDA detecta mensajes pendientes en la cola y crea workers en Kubernetes.
4. El worker procesa la imagen con el modelo de IA.
5. El resultado vuelve al backend mediante `reply_to` y `correlation_id`.
6. El backend responde al frontend con las probabilidades calculadas.

Acceder al backend por `127.0.0.1:3001`

# Uso de Just

Las aplicaciones se corren mediante `justfile`.

## Instalación

El proyecto contiene un Justfile para el despliegue y administración del proyecto.

```bash
   winget install Casey.Just
```

Instala y configura las dependencias necesarias para trabajar con KEDA y el entorno k8s.

* `just install-keda`

---

# Requisitos para Windows + Docker Desktop

Si se va a desplegar este proyecto en Windows con Docker Desktop, es necesario configurar Docker Desktop para poder correr la imagen del worker en el ambiente de k8s.
Para ello, se debe hacer lo siguiente:

Habilitar:
`Use containerd for pulling and storing images`

Ruta:
`Configuración -> General -> Use containerd for pulling and storing images`

---

# Uso

* `just`

  Ejecuta el help y muestra todos los comandos disponibles.

---

* `just up`

  Levanta todos los contenedores y servicios necesarios del proyecto.
  Los workers los levantará KEDA en el entorno k8s. Balanceo de carga y despliegue a demanda.

---

* `just dev`

  Levanta el proyecto en modo desarrollo.
  Existe un solo worker en un contenedor. No se utiliza k8s ni KEDA. Recordar parar el contenedor (`just down`) si se desea pasar a despliegue (`just up`).

---

* `just down`

  Borra el espacio de trabajo y elimina contenedores, redes y recursos temporales.
  Ideal para levantar el proyecto desde cero o limpiar conflictos.

---

* `just logs`

  Permite debuggear en vivo los contenedores principales.

---

* `just logs-worker`

  Permite visualizar los logs de los workers.
  Los workers no se pueden debuggear en vivo nativamente, por lo que este comando sirve para monitoreo y diagnóstico.

---

* `just ...`

  Existen más comandos auxiliares disponibles en el help.
