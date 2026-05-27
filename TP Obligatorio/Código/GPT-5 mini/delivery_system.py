"""
delivery_system.py

Simulación concurrente de un sistema de delivery multi-actor.

Este módulo implementa las clases y la orquestación descritas en
`instructions.md` usando únicamente la biblioteca estándar de Python
y respetando las restricciones de sincronización y apagado cooperativo.
"""

import logging
import threading
import queue
import time
import random
import collections
import os

# Optional psutil integration (graceful fallback if not installed)
try:
    import psutil
    _HAS_PSUTIL = True
except Exception:
    psutil = None
    _HAS_PSUTIL = False


# Logger configuration (always provide the required extra keys when logging)
logger = logging.getLogger("delivery_system")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(threadName)s] [Pedido ID: %(pedido_id)s] [%(estado_pedido)s] -> %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class Pedido:
    """Entidad que representa un pedido y su máquina de estados.

    La clase asegura atomicidad en las transiciones mediante un `threading.Lock`
    adjunto a la instancia.
    """

    def __init__(self, id_pedido, nombre_plato, tiempo_preparacion_estimado):
        self.id_pedido = id_pedido
        self.nombre_plato = nombre_plato
        self.tiempo_preparacion_estimado = float(tiempo_preparacion_estimado)

        self.timestamp_creacion = None
        self.timestamp_inicio_preparacion = None
        self.timestamp_listo = None
        self.timestamp_entrega = None

        self.estado = "Ninguno"
        self.lock = threading.Lock()

    def cambiar_estado(self, nuevo_estado, actor_name: str) -> None:
        """Realiza una transición de estado atómica y registra timestamps.

        Si la transición no es lineal/permitida, se registra un mensaje y no
        se realiza el cambio.
        """
        valid_transitions = {
            "Ninguno": ["PENDIENTE"],
            "PENDIENTE": ["EN_PREPARACION"],
            "EN_PREPARACION": ["LISTO"],
            "LISTO": ["EN_ENTREGA"],
            "EN_ENTREGA": ["ENTREGADO"],
            "ENTREGADO": [],
        }

        with self.lock:
            origen = self.estado
            permitidos = valid_transitions.get(origen, [])
            if nuevo_estado not in permitidos:
                logger.info(f"Invalid transition {origen} -> {nuevo_estado} by {actor_name}", extra={"pedido_id": self.id_pedido, "estado_pedido": self.estado})
                return

            self.estado = nuevo_estado
            ahora = time.time()
            if nuevo_estado == "PENDIENTE":
                self.timestamp_creacion = ahora
            elif nuevo_estado == "EN_PREPARACION":
                self.timestamp_inicio_preparacion = ahora
            elif nuevo_estado == "LISTO":
                self.timestamp_listo = ahora
            elif nuevo_estado == "ENTREGADO":
                self.timestamp_entrega = ahora

            logger.info(f"{actor_name} -> {origen} -> {nuevo_estado}", extra={"pedido_id": self.id_pedido, "estado_pedido": self.estado})


class Cliente(threading.Thread):
    """Hilo productor que genera pedidos aleatorios y los inserta en la cola.

    Detecta el `shutdown_event` mediante `Event.wait()` para no usar esperas
    activas y responde limpiamente al apagado.
    """

    def __init__(self, cliente_id, cola_pendientes: queue.Queue, pedido_factory, shutdown_event: threading.Event, min_interval=1.0, max_interval=3.0):
        super().__init__(name=f"Cliente-{cliente_id}")
        self.cliente_id = cliente_id
        self.cola_pendientes = cola_pendientes
        self.pedido_factory = pedido_factory
        self.shutdown_event = shutdown_event
        self.min_interval = float(min_interval)
        self.max_interval = float(max_interval)
        self.daemon = False

    def run(self):
        while not self.shutdown_event.is_set():
            intervalo = random.uniform(self.min_interval, self.max_interval)
            # Espera que puede interrumpirse por apagado cooperativo
            if self.shutdown_event.wait(timeout=intervalo):
                break

            pedido = self.pedido_factory()
            # Registrar creación como transición atómica
            pedido.cambiar_estado("PENDIENTE", self.name)

            try:
                # Intentar encolarlo con timeout para poder reaccionar al shutdown
                self.cola_pendientes.put(pedido, timeout=1)
                logger.info("Pedido encolado en pendientes", extra={"pedido_id": pedido.id_pedido, "estado_pedido": pedido.estado})
            except queue.Full:
                logger.info("Cola de pendientes llena, cliente no pudo encolar", extra={"pedido_id": pedido.id_pedido, "estado_pedido": pedido.estado})
                if self.shutdown_event.is_set():
                    break


class Cocinero(threading.Thread):
    """Consume pedidos pendientes, simula la preparación y produce pedidos listos.

    Respeta la jerarquía: adquiere el `kitchen_semaphore` antes de retirar y cambiar
    el estado a `EN_PREPARACION`.
    """

    def __init__(self, cocinero_id, cola_pendientes: queue.Queue, cola_listos: queue.Queue, kitchen_semaphore: threading.Semaphore, shutdown_event: threading.Event):
        super().__init__(name=f"Cocinero-{cocinero_id}")
        self.cola_pendientes = cola_pendientes
        self.cola_listos = cola_listos
        self.kitchen_semaphore = kitchen_semaphore
        self.shutdown_event = shutdown_event
        self.daemon = False

    def run(self):
        while True:
            # Condición de salida cooperativa: apagar + cola vacía
            if self.shutdown_event.is_set() and self.cola_pendientes.empty():
                break

            # Adquirir semáforo antes de retirar/formalizar preparación (con timeout para chequear shutdown)
            acquired = self.kitchen_semaphore.acquire(timeout=1)
            if not acquired:
                continue

            pedido = None
            try:
                try:
                    pedido = self.cola_pendientes.get(timeout=1)
                except queue.Empty:
                    # No había pedido: soltar semáforo y continuar
                    continue

                # Transición a EN_PREPARACION (método maneja su propio lock)
                pedido.cambiar_estado("EN_PREPARACION", self.name)

                # Simular cocción (permitir interrupción por shutdown_event)
                self.shutdown_event.wait(timeout=pedido.tiempo_preparacion_estimado)

                pedido.cambiar_estado("LISTO", self.name)

                # Insertar en cola de listos (bloqueante hasta que haya espacio)
                # No liberamos coherencia: liberamos semáforo antes de bloquear en la cola para permitir que otros cocineros trabajen
                try:
                    self.cola_listos.put(pedido)
                    logger.info("Pedido puesto en cola LISTO por cocinero", extra={"pedido_id": pedido.id_pedido, "estado_pedido": pedido.estado})
                except Exception:
                    logger.info("Error al encolar en lista de listos", extra={"pedido_id": pedido.id_pedido, "estado_pedido": pedido.estado})
            finally:
                # Liberar semáforo siempre que se haya adquirido
                try:
                    self.kitchen_semaphore.release()
                except Exception:
                    pass


class Repartidor(threading.Thread):
    """Consume pedidos listos, simula entrega y actualiza métricas globales.

    Al actualizar métricas que involucran al `Pedido`, respeta la jerarquía:
    adquirir `Pedido.lock` antes del `metrics_lock`.
    """

    def __init__(self, repartidor_id, cola_listos: queue.Queue, metrics: dict, metrics_lock: threading.Lock, shutdown_event: threading.Event, min_delivery=2.0, max_delivery=5.0):
        super().__init__(name=f"Repartidor-{repartidor_id}")
        self.cola_listos = cola_listos
        self.metrics = metrics
        self.metrics_lock = metrics_lock
        self.shutdown_event = shutdown_event
        self.min_delivery = float(min_delivery)
        self.max_delivery = float(max_delivery)
        self.daemon = False

    def run(self):
        while True:
            if self.shutdown_event.is_set() and self.cola_listos.empty():
                break

            try:
                pedido = self.cola_listos.get(timeout=1)
            except queue.Empty:
                continue

            # Inicia entrega
            pedido.cambiar_estado("EN_ENTREGA", self.name)

            # Simular traslado (permitir interrupción cooperativa)
            delivery_time = random.uniform(self.min_delivery, self.max_delivery)
            self.shutdown_event.wait(timeout=delivery_time)

            # Finaliza entrega
            pedido.cambiar_estado("ENTREGADO", self.name)

            # Actualizar métricas asegurando la jerarquía de locks: primero pedido.lock, luego metrics_lock
            with pedido.lock:
                with self.metrics_lock:
                    if pedido.timestamp_creacion is not None and pedido.timestamp_entrega is not None:
                        ciclo = pedido.timestamp_entrega - pedido.timestamp_creacion
                        self.metrics["completed"] += 1
                        self.metrics.setdefault("total_cycle_time", 0.0)
                        self.metrics["total_cycle_time"] += ciclo
                        logger.info(f"Pedido entregado. Ciclo={ciclo:.3f}s", extra={"pedido_id": pedido.id_pedido, "estado_pedido": pedido.estado})


class MonitorSistema(threading.Thread):
    """Hilo que realiza chequeos periódicos del estado del sistema e informa via logging.

    Finaliza cuando el `shutdown_event` está activo y todos los hilos trabajadores han terminado.
    """

    def __init__(self, cola_pendientes: queue.Queue, cola_listos: queue.Queue, threads_list: list, shutdown_event: threading.Event, interval=2.0):
        super().__init__(name="MonitorSistema")
        self.cola_pendientes = cola_pendientes
        self.cola_listos = cola_listos
        self.threads_list = threads_list
        self.shutdown_event = shutdown_event
        self.interval = float(interval)
        self.daemon = False

    def run(self):
        while True:
            pending = self.cola_pendientes.qsize()
            ready = self.cola_listos.qsize()
            active = threading.active_count()
            # Gather system stats if psutil is available
            if _HAS_PSUTIL:
                try:
                    cpu = psutil.cpu_percent(interval=None)
                    mem = psutil.virtual_memory().percent
                except Exception:
                    cpu = None
                    mem = None
            else:
                cpu = None
                mem = None

            logger.info(
                f"Monitor: pending={pending}, ready={ready}, active_threads={active}, cpu={cpu if cpu is not None else 'n/a'}%, mem={mem if mem is not None else 'n/a'}%",
                extra={"pedido_id": "-", "estado_pedido": "-"},
            )

            if self.shutdown_event.wait(timeout=self.interval):
                # Si estamos en shutdown, solo finalizamos cuando todos los workers hayan terminado
                others_alive = any((t.is_alive() and t.name != self.name) for t in self.threads_list)
                if not others_alive:
                    break


class SistemaDelivery:
    """Orquestador principal que inicializa colas, actores, métricas y controla la simulación."""

    def __init__(self, num_clientes=3, num_cocineros=4, num_repartidores=3, pending_maxsize=50, ready_maxsize=50, kitchen_capacity=None, monitor_interval=2.0, simulation_time=60):
        self.num_clientes = max(3, int(num_clientes))
        self.num_cocineros = max(4, int(num_cocineros))
        self.num_repartidores = max(3, int(num_repartidores))

        self.cola_pendientes = queue.Queue(maxsize=int(pending_maxsize))
        self.cola_listos = queue.Queue(maxsize=int(ready_maxsize))

        self.kitchen_capacity = int(kitchen_capacity) if kitchen_capacity is not None else self.num_cocineros
        self.kitchen_semaphore = threading.Semaphore(self.kitchen_capacity)

        self.shutdown_event = threading.Event()

        self.metrics = {"completed": 0, "total_cycle_time": 0.0}
        self.metrics_lock = threading.Lock()

        self._id_counter = 0
        self._id_lock = threading.Lock()

        self.threads = []
        self.monitor_interval = float(monitor_interval)
        self.simulation_time = float(simulation_time)

        # Menu de ejemplo
        self.menu = [
            "Pizza Margarita",
            "Empanadas",
            "Sushi Combo",
            "Hamburguesa Clasica",
            "Ensalada Cesar",
            "Pasta Bolognesa",
        ]

    def _next_id(self):
        with self._id_lock:
            self._id_counter += 1
            return self._id_counter

    def _create_pedido(self):
        pid = self._next_id()
        nombre = random.choice(self.menu)
        # Estimación de preparación razonable
        tiempo_prep = random.uniform(0.5, 3.0)
        return Pedido(pid, nombre, tiempo_prep)

    def start(self):
        # Crear y arrancar actores
        # Clientes
        for i in range(1, self.num_clientes + 1):
            c = Cliente(i, self.cola_pendientes, self._create_pedido, self.shutdown_event)
            self.threads.append(c)
            c.start()

        # Cocineros
        for i in range(1, self.num_cocineros + 1):
            cook = Cocinero(i, self.cola_pendientes, self.cola_listos, self.kitchen_semaphore, self.shutdown_event)
            self.threads.append(cook)
            cook.start()

        # Repartidores
        for i in range(1, self.num_repartidores + 1):
            d = Repartidor(i, self.cola_listos, self.metrics, self.metrics_lock, self.shutdown_event)
            self.threads.append(d)
            d.start()

        # Monitor
        monitor = MonitorSistema(self.cola_pendientes, self.cola_listos, self.threads + [], self.shutdown_event, interval=self.monitor_interval)
        self.threads.append(monitor)
        monitor.start()

        # Programar apagado cooperativo tras el tiempo de simulación
        timer = threading.Timer(self.simulation_time, self._initiate_shutdown)
        timer.start()

        # Esperar que todos los hilos terminen
        for t in list(self.threads):
            t.join()

        # Asegurar que el timer no quede en segundo plano
        timer.cancel()

        # Reporte final de métricas
        completed = self.metrics.get("completed", 0)
        total = self.metrics.get("total_cycle_time", 0.0)
        avg = (total / completed) if completed else 0.0
        logger.info(f"Simulación finalizada. Pedidos completados={completed}, Tiempo medio ciclo={avg:.3f}s", extra={"pedido_id": "-", "estado_pedido": "-"})

    def _initiate_shutdown(self):
        logger.info("Iniciando shutdown cooperativo", extra={"pedido_id": "-", "estado_pedido": "-"})
        self.shutdown_event.set()


if __name__ == "__main__":
    # Ejecutar una simulación de ejemplo con los mínimos requeridos
    sistema = SistemaDelivery(num_clientes=3, num_cocineros=4, num_repartidores=3, pending_maxsize=20, ready_maxsize=20, simulation_time=60)
    sistema.start()
