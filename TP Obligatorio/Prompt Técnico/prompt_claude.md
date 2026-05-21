• LENGUAJE DE PROGRAMACIÓN:

- Utilizar Python 3.10+ como lenguaje principal.
- Se permite el uso de la biblioteca estándar únicamente: threading, multiprocessing, queue, asyncio, time, random, logging, collections.
- No se deben usar frameworks externos ni librerías de terceros.

• PLATAFORMA:

- Aplicación de consola ejecutable en cualquier sistema operativo con Python 3.10+.
- Sin interfaz gráfica; toda la salida debe realizarse por stdout mediante el módulo logging.

• FUNCIONALIDAD A IMPLEMENTAR:

- Desarrollar una simulación de un sistema de delivery estilo Uber Eats / PedidosYa con múltiples actores concurrentes.
- El sistema debe modelar el ciclo completo de un pedido: generación → preparación → entrega → confirmación.
- Debe soportar múltiples instancias simultáneas de cada actor (clientes, cocineros, repartidores).

• ACTORES DEL SISTEMA:

- Clientes (Producers): generan pedidos de forma aleatoria con un intervalo configurable. Cada pedido tiene: ID único, nombre del plato, tiempo estimado de preparación y timestamp de creación.
- Cocineros (Workers): toman pedidos de la cola de pedidos pendientes, los "preparan" (simulado con time.sleep() proporcional al tiempo estimado) y los colocan en la cola de pedidos listos.
- Repartidores (Deliverers): toman pedidos de la cola de pedidos listos y los "entregan" (simulado con time.sleep() aleatorio dentro de un rango configurable). Al completar, registran el tiempo total del pedido.
- Monitor del sistema: hilo dedicado que cada N segundos imprime el estado del sistema: pedidos en cola, pedidos en preparación, pedidos en entrega, pedidos completados, threads activos.

• REQUISITOS ESPECÍFICOS:

- La cantidad de clientes, cocineros y repartidores debe ser configurable mediante constantes al inicio del programa.
- Implementar dos colas thread-safe usando queue.Queue:
  · cola_pedidos_pendientes: entre clientes y cocineros (productor-consumidor nivel 1).
  · cola_pedidos_listos: entre cocineros y repartidores (productor-consumidor nivel 2).
- Cada cola debe tener una capacidad máxima configurable. Si la cola está llena, el productor debe bloquearse (comportamiento natural de queue.Queue con maxsize).
- Implementar un threading.Event de apagado (shutdown_event) que al activarse indique a todos los hilos que deben terminar limpiamente al vaciar sus colas.
- Cada actor debe correr en su propio threading.Thread con daemon=False.
- Usar threading.Lock para proteger el acceso al contador de estadísticas globales (pedidos completados, tiempo total acumulado).
- Usar threading.Semaphore para limitar la cantidad de pedidos que pueden estar en preparación simultáneamente (máximo igual a la cantidad de cocineros activos).
- Cada pedido debe tener un estado representado con una máquina de estados con al menos 4 estados: PENDIENTE → EN_PREPARACION → LISTO → EN_ENTREGA → ENTREGADO.
- Las transiciones de estado deben realizarse de forma atómica usando un Lock por pedido.
- El sistema debe correr durante un tiempo total configurable (por ejemplo, 60 segundos de simulación) y luego iniciar el apagado ordenado.
- Al finalizar, imprimir un resumen de métricas:
  · Total de pedidos generados, completados y descartados.
  · Tiempo promedio de preparación.
  · Tiempo promedio de entrega.
  · Tiempo promedio total (desde creación hasta entrega).
  · Throughput: pedidos completados por minuto.
- Todo el logging debe incluir: timestamp, nombre del thread, ID del pedido y estado actual.
- El código debe estar dividido en clases: Pedido, Cliente, Cocinero, Repartidor, MonitorSistema, SistemaDelivery.

• RESTRICCIONES:

- No usar asyncio como mecanismo principal de concurrencia; el modelo debe basarse en threads reales (threading). asyncio puede usarse opcionalmente para comparación en una sección aparte claramente delimitada.
- No usar variables globales sin protección de Lock. Toda variable compartida entre threads debe estar protegida.
- No usar time.sleep(0) como yield; los threads deben bloquearse en las colas o en sincronizadores, no en busy-waiting.
- No usar Thread.stop() ni Thread.terminate(); el apagado debe ser cooperativo mediante shutdown_event.
- El código no debe tener race conditions detectables: proteger todos los accesos a estado compartido.
- No debe haber posibilidad de deadlock: el orden de adquisición de locks debe ser consistente y documentado en comentarios.
- La cantidad mínima de threads simultáneos en la simulación debe ser: 3 clientes + 4 cocineros + 3 repartidores + 1 monitor = 11 threads mínimo.
- El código debe incluir docstrings en todas las clases y métodos públicos.
- No se permite el uso de la keyword global. Toda variable compartida debe ser atributo de la clase SistemaDelivery y pasada por referencia a los actores.
