import threading
import queue
import time
import random
import logging

# Configuración del formato de logging para incluir Timestamp y Thread Name automáticamente.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(message)s',
    datefmt='%H:%M:%S'
)

class EstadoPedido:
    """Clase enumerada simulada para representar los estados de un pedido."""
    PENDIENTE = "PENDIENTE"
    EN_PREPARACION = "EN_PREPARACION"
    LISTO = "LISTO"
    EN_ENTREGA = "EN_ENTREGA"
    ENTREGADO = "ENTREGADO"


class Pedido:
    """Representa un pedido generado por un cliente en el sistema."""
    
    def __init__(self, id_pedido: int, plato: str, tiempo_prep: float):
        """
        Inicializa un nuevo pedido.
        
        Args:
            id_pedido (int): Identificador único del pedido.
            plato (str): Nombre del plato a preparar.
            tiempo_prep (float): Tiempo estimado de preparación en segundos.
        """
        self.id = id_pedido
        self.plato = plato
        self.tiempo_prep = tiempo_prep
        self.estado = EstadoPedido.PENDIENTE
        
        # Lock individual para asegurar transiciones de estado atómicas.
        self.lock = threading.Lock()
        
        self.ts_creacion = time.time()
        self.ts_prep = None
        self.ts_listo = None
        self.ts_entregado = None

    def cambiar_estado(self, nuevo_estado: str):
        """
        Cambia el estado del pedido de forma atómica y registra los timestamps.
        
        Args:
            nuevo_estado (str): El nuevo estado a asignar al pedido.
        """
        with self.lock:
            self.estado = nuevo_estado
            if nuevo_estado == EstadoPedido.EN_PREPARACION:
                self.ts_prep = time.time()
            elif nuevo_estado == EstadoPedido.LISTO:
                self.ts_listo = time.time()
            elif nuevo_estado == EstadoPedido.ENTREGADO:
                self.ts_entregado = time.time()
            
            logging.info(f"Pedido {self.id} | Estado: {self.estado} | Plato: {self.plato}")


class SistemaDelivery:
    """Clase principal que contiene el estado compartido y orquesta el sistema."""
    
    def __init__(self):
        """Inicializa las configuraciones, colas, sincronizadores y métricas del sistema."""
        # --- CONFIGURACIÓN ---
        self.NUM_CLIENTES = 3
        self.NUM_COCINEROS = 4
        self.NUM_REPARTIDORES = 3
        self.TIEMPO_SIMULACION = 30  # Segundos de ejecución antes de iniciar el apagado
        self.CAPACIDAD_COLA = 15
        
        # --- COLAS (Productor-Consumidor) ---
        self.cola_pendientes = queue.Queue(maxsize=self.CAPACIDAD_COLA)
        self.cola_listos = queue.Queue(maxsize=self.CAPACIDAD_COLA)
        
        # --- SINCRONIZADORES ---
        self.shutdown_event = threading.Event()
        self.semaforo_cocina = threading.Semaphore(self.NUM_COCINEROS)
        
        self.lock_metricas = threading.Lock()
        self.lock_activos = threading.Lock()
        
        # --- ESTADO COMPARTIDO ---
        self.pedidos_activos = 0  # Permite a los consumidores saber si quedan pedidos en el flujo
        self.contador_ids = 0     # Generador de IDs únicos
        
        self.metricas = {
            "generados": 0,
            "completados": 0,
            "descartados": 0,
            "tiempo_prep_total": 0.0,
            "tiempo_entrega_total": 0.0,
            "tiempo_total_ciclo": 0.0
        }

    def generar_id_pedido(self) -> int:
        """Genera un ID único para un pedido de forma segura."""
        with self.lock_activos:
            self.contador_ids += 1
            return self.contador_ids

    def registrar_completado(self, pedido: Pedido):
        """
        Registra las métricas de un pedido completado y actualiza el estado global.
        El orden de adquisición de locks es consistente (evita deadlocks al no anidar locks compartidos).
        """
        # Calcular tiempos (sin necesidad de bloquear pedido, pues sus timestamps ya no mutan)
        tiempo_prep = pedido.ts_listo - pedido.ts_prep
        tiempo_entrega = pedido.ts_entregado - pedido.ts_listo
        tiempo_total = pedido.ts_entregado - pedido.ts_creacion
        
        with self.lock_metricas:
            self.metricas["completados"] += 1
            self.metricas["tiempo_prep_total"] += tiempo_prep
            self.metricas["tiempo_entrega_total"] += tiempo_entrega
            self.metricas["tiempo_total_ciclo"] += tiempo_total
            
        with self.lock_activos:
            self.pedidos_activos -= 1

    def registrar_descartado(self):
        """Registra un pedido que no pudo ser procesado durante el apagado."""
        with self.lock_metricas:
            self.metricas["descartados"] += 1
        with self.lock_activos:
            self.pedidos_activos -= 1

    def imprimir_resumen(self):
        """Imprime el resumen estadístico final de la simulación."""
        completados = self.metricas["completados"]
        logging.info("===============================================")
        logging.info("         RESUMEN FINAL DE LA SIMULACIÓN        ")
        logging.info("===============================================")
        logging.info(f"Total generados:   {self.metricas['generados']}")
        logging.info(f"Total completados: {completados}")
        logging.info(f"Total descartados: {self.metricas['descartados']}")
        
        if completados > 0:
            avg_prep = self.metricas["tiempo_prep_total"] / completados
            avg_entrega = self.metricas["tiempo_entrega_total"] / completados
            avg_total = self.metricas["tiempo_total_ciclo"] / completados
            throughput = completados / (self.TIEMPO_SIMULACION / 60.0)
            
            logging.info(f"Tiempo prom. preparación: {avg_prep:.2f} seg")
            logging.info(f"Tiempo prom. entrega:     {avg_entrega:.2f} seg")
            logging.info(f"Tiempo prom. total:       {avg_total:.2f} seg")
            logging.info(f"Throughput:               {throughput:.2f} pedidos/minuto")
        logging.info("===============================================")


class Cliente(threading.Thread):
    """Actor que genera pedidos de forma aleatoria."""
    
    def __init__(self, nombre: str, sistema: SistemaDelivery):
        super().__init__(name=nombre, daemon=False)
        self.sistema = sistema
        self.platos = ["Pizza", "Hamburguesa", "Sushi", "Ensalada", "Tacos"]

    def run(self):
        """Ciclo de vida del cliente: genera pedidos mientras el sistema esté activo."""
        while not self.sistema.shutdown_event.is_set():
            time.sleep(random.uniform(1.0, 3.0))  # Intervalo entre pedidos
            
            if self.sistema.shutdown_event.is_set():
                break

            id_pedido = self.sistema.generar_id_pedido()
            plato = random.choice(self.platos)
            tiempo_prep = random.uniform(2.0, 5.0)
            
            pedido = Pedido(id_pedido, plato, tiempo_prep)
            
            with self.sistema.lock_metricas:
                self.sistema.metricas["generados"] += 1
            with self.sistema.lock_activos:
                self.sistema.pedidos_activos += 1
                
            logging.info(f"Pedido {pedido.id} | Estado: {pedido.estado} | Creado por cliente")
            
            # Intentar encolar, manejando el apagado cooperativo si la cola está llena
            while not self.sistema.shutdown_event.is_set():
                try:
                    self.sistema.cola_pendientes.put(pedido, timeout=1.0)
                    break
                except queue.Full:
                    continue
            
            # Si salimos del loop por shutdown sin encolar
            if self.sistema.shutdown_event.is_set() and pedido.estado == EstadoPedido.PENDIENTE:
                try:
                    # Intento final no bloqueante
                    self.sistema.cola_pendientes.put_nowait(pedido)
                except queue.Full:
                    self.sistema.registrar_descartado()


class Cocinero(threading.Thread):
    """Actor que procesa pedidos pendientes y los convierte en listos."""
    
    def __init__(self, nombre: str, sistema: SistemaDelivery):
        super().__init__(name=nombre, daemon=False)
        self.sistema = sistema

    def run(self):
        """Ciclo de preparación: toma pedidos y usa el semáforo para simular cocina."""
        # Se detiene si hay evento de apagado Y la cola de pendientes está vacía.
        while not (self.sistema.shutdown_event.is_set() and self.sistema.cola_pendientes.empty()):
            try:
                pedido = self.sistema.cola_pendientes.get(timeout=1.0)
            except queue.Empty:
                continue

            # Semáforo para limitar preparación concurrente según cantidad de cocineros
            with self.sistema.semaforo_cocina:
                pedido.cambiar_estado(EstadoPedido.EN_PREPARACION)
                time.sleep(pedido.tiempo_prep)
                pedido.cambiar_estado(EstadoPedido.LISTO)
            
            # Encolar a listos
            while True:
                try:
                    self.sistema.cola_listos.put(pedido, timeout=1.0)
                    break
                except queue.Full:
                    if self.sistema.shutdown_event.is_set() and self.sistema.pedidos_activos == 0:
                        break # Prevención de escape si la lógica falla (poco probable)
                    continue
            
            self.sistema.cola_pendientes.task_done()


class Repartidor(threading.Thread):
    """Actor que toma pedidos listos y los entrega al cliente."""
    
    def __init__(self, nombre: str, sistema: SistemaDelivery):
        super().__init__(name=nombre, daemon=False)
        self.sistema = sistema

    def run(self):
        """Ciclo de entrega: toma pedidos listos y finaliza el ciclo."""
        # Se detiene únicamente cuando el sistema se apaga y no queda NINGÚN pedido activo.
        while True:
            if self.sistema.shutdown_event.is_set():
                with self.sistema.lock_activos:
                    if self.sistema.pedidos_activos == 0:
                        break

            try:
                pedido = self.sistema.cola_listos.get(timeout=1.0)
            except queue.Empty:
                continue

            pedido.cambiar_estado(EstadoPedido.EN_ENTREGA)
            tiempo_entrega = random.uniform(2.0, 4.0)
            time.sleep(tiempo_entrega)
            
            pedido.cambiar_estado(EstadoPedido.ENTREGADO)
            self.sistema.registrar_completado(pedido)
            
            self.sistema.cola_listos.task_done()


class MonitorSistema(threading.Thread):
    """Hilo dedicado a observar y loguear el estado general del sistema."""
    
    def __init__(self, sistema: SistemaDelivery):
        super().__init__(name="Monitor-1", daemon=False)
        self.sistema = sistema
        self.intervalo = 5.0

    def run(self):
        """Imprime la telemetría periódicamente."""
        while not self.sistema.shutdown_event.is_set():
            time.sleep(self.intervalo)
            if self.sistema.shutdown_event.is_set():
                break
                
            q_pendientes = self.sistema.cola_pendientes.qsize()
            q_listos = self.sistema.cola_listos.qsize()
            
            with self.sistema.lock_activos:
                activos = self.sistema.pedidos_activos
                
            with self.sistema.lock_metricas:
                completados = self.sistema.metricas["completados"]
                
            threads_vivos = threading.active_count()
            
            logging.info(f"Pedido N/A | Estado: N/A | [MONITOR] "
                         f"Pendientes={q_pendientes}, Listos={q_listos}, "
                         f"Activos en Flujo={activos}, Completados={completados}, "
                         f"Threads Activos={threads_vivos}")


# ==========================================
# INICIO DE LA APLICACIÓN
# ==========================================
if __name__ == "__main__":
    sistema = SistemaDelivery()
    hilos = []

    logging.info("Pedido N/A | Estado: N/A | Iniciando Sistema de Delivery (Uber Eats/PedidosYa Simulador)")

    # 1. Crear y arrancar Monitor
    monitor = MonitorSistema(sistema)
    hilos.append(monitor)
    monitor.start()

    # 2. Crear y arrancar Clientes (Producers)
    for i in range(sistema.NUM_CLIENTES):
        cliente = Cliente(f"Cliente-{i+1}", sistema)
        hilos.append(cliente)
        cliente.start()

    # 3. Crear y arrancar Cocineros (Workers Nivel 1)
    for i in range(sistema.NUM_COCINEROS):
        cocinero = Cocinero(f"Cocinero-{i+1}", sistema)
        hilos.append(cocinero)
        cocinero.start()

    # 4. Crear y arrancar Repartidores (Workers Nivel 2)
    for i in range(sistema.NUM_REPARTIDORES):
        repartidor = Repartidor(f"Repartidor-{i+1}", sistema)
        hilos.append(repartidor)
        repartidor.start()

    # Espera simulando el paso del tiempo de la jornada operativa
    try:
        time.sleep(sistema.TIEMPO_SIMULACION)
    except KeyboardInterrupt:
        logging.info("Pedido N/A | Estado: N/A | Interrupción manual detectada.")

    logging.info("Pedido N/A | Estado: N/A | Tiempo límite alcanzado. Iniciando apagado cooperativo...")
    
    # Activar apagado: esto detendrá primero a los clientes de generar más pedidos.
    sistema.shutdown_event.set()

    # Esperar a que los hilos terminen limpiamente
    for hilo in hilos:
        hilo.join()

    logging.info("Pedido N/A | Estado: N/A | Todos los hilos han terminado correctamente. Colas vaciadas.")
    sistema.imprimir_resumen()