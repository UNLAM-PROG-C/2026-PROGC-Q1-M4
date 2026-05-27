#!/usr/bin/env python3
"""
Sistema de Simulacion de Delivery Concurrente Multi-Actor
Especificacion de Desarrollo Guiado por Especificaciones (SDD)
"""

import logging
import random
import sys
import threading
import time
from queue import Empty, Full, Queue

import psutil


# ─── Logging Configuration ────────────────────────────────────────────────

class PedidoLogFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, 'pedido_id'):
            record.pedido_id = 'N/A'
        if not hasattr(record, 'estado_pedido'):
            record.estado_pedido = 'N/A'
        return super().format(record)


LOG_FORMAT = "%(asctime)s [%(threadName)s] [Pedido ID: %(pedido_id)s] [%(estado_pedido)s] -> %(message)s"
DATE_FORMAT = "%H:%M:%S"

_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(PedidoLogFormatter(LOG_FORMAT, datefmt=DATE_FORMAT))
logger = logging.getLogger("DeliverySystem")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.propagate = False


# ─── Configuration ────────────────────────────────────────────────────────

NUM_CLIENTES = 3
NUM_COCINEROS = 4
NUM_REPARTIDORES = 3
MAX_COLA_PENDIENTES = 10
MAX_COLA_LISTOS = 10
TIEMPO_SIMULACION = 60
INTERVALO_MONITOR = 2
RANGO_CREACION = (1.0, 3.0)
RANGO_COCCION = (1.0, 4.0)
RANGO_ENTREGA = (2.0, 5.0)
PLATOS = [
    "Pizza Margherita",
    "Hamburguesa Clasica",
    "Sushi Roll",
    "Pasta Carbonara",
    "Ensalada Caesar",
    "Tacos al Pastor",
]

_order_id_counter = 0
_order_id_lock = threading.Lock()


def _next_order_id():
    global _order_id_counter
    with _order_id_lock:
        _order_id_counter += 1
        return f"ORD-{_order_id_counter:04d}"


# ─── Clase Pedido ─────────────────────────────────────────────────────────

class Pedido:
    """Representa un pedido individual con maquina de estados."""

    TRANSICIONES_VALIDAS = {
        None: "PENDIENTE",
        "PENDIENTE": "EN_PREPARACION",
        "EN_PREPARACION": "LISTO",
        "LISTO": "EN_ENTREGA",
        "EN_ENTREGA": "ENTREGADO",
    }

    def __init__(self, nombre_plato, tiempo_preparacion_estimado):
        self.id_pedido = _next_order_id()
        self.nombre_plato = nombre_plato
        self.tiempo_preparacion_estimado = tiempo_preparacion_estimado
        self.timestamp_creacion = time.time()
        self.timestamp_inicio_preparacion = None
        self.timestamp_listo = None
        self.timestamp_entrega = None
        self.estado = None
        self.lock = threading.Lock()

    def cambiar_estado(self, nuevo_estado, actor_name):
        with self.lock:
            estado_anterior = self.estado
            if nuevo_estado not in set(self.TRANSICIONES_VALIDAS.values()):
                raise ValueError(f"Estado '{nuevo_estado}' no es un estado valido")
            if self.TRANSICIONES_VALIDAS.get(estado_anterior) != nuevo_estado:
                raise ValueError(
                    f"Transicion invalida: {estado_anterior} -> {nuevo_estado}"
                )
            self.estado = nuevo_estado

            now = time.time()
            if nuevo_estado == "EN_PREPARACION":
                self.timestamp_inicio_preparacion = now
            elif nuevo_estado == "LISTO":
                self.timestamp_listo = now
            elif nuevo_estado == "ENTREGADO":
                self.timestamp_entrega = now

            logger.info(
                f"{actor_name} cambio estado: {estado_anterior or 'NINGUNO'} -> {nuevo_estado} | Plato: {self.nombre_plato}",
                extra={'pedido_id': self.id_pedido, 'estado_pedido': nuevo_estado},
            )


# ─── Clase Cliente ────────────────────────────────────────────────────────

class Cliente(threading.Thread):
    """Hilo productor que genera pedidos."""

    def __init__(self, cola_pendientes, shutdown_event, name):
        super().__init__(name=name, daemon=False)
        self.cola_pendientes = cola_pendientes
        self.shutdown_event = shutdown_event

    def run(self):
        while not self.shutdown_event.is_set():
            time.sleep(random.uniform(*RANGO_CREACION))

            if self.shutdown_event.is_set():
                break

            nombre_plato = random.choice(PLATOS)
            tiempo_prep = random.uniform(*RANGO_COCCION)
            pedido = Pedido(nombre_plato, tiempo_prep)
            pedido.cambiar_estado("PENDIENTE", self.name)

            try:
                self.cola_pendientes.put(pedido, timeout=1.0)
                logger.info(
                    f"{self.name} genero {pedido.id_pedido} | Plato: {nombre_plato} | Tiempo prep: {tiempo_prep:.2f}s",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'PENDIENTE'},
                )
            except Full:
                logger.warning(
                    f"{self.name} cola pendientes llena, reintentando...",
                    extra={'pedido_id': 'N/A', 'estado_pedido': 'N/A'},
                )
            except Exception as e:
                logger.error(
                    f"{self.name} error: {e}",
                    extra={'pedido_id': 'N/A', 'estado_pedido': 'N/A'},
                )

        logger.info(
            f"{self.name} finalizando (shutdown detectado)",
            extra={'pedido_id': 'N/A', 'estado_pedido': 'SHUTDOWN'},
        )


# ─── Clase Cocinero ───────────────────────────────────────────────────────

class Cocinero(threading.Thread):
    """Hilo worker (Nivel 1) que cocina pedidos."""

    def __init__(self, cola_pendientes, cola_listos, semaforo_cocina, shutdown_event, name):
        super().__init__(name=name, daemon=False)
        self.cola_pendientes = cola_pendientes
        self.cola_listos = cola_listos
        self.semaforo_cocina = semaforo_cocina
        self.shutdown_event = shutdown_event

    def run(self):
        while True:
            try:
                pedido = self.cola_pendientes.get(timeout=0.5)
            except Empty:
                if self.shutdown_event.is_set():
                    break
                continue

            self.semaforo_cocina.acquire()

            try:
                pedido.cambiar_estado("EN_PREPARACION", self.name)

                logger.info(
                    f"{self.name} cocinando {pedido.id_pedido} | Plato: {pedido.nombre_plato} | Tiempo: {pedido.tiempo_preparacion_estimado:.2f}s",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'EN_PREPARACION'},
                )

                time.sleep(pedido.tiempo_preparacion_estimado)

                pedido.cambiar_estado("LISTO", self.name)

                self.cola_listos.put(pedido, timeout=5.0)
                logger.info(
                    f"{self.name} completo {pedido.id_pedido} | Enviado a reparto",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'LISTO'},
                )
            except Full:
                logger.error(
                    f"{self.name} cola listos llena! Reintentando...",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'LISTO'},
                )
            except Exception as e:
                logger.error(
                    f"{self.name} error procesando {pedido.id_pedido}: {e}",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'ERROR'},
                )
            finally:
                self.semaforo_cocina.release()
                self.cola_pendientes.task_done()

        logger.info(
            f"{self.name} finalizando (cola vacia + shutdown)",
            extra={'pedido_id': 'N/A', 'estado_pedido': 'SHUTDOWN'},
        )


# ─── Clase Repartidor ─────────────────────────────────────────────────────

class Repartidor(threading.Thread):
    """Hilo de reparto (Nivel 2) que entrega pedidos."""

    def __init__(self, cola_listos, stats_lock, stats, shutdown_event, name):
        super().__init__(name=name, daemon=False)
        self.cola_listos = cola_listos
        self.stats_lock = stats_lock
        self.stats = stats
        self.shutdown_event = shutdown_event

    def run(self):
        while True:
            try:
                pedido = self.cola_listos.get(timeout=0.5)
            except Empty:
                if self.shutdown_event.is_set():
                    break
                continue

            try:
                pedido.cambiar_estado("EN_ENTREGA", self.name)

                tiempo_entrega = random.uniform(*RANGO_ENTREGA)
                logger.info(
                    f"{self.name} entregando {pedido.id_pedido} | Tiempo ruta: {tiempo_entrega:.2f}s",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'EN_ENTREGA'},
                )

                time.sleep(tiempo_entrega)

                pedido.cambiar_estado("ENTREGADO", self.name)

                with self.stats_lock:
                    self.stats['completados'] += 1
                    ciclo = pedido.timestamp_entrega - pedido.timestamp_creacion
                    self.stats['tiempos_ciclo'].append(ciclo)
                    self.stats['tiempo_total_ciclo'] += ciclo

                logger.info(
                    f"{self.name} entrego {pedido.id_pedido} | Tiempo ciclo: {ciclo:.2f}s",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'ENTREGADO'},
                )
            except Exception as e:
                logger.error(
                    f"{self.name} error entregando {pedido.id_pedido}: {e}",
                    extra={'pedido_id': pedido.id_pedido, 'estado_pedido': 'ERROR'},
                )
            finally:
                self.cola_listos.task_done()

        logger.info(
            f"{self.name} finalizando (cola vacia + shutdown)",
            extra={'pedido_id': 'N/A', 'estado_pedido': 'SHUTDOWN'},
        )


# ─── Clase MonitorSistema ─────────────────────────────────────────────────

class MonitorSistema(threading.Thread):
    """Hilo de monitoreo periodico de salud del sistema."""

    def __init__(self, cola_pendientes, cola_listos, workers, shutdown_event):
        super().__init__(name="MonitorSistema", daemon=False)
        self.cola_pendientes = cola_pendientes
        self.cola_listos = cola_listos
        self.workers = workers
        self.shutdown_event = shutdown_event

    def run(self):
        while not self.shutdown_event.is_set():
            time.sleep(INTERVALO_MONITOR)

            if self.shutdown_event.is_set():
                break

            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent

                pendientes = self.cola_pendientes.qsize()
                listos = self.cola_listos.qsize()
                activos = threading.active_count()

                logger.info(
                    f"[MONITOR] Hilos activos: {activos} | Cola pendientes: {pendientes} | "
                    f"Cola listos: {listos} | CPU: {cpu:.1f}% | RAM: {ram:.1f}%",
                    extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'MONITOR'},
                )
            except Exception as e:
                logger.error(
                    f"[MONITOR] Error: {e}",
                    extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'ERROR'},
                )

        logger.info(
            "MonitorSistema finalizando",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )


# ─── Clase SistemaDelivery ────────────────────────────────────────────────

class SistemaDelivery:
    """Orquestador principal de la simulacion."""

    def __init__(self):
        self.cola_pendientes = Queue(maxsize=MAX_COLA_PENDIENTES)
        self.cola_listos = Queue(maxsize=MAX_COLA_LISTOS)

        self.shutdown_event = threading.Event()
        self.semaforo_cocina = threading.Semaphore(NUM_COCINEROS)

        self.stats_lock = threading.Lock()
        self.stats = {
            'completados': 0,
            'tiempos_ciclo': [],
            'tiempo_total_ciclo': 0.0,
        }

        self.clientes = []
        self.cocineros = []
        self.repartidores = []
        self.monitor = None

    def iniciar(self):
        logger.info(
            "=== INICIANDO SISTEMA DE DELIVERY ===",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'INICIO'},
        )
        logger.info(
            f"Config: {NUM_CLIENTES} clientes, {NUM_COCINEROS} cocineros, "
            f"{NUM_REPARTIDORES} repartidores, {TIEMPO_SIMULACION}s simulacion",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'INICIO'},
        )

        for i in range(1, NUM_CLIENTES + 1):
            t = Cliente(self.cola_pendientes, self.shutdown_event, f"Cliente-{i}")
            self.clientes.append(t)

        for i in range(1, NUM_COCINEROS + 1):
            t = Cocinero(self.cola_pendientes, self.cola_listos,
                        self.semaforo_cocina, self.shutdown_event, f"Cocinero-{i}")
            self.cocineros.append(t)

        for i in range(1, NUM_REPARTIDORES + 1):
            t = Repartidor(self.cola_listos, self.stats_lock,
                          self.stats, self.shutdown_event, f"Repartidor-{i}")
            self.repartidores.append(t)

        all_workers = self.clientes + self.cocineros + self.repartidores
        self.monitor = MonitorSistema(
            self.cola_pendientes, self.cola_listos,
            all_workers, self.shutdown_event,
        )

        for t in all_workers:
            t.start()
        self.monitor.start()

        logger.info(
            f"Todos los hilos iniciados ({threading.active_count()} activos)",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'INICIO'},
        )

    def esperar_y_apagar(self):
        logger.info(
            f"Simulacion ejecutandose por {TIEMPO_SIMULACION} segundos...",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'ACTIVO'},
        )

        time.sleep(TIEMPO_SIMULACION)

        logger.info(
            "=== INICIANDO APAGADO COOPERATIVO ===",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )

        self.shutdown_event.set()

        for t in self.clientes:
            t.join()
        logger.info(
            "Todos los clientes finalizados",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )

        for t in self.cocineros:
            t.join()
        logger.info(
            "Todos los cocineros finalizados",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )

        for t in self.repartidores:
            t.join()
        logger.info(
            "Todos los repartidores finalizados",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )

        self.monitor.join()
        logger.info(
            "Monitor finalizado",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )

    def reportar_estadisticas(self):
        with self.stats_lock:
            completados = self.stats['completados']
            tiempos = self.stats['tiempos_ciclo']
            total = self.stats['tiempo_total_ciclo']

        logger.info(
            "=== ESTADISTICAS FINALES ===",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'FINAL'},
        )
        logger.info(
            f"Pedidos completados: {completados}",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'FINAL'},
        )
        if completados > 0:
            promedio = total / completados
            min_t = min(tiempos)
            max_t = max(tiempos)
            logger.info(
                f"Tiempo ciclo - Promedio: {promedio:.2f}s | Min: {min_t:.2f}s | Max: {max_t:.2f}s",
                extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'FINAL'},
            )
        logger.info(
            "=== SISTEMA FINALIZADO ===",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'FINAL'},
        )


def main():
    sistema = SistemaDelivery()
    try:
        sistema.iniciar()
        sistema.esperar_y_apagar()
    except KeyboardInterrupt:
        logger.info(
            "Interrupcion de usuario detectada",
            extra={'pedido_id': 'SISTEMA', 'estado_pedido': 'SHUTDOWN'},
        )
        sistema.shutdown_event.set()
        for t in sistema.clientes + sistema.cocineros + sistema.repartidores:
            if t.is_alive():
                t.join(timeout=2.0)
        if sistema.monitor and sistema.monitor.is_alive():
            sistema.monitor.join(timeout=2.0)
    finally:
        sistema.reportar_estadisticas()


if __name__ == "__main__":
    main()
