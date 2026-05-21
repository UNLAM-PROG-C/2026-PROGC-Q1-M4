"""
Sistema de Delivery Concurrente - Simulación estilo Uber Eats / PedidosYa
Implementado con threading puro (Python 3.10+)

Orden de adquisición de locks (para evitar deadlock):
  1. Lock del pedido (pedido._lock) — siempre antes de stats_lock
  2. stats_lock                    — nunca anidado con otro lock
"""

import threading
import queue
import time
import random
import logging
from collections import Counter
from enum import Enum, auto
import psutil
import os

# ---------------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------------
NUM_CLIENTES = 3
NUM_COCINEROS = 4
NUM_REPARTIDORES = 3
CAPACIDAD_COLA_PENDIENTES = 10
CAPACIDAD_COLA_LISTOS = 10
INTERVALO_CLIENTE = (1.0, 3.0)       # segundos entre pedidos por cliente
TIEMPO_ENTREGA = (2.0, 5.0)          # segundos que tarda un repartidor
TIEMPO_SIMULACION = 10               # segundos totales de simulación
INTERVALO_MONITOR = 5                # segundos entre reportes del monitor

PLATOS = [
    ("Pizza Margherita", 4.0),
    ("Hamburguesa Clásica", 3.0),
    ("Sushi Roll", 5.0),
    ("Pasta Carbonara", 3.5),
    ("Ensalada César", 2.0),
    ("Tacos al Pastor", 2.5),
    ("Pollo al Curry", 4.5),
    ("Milanesa Napolitana", 4.0),
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)-20s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ESTADO DEL PEDIDO
# ---------------------------------------------------------------------------
class EstadoPedido(Enum):
    PENDIENTE = auto()
    EN_PREPARACION = auto()
    LISTO = auto()
    EN_ENTREGA = auto()
    ENTREGADO = auto()
    DESCARTADO = auto()


# ---------------------------------------------------------------------------
# CLASE PEDIDO
# ---------------------------------------------------------------------------
class Pedido:
    """Representa un pedido con máquina de estados protegida por un Lock."""

    _id_counter = 0
    _id_lock = threading.Lock()

    def __init__(self, nombre_plato: str, tiempo_preparacion: float):
        with Pedido._id_lock:
            Pedido._id_counter += 1
            self.id = Pedido._id_counter

        self.nombre_plato = nombre_plato
        self.tiempo_preparacion = tiempo_preparacion
        self.estado = EstadoPedido.PENDIENTE
        self._lock = threading.Lock()

        self.ts_creacion = time.monotonic()
        self.ts_inicio_prep: float | None = None
        self.ts_fin_prep: float | None = None
        self.ts_inicio_entrega: float | None = None
        self.ts_entregado: float | None = None

    def transicionar(self, nuevo_estado: EstadoPedido) -> bool:
        """Transición atómica de estado. Retorna True si fue exitosa."""
        transiciones_validas = {
            EstadoPedido.PENDIENTE:        EstadoPedido.EN_PREPARACION,
            EstadoPedido.EN_PREPARACION:   EstadoPedido.LISTO,
            EstadoPedido.LISTO:            EstadoPedido.EN_ENTREGA,
            EstadoPedido.EN_ENTREGA:       EstadoPedido.ENTREGADO,
        }
        with self._lock:
            if transiciones_validas.get(self.estado) == nuevo_estado:
                self.estado = nuevo_estado
                return True
            if nuevo_estado == EstadoPedido.DESCARTADO:
                self.estado = nuevo_estado
                return True
            return False

    def duracion_preparacion(self) -> float | None:
        """Tiempo de preparación en segundos, o None si no está disponible."""
        if self.ts_inicio_prep and self.ts_fin_prep:
            return self.ts_fin_prep - self.ts_inicio_prep
        return None

    def duracion_entrega(self) -> float | None:
        """Tiempo de entrega en segundos, o None si no está disponible."""
        if self.ts_inicio_entrega and self.ts_entregado:
            return self.ts_entregado - self.ts_inicio_entrega
        return None

    def duracion_total(self) -> float | None:
        """Tiempo total desde creación hasta entrega, o None si no está disponible."""
        if self.ts_entregado:
            return self.ts_entregado - self.ts_creacion
        return None

    def __str__(self) -> str:
        return f"Pedido#{self.id}[{self.nombre_plato}|{self.estado.name}]"


# ---------------------------------------------------------------------------
# CLASE CLIENTE
# ---------------------------------------------------------------------------
class Cliente(threading.Thread):
    """
    Produce pedidos de forma aleatoria y los encola en cola_pendientes.
    Se bloquea si la cola está llena (comportamiento natural de queue.Queue).
    """

    def __init__(
        self,
        cliente_id: int,
        cola_pendientes: queue.Queue,
        shutdown_event: threading.Event,
        stats: "Estadisticas",
        intervalo: tuple[float, float] = INTERVALO_CLIENTE,
    ):
        super().__init__(name=f"Cliente-{cliente_id}", daemon=False)
        self.cliente_id = cliente_id
        self.cola_pendientes = cola_pendientes
        self.shutdown_event = shutdown_event
        self.stats = stats
        self.intervalo = intervalo

    def run(self) -> None:
        """Genera pedidos hasta que se active el evento de apagado."""
        log.info(f"[{self.name}] Iniciado.")
        while not self.shutdown_event.is_set():
            plato, tiempo_prep = random.choice(PLATOS)
            pedido = Pedido(plato, tiempo_prep)
            self.stats.registrar_generado()

            try:
                self.cola_pendientes.put(pedido, timeout=1.0)
                log.info(f"[{self.name}] Nuevo pedido {pedido} encolado.")
            except queue.Full:
                pedido.transicionar(EstadoPedido.DESCARTADO)
                self.stats.registrar_descartado()
                log.warning(f"[{self.name}] Cola llena, {pedido} descartado.")

            espera = random.uniform(*self.intervalo)
            self.shutdown_event.wait(timeout=espera)

        log.info(f"[{self.name}] Apagado ordenado completado.")


# ---------------------------------------------------------------------------
# CLASE COCINERO
# ---------------------------------------------------------------------------
class Cocinero(threading.Thread):
    """
    Consume pedidos de cola_pendientes, los prepara y los pasa a cola_listos.
    Usa un Semaphore para limitar la concurrencia máxima de preparaciones.
    """

    def __init__(
        self,
        cocinero_id: int,
        cola_pendientes: queue.Queue,
        cola_listos: queue.Queue,
        shutdown_event: threading.Event,
        sem_preparacion: threading.Semaphore,
        stats: "Estadisticas",
    ):
        super().__init__(name=f"Cocinero-{cocinero_id}", daemon=False)
        self.cocinero_id = cocinero_id
        self.cola_pendientes = cola_pendientes
        self.cola_listos = cola_listos
        self.shutdown_event = shutdown_event
        self.sem_preparacion = sem_preparacion
        self.stats = stats

    def run(self) -> None:
        """Prepara pedidos hasta que se active el apagado y la cola esté vacía."""
        log.info(f"[{self.name}] Iniciado.")
        while True:
            try:
                pedido = self.cola_pendientes.get(timeout=1.0)
            except queue.Empty:
                if self.shutdown_event.is_set():
                    break
                continue

            self.sem_preparacion.acquire()
            try:
                ok = pedido.transicionar(EstadoPedido.EN_PREPARACION)
                if not ok:
                    log.warning(f"[{self.name}] Transición fallida para {pedido}.")
                    self.cola_pendientes.task_done()
                    continue

                pedido.ts_inicio_prep = time.monotonic()
                log.info(f"[{self.name}] Preparando {pedido} ({pedido.tiempo_preparacion:.1f}s).")
                time.sleep(pedido.tiempo_preparacion)
                pedido.ts_fin_prep = time.monotonic()

                pedido.transicionar(EstadoPedido.LISTO)
                log.info(f"[{self.name}] {pedido} listo.")

                self.cola_listos.put(pedido)
            finally:
                self.sem_preparacion.release()
                self.cola_pendientes.task_done()

        log.info(f"[{self.name}] Apagado ordenado completado.")


# ---------------------------------------------------------------------------
# CLASE REPARTIDOR
# ---------------------------------------------------------------------------
class Repartidor(threading.Thread):
    """
    Consume pedidos de cola_listos y los entrega con un tiempo aleatorio.
    Actualiza las estadísticas globales al completar cada entrega.
    """

    def __init__(
        self,
        repartidor_id: int,
        cola_listos: queue.Queue,
        shutdown_event: threading.Event,
        stats: "Estadisticas",
        tiempo_entrega: tuple[float, float] = TIEMPO_ENTREGA,
    ):
        super().__init__(name=f"Repartidor-{repartidor_id}", daemon=False)
        self.repartidor_id = repartidor_id
        self.cola_listos = cola_listos
        self.shutdown_event = shutdown_event
        self.stats = stats
        self.tiempo_entrega = tiempo_entrega

    def run(self) -> None:
        """Entrega pedidos hasta que se active el apagado y la cola esté vacía."""
        log.info(f"[{self.name}] Iniciado.")
        while True:
            try:
                pedido = self.cola_listos.get(timeout=1.0)
            except queue.Empty:
                if self.shutdown_event.is_set():
                    break
                continue

            ok = pedido.transicionar(EstadoPedido.EN_ENTREGA)
            if not ok:
                log.warning(f"[{self.name}] Transición fallida para {pedido}.")
                self.cola_listos.task_done()
                continue

            pedido.ts_inicio_entrega = time.monotonic()
            duracion = random.uniform(*self.tiempo_entrega)
            log.info(f"[{self.name}] Entregando {pedido} ({duracion:.1f}s).")
            time.sleep(duracion)
            pedido.ts_entregado = time.monotonic()

            pedido.transicionar(EstadoPedido.ENTREGADO)
            log.info(f"[{self.name}] {pedido} entregado. Total={pedido.duracion_total():.1f}s.")

            self.stats.registrar_entregado(pedido)
            self.cola_listos.task_done()

        log.info(f"[{self.name}] Apagado ordenado completado.")


# ---------------------------------------------------------------------------
# ESTADÍSTICAS GLOBALES (thread-safe)
# ---------------------------------------------------------------------------
class Estadisticas:
    """Contador de métricas globales protegido por un Lock."""

    def __init__(self):
        self._lock = threading.Lock()
        self.generados = 0
        self.completados = 0
        self.descartados = 0
        self._tiempos_prep: list[float] = []
        self._tiempos_entrega: list[float] = []
        self._tiempos_total: list[float] = []
        self.peak_cpu_pct: float = 0.0
        self.peak_mem_rss_mb: float = 0.0

    def registrar_generado(self) -> None:
        """Incrementa el contador de pedidos generados."""
        with self._lock:
            self.generados += 1

    def registrar_descartado(self) -> None:
        """Incrementa el contador de pedidos descartados."""
        with self._lock:
            self.descartados += 1

    def registrar_entregado(self, pedido: Pedido) -> None:
        """Registra las métricas de un pedido completado."""
        tp = pedido.duracion_preparacion()
        te = pedido.duracion_entrega()
        tt = pedido.duracion_total()
        with self._lock:
            self.completados += 1
            if tp is not None:
                self._tiempos_prep.append(tp)
            if te is not None:
                self._tiempos_entrega.append(te)
            if tt is not None:
                self._tiempos_total.append(tt)

    def actualizar_recursos(self, cpu_pct: float, mem_rss_mb: float) -> None:
        """Actualiza los picos de CPU y memoria si se superan los máximos registrados."""
        with self._lock:
            if cpu_pct > self.peak_cpu_pct:
                self.peak_cpu_pct = cpu_pct
            if mem_rss_mb > self.peak_mem_rss_mb:
                self.peak_mem_rss_mb = mem_rss_mb

    def snapshot(self) -> dict:
        """Retorna una copia de las estadísticas actuales."""
        with self._lock:
            return {
                "generados": self.generados,
                "completados": self.completados,
                "descartados": self.descartados,
                "avg_prep": (sum(self._tiempos_prep) / len(self._tiempos_prep)) if self._tiempos_prep else 0.0,
                "avg_entrega": (sum(self._tiempos_entrega) / len(self._tiempos_entrega)) if self._tiempos_entrega else 0.0,
                "avg_total": (sum(self._tiempos_total) / len(self._tiempos_total)) if self._tiempos_total else 0.0,
                "peak_cpu_pct": self.peak_cpu_pct,
                "peak_mem_rss_mb": self.peak_mem_rss_mb,
            }


# ---------------------------------------------------------------------------
# MONITOR DEL SISTEMA
# ---------------------------------------------------------------------------
class MonitorSistema(threading.Thread):
    """
    Hilo de monitoreo que imprime el estado del sistema cada N segundos.
    Lee el tamaño de las colas y las estadísticas globales.
    """

    def __init__(
        self,
        cola_pendientes: queue.Queue,
        cola_listos: queue.Queue,
        shutdown_event: threading.Event,
        stats: Estadisticas,
        intervalo: float = INTERVALO_MONITOR,
    ):
        super().__init__(name="Monitor", daemon=False)
        self.cola_pendientes = cola_pendientes
        self.cola_listos = cola_listos
        self.shutdown_event = shutdown_event
        self.stats = stats
        self.intervalo = intervalo
        self._proceso = psutil.Process(os.getpid())
        # Primera llamada descartada: psutil necesita un intervalo previo para cpu_percent
        self._proceso.cpu_percent(interval=None)

    def run(self) -> None:
        """Imprime el estado del sistema periódicamente hasta el apagado."""
        log.info("[Monitor] Iniciado.")
        while not self.shutdown_event.is_set():
            self.shutdown_event.wait(timeout=self.intervalo)
            self._imprimir_estado()
        self._imprimir_estado()
        log.info("[Monitor] Apagado ordenado completado.")

    def _imprimir_estado(self) -> None:
        """Imprime una línea de estado con las métricas actuales de pedidos y recursos."""
        snap = self.stats.snapshot()
        threads_activos = threading.active_count()

        cpu_pct = self._proceso.cpu_percent(interval=None)
        mem_rss_mb = self._proceso.memory_info().rss / (1024 * 1024)
        self.stats.actualizar_recursos(cpu_pct, mem_rss_mb)

        log.info(
            f"[Monitor] === ESTADO === "
            f"Pendientes={self.cola_pendientes.qsize()} "
            f"Listos={self.cola_listos.qsize()} "
            f"Completados={snap['completados']} "
            f"Descartados={snap['descartados']} "
            f"Threads={threads_activos} "
            f"CPU={cpu_pct:.1f}% "
            f"RAM={mem_rss_mb:.1f}MB"
        )


# ---------------------------------------------------------------------------
# SISTEMA DELIVERY (coordinador principal)
# ---------------------------------------------------------------------------
class SistemaDelivery:
    """
    Clase principal que instancia y coordina todos los actores del sistema.
    Gestiona el ciclo de vida de los threads y el apagado ordenado.
    """

    def __init__(
        self,
        num_clientes: int = NUM_CLIENTES,
        num_cocineros: int = NUM_COCINEROS,
        num_repartidores: int = NUM_REPARTIDORES,
        cap_pendientes: int = CAPACIDAD_COLA_PENDIENTES,
        cap_listos: int = CAPACIDAD_COLA_LISTOS,
        tiempo_simulacion: float = TIEMPO_SIMULACION,
    ):
        self.num_clientes = num_clientes
        self.num_cocineros = num_cocineros
        self.num_repartidores = num_repartidores
        self.tiempo_simulacion = tiempo_simulacion

        self.cola_pendientes: queue.Queue = queue.Queue(maxsize=cap_pendientes)
        self.cola_listos: queue.Queue = queue.Queue(maxsize=cap_listos)
        self.shutdown_event = threading.Event()
        # Semáforo: máximo NUM_COCINEROS preparaciones simultáneas
        self.sem_preparacion = threading.Semaphore(num_cocineros)
        self.stats = Estadisticas()

        self._threads: list[threading.Thread] = []

    def _crear_threads(self) -> None:
        """Instancia todos los threads de actores y el monitor."""
        for i in range(1, self.num_clientes + 1):
            self._threads.append(Cliente(
                i, self.cola_pendientes, self.shutdown_event, self.stats
            ))
        for i in range(1, self.num_cocineros + 1):
            self._threads.append(Cocinero(
                i, self.cola_pendientes, self.cola_listos,
                self.shutdown_event, self.sem_preparacion, self.stats
            ))
        for i in range(1, self.num_repartidores + 1):
            self._threads.append(Repartidor(
                i, self.cola_listos, self.shutdown_event, self.stats
            ))
        self._threads.append(MonitorSistema(
            self.cola_pendientes, self.cola_listos,
            self.shutdown_event, self.stats
        ))

    def ejecutar(self) -> None:
        """Inicia la simulación, espera el tiempo configurado y apaga ordenadamente."""
        log.info(f"[Sistema] Iniciando simulación ({self.tiempo_simulacion}s).")
        log.info(
            f"[Sistema] Config: {self.num_clientes} clientes, "
            f"{self.num_cocineros} cocineros, {self.num_repartidores} repartidores."
        )

        self._crear_threads()
        ts_inicio = time.monotonic()

        for t in self._threads:
            t.start()

        time.sleep(self.tiempo_simulacion)

        log.info("[Sistema] Tiempo agotado. Iniciando apagado ordenado...")
        self.shutdown_event.set()

        for t in self._threads:
            t.join()

        ts_fin = time.monotonic()
        duracion_real = ts_fin - ts_inicio
        self._imprimir_resumen(duracion_real)

    def _imprimir_resumen(self, duracion_real: float) -> None:
        """Imprime el resumen final de métricas al concluir la simulación."""
        snap = self.stats.snapshot()
        throughput = (snap["completados"] / duracion_real) * 60 if duracion_real > 0 else 0

        separador = "=" * 60
        log.info(separador)
        log.info("[Sistema] RESUMEN FINAL DE MÉTRICAS")
        log.info(separador)
        log.info(f"  Duración real de la simulación : {duracion_real:.1f}s")
        log.info(f"  Pedidos generados              : {snap['generados']}")
        log.info(f"  Pedidos completados            : {snap['completados']}")
        log.info(f"  Pedidos descartados            : {snap['descartados']}")
        log.info(f"  Tiempo promedio de preparación : {snap['avg_prep']:.2f}s")
        log.info(f"  Tiempo promedio de entrega     : {snap['avg_entrega']:.2f}s")
        log.info(f"  Tiempo promedio total          : {snap['avg_total']:.2f}s")
        log.info(f"  Throughput                     : {throughput:.2f} pedidos/min")
        log.info(f"  Pico de CPU del proceso        : {snap['peak_cpu_pct']:.1f}%")
        log.info(f"  Pico de memoria RSS            : {snap['peak_mem_rss_mb']:.1f} MB")
        log.info(separador)

# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sistema = SistemaDelivery(
        num_clientes=NUM_CLIENTES,
        num_cocineros=NUM_COCINEROS,
        num_repartidores=NUM_REPARTIDORES,
        cap_pendientes=CAPACIDAD_COLA_PENDIENTES,
        cap_listos=CAPACIDAD_COLA_LISTOS,
        tiempo_simulacion=TIEMPO_SIMULACION,
    )
    sistema.ejecutar()
