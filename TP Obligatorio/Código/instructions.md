spec_content = """# Especificación de Desarrollo Guiado por Especificaciones (SDD)
## Sistema de Simulación de Delivery Concurrente Multi-Actor

Este documento define las especificaciones técnicas rigurosas y la arquitectura de diseño para el desarrollo de un sistema de simulación de delivery concurrente (estilo Uber Eats / PedidosYa) en Python. Está diseñado para guiar de manera inequívoca a un modelo de IA en la generación de código limpio, seguro, eficiente y exento de condiciones de carrera o bloqueos mutuos.

---

## 1. REQUISITOS DEL ENTORNO Y RESTRICCIONES

### 1.1 Entorno de Ejecución
- **Lenguaje Principal:** Python 3.10 o superior (utilizando características modernas como type hinting avanzado y correspondencia de patrones si fuera necesario).
- **Plataforma:** Aplicación de consola multiplataforma (compatible con Linux, macOS y Windows).
- **Interfaz:** Exclusivamente a través de la salida estándar (`stdout`) administrada mediante el módulo `logging`. Queda prohibido el uso de interfaces gráficas (GUI) o web.

### 1.2 Restricciones de Dependencias
- **Librerías Permitidas:** Únicamente se permite el uso de la biblioteca estándar de Python. Específicamente: `threading`, `multiprocessing`, `queue`, `asyncio`, `time`, `random`, `logging`, y `collections`.
- **Prohibiciones Absolutas:** No se permite la instalación ni el uso de frameworks o librerías de terceros (p. ej., `Pydantic`, `FastAPI`, `Trio`, `Loguru`, etc.).

### 1.3 Restricciones de Concurrencia y Sincronización
- **Mecanismo Principal:** Hilos reales del sistema operativo utilizando el módulo `threading`.
- **Concurrencia Cooperativa:** Queda terminantemente prohibido el uso de `Thread.stop()`, `Thread.terminate()` o matar hilos de forma abrupta. El apagado del sistema debe ser puramente cooperativo mediante señales y eventos.
- **Evitación de Espera Activa:** Está prohibido el uso de `time.sleep(0)` como mecanismo de ceder CPU o bucles de espera activa (`while not ready: pass`). Los hilos deben bloquearse legítimamente en colas seguras o primitivas de sincronización.
- **Acceso a Estado Compartido:** No se permite ninguna variable global mutábase sin la protección explícita de un cerrojo (`threading.Lock`).

### 1.4 Registro de consumo de CPU y RAM
- **Implementacion:** Utilizar psutil para ir imprimiendo periodicamente en consola el consumo de cpu y de ram (%) que va teniendo el programa completo.

---

## 2. ARQUITECTURA DEL SISTEMA Y MODELO DE ACTORES

El sistema se basa en un pipeline de procesamiento concurrente multi-nivel basado en el patrón Productor-Consumidor. El flujo de datos sigue el ciclo completo de un pedido: **Generación → Preparación → Entrega → Confirmación**.

[Clientes] --(produce)--> [Cola Pedidos Pendientes] --(consume/produce)--> [Cocineros]
|
[Métricas] <--(registra)-- [Repartidores] <--(consume)-- [Cola Pedidos Listos] <+

### 2.1 Topología de Hilos Mínima
Para garantizar la concurrencia masiva y validar el diseño, el sistema debe inicializar y ejecutar simultáneamente un mínimo de **11 hilos activos**:
- $\ge 3$ Hilos de Clientes (`Cliente`)
- $\ge 4$ Hilos de Cocineros (`Cocinero`)
- $\ge 3$ Hilos de Repartidores (`Repartidor`)
- $1$ Hilo de Monitoreo (`MonitorSistema`)

---

## 3. MÁQUINA DE ESTADOS DEL PEDIDO

Cada pedido es un objeto dinámico que transiciona de forma estrictamente lineal a través de cinco estados. Cada transición debe ser **atómica**, protegida por un cerrojo exclusivo adjunto a la propia instancia del pedido.

| Estado Origen | Transición / Acción | Estado Destino | Actor Responsable |
| :--- | :--- | :--- | :--- |
| `Ninguno` | Creación e inserción en cola de pendientes | `PENDIENTE` | `Cliente` |
| `PENDIENTE` | Extracción de la cola e inicio de cocción | `EN_PREPARACION` | `Cocinero` |
| `EN_PREPARACION` | Finalización de cocción y envío a cola listos | `LISTO` | `Cocinero` |
| `LISTO` | Extracción de cola listos e inicio de ruta | `EN_ENTREGA` | `Repartidor` |
| `EN_ENTREGA` | Entrega efectiva al cliente y cálculo de tiempos | `ENTREGADO` | `Repartidor` |

---

## 4. ESPECIFICACIÓN DETALLADA DE CLASES (CONTRATO DE INTERFAZ)

El código generado debe estructurarse estrictamente en las siguientes clases, respetando firmas y contratos de comportamiento.

### 4.1 Clase `Pedido`
Representa la entidad de datos y la máquina de estados de un pedido individual.
- **Atributos:**
  - `id_pedido` (str/int): Identificador único global.
  - `nombre_plato` (str): Nombre descriptivo del producto.
  - `tiempo_preparacion_estimado` (float): Tiempo simulado requerido para cocinar.
  - `timestamp_creacion` (float): Tiempo epoch de creación (`time.time()`).
  - `timestamp_inicio_preparacion` (float): Tiempo de inicio de cocción.
  - `timestamp_listo` (float): Tiempo de fin de cocción.
  - `timestamp_entrega` (float): Tiempo de entrega efectiva.
  - `estado` (str): Estado actual (`PENDIENTE`, `EN_PREPARACION`, etc.).
  - `lock` (`threading.Lock`): Cerrojo exclusivo para la atomicidad de esta instancia.
- **Métodos:**
  - `cambiar_estado(nuevo_estado: str, actor_name: str) -> None`: Adquiere el lock interno, valida la transición lineal, actualiza el atributo `estado`, registra los timestamps correspondientes y emite un log detallado.

### 4.2 Clase `Cliente` (Producers)
Hilo encargado de simular la demanda de pedidos en el ecosistema.
- **Comportamiento:**
  - Corre en un bucle infinito que verifica continuamente el `shutdown_event`.
  - Genera un pedido aleatorio con un intervalo configurable (p. ej., cada $1$ a $3$ segundos).
  - Intenta insertar el pedido en `cola_pedidos_pendientes`. Si la cola está llena, el hilo debe bloquearse automáticamente (`maxsize` de la cola).
  - Si el sistema inicia el apagado y la cola está llena o el hilo se desbloquea, debe finalizar su ejecución limpiamente.

### 4.3 Clase `Cocinero` (Workers - Nivel 1)
Consumidor de pedidos pendientes y productor de pedidos listos.
- **Comportamiento:**
  - Consume de `cola_pedidos_pendientes`. El bloqueo de extracción debe tener un *timeout* corto para permitir verificar el `shutdown_event`.
  - Antes de iniciar la preparación, debe adquirir un `threading.Semaphore` global que limita la capacidad simultánea de la cocina (máximo igual al número de cocineros activos).
  - Transiciona el estado a `EN_PREPARACION`.
  - Simula la cocción usando `time.sleep(tiempo_preparacion_estimado)`.
  - Transiciona el estado a `LISTO`, libera el semáforo e inserta el pedido en `cola_pedidos_listos` (bloqueándose si esta última está llena).

### 4.4 Clase `Repartidor` (Deliverers - Nivel 2)
Consumidor final del flujo de trabajo.
- **Comportamiento:**
  - Consume de `cola_pedidos_listos` con un mecanismo de bloqueo por *timeout*.
  - Transiciona el estado a `EN_ENTREGA`.
  - Simula el traslado mediante un `time.sleep()` con un valor flotante aleatorio dentro de un rango configurable (p. ej., entre $2.0$ y $5.0$ segundos).
  - Transiciona el estado a `ENTREGADO`.
  - Adquiere el lock de estadísticas globales para registrar de forma segura los tiempos de ciclo y contar el pedido como completado.

### 4.5 Clase `MonitorSistema`
Hilo de diagnóstico periódico de salud del sistema.
- **Comportamiento:**
  - Cada $N$ segundos (configurable, por defecto $2$ segundos), inspecciona de forma segura el tamaño de las colas, calcula el conteo de hilos activos utilizando `threading.active_count()` e imprime un reporte estructurado por `logging`.

### 4.6 Clase `SistemaDelivery`
El orquestador principal (Engine) de la simulación.
- **Responsabilidades:**
  - Almacenar configuraciones del sistema (número de actores, capacidades máximas de colas, tiempos de simulación).
  - Inicializar las dos instancias de `queue.Queue` (`cola_pedidos_pendientes` y `cola_pedidos_listos`) configuradas con sus respectivos `maxsize`.
  - Alojar las variables de métricas globales y su correspondiente `threading.Lock`.
  - Instanciar e iniciar todos los hilos (`daemon=False`).
  - Gestionar el temporizador principal de la simulación. Tras expirar el tiempo (p. ej., 60 segundos), activa el `shutdown_event` e inicia el protocolo de parada ordenada.

---

## 5. ESTRATEGIA DE SINCRONIZACIÓN Y PREVENCIÓN DE ERRORES

Para garantizar la estabilidad absoluta bajo condiciones de alta concurrencia, el modelo debe implementar las siguientes directrices de diseño:

### 5.1 Prevención de Deadlocks (Bloqueos Mutuos)
Para evitar inversiones de prioridades o interbloqueos, se establece una **jerarquía estricta de adquisición de recursos**:
1. Un hilo NUNCA debe intentar adquirir más de un Lock de Pedido simultáneamente.
2. Si un hilo requiere acceder a las estadísticas globales y a un Pedido al mismo tiempo, **SIEMPRE debe adquirir primero el Lock del Pedido y posteriormente el Lock de Estadísticas Globales**.
3. El `threading.Semaphore` de la cocina siempre debe adquirirse **antes** de retirar formalmente o procesar el cambio de estado del pedido a `EN_PREPARACION`.

### 5.2 Protocolo de Apagado Cooperativo Limpio
Cuando `SistemaDelivery` activa el `shutdown_event`:
1. Los hilos **Clientes** detectan el evento inmediatamente en su siguiente iteración y rompen su bucle, finalizando su ejecución. Esto detiene la inyección de nuevos pedidos.
2. Los hilos **Cocineros** continúan extrayendo elementos de la `cola_pedidos_pendientes`. Solo cuando la cola está completamente vacía (`queue.Empty` capturado) Y el `shutdown_event` está activo, proceden a salir de su bucle.
3. Los hilos **Repartidores** siguen la misma lógica con la `cola_pedidos_listos`: no se apagan hasta que la cola esté vacía y el evento de apagado esté encendido.
4. El hilo **Monitor** finaliza tras comprobar que todos los hilos trabajadores han terminado.
5. El hilo principal ejecuta `.join()` sobre todos los actores asegurando el vaciado total.

---

## 6. REGISTRO (LOGGING) Y FORMATO DE SALIDA

Todo evento dentro de los hilos de ejecución debe ser registrado utilizando el módulo `logging`. La configuración base debe asegurar el siguiente formato:

```text
%(asctime)s [%(threadName)s] [Pedido ID: %(pedido_id)s] [%(estado_pedido)s] -> %(message)s