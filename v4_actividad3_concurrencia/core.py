import asyncio
import hashlib
import hmac
import json
import os
import random
import time
import uuid
import zlib
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


class Registro:
    visible = True
    inicio = time.perf_counter()


def registrar(mensaje, forzar=False):
    if Registro.visible or forzar:
        hora = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        transcurrido = time.perf_counter() - Registro.inicio
        print(f"[{hora} | {transcurrido:7.3f}s] {mensaje}", flush=True)


@dataclass
class Evento:
    tipo: str
    tx_id: str
    origen: str = ""
    datos: dict = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    creado_en: float = field(default_factory=time.time)
    firma: str = ""
    intentos: int = 0

    def contenido(self):
        return json.dumps(
            {
                "tipo": self.tipo,
                "tx_id": self.tx_id,
                "origen": self.origen,
                "datos": self.datos,
                "event_id": self.event_id,
                "creado_en": self.creado_en,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def desde_dict(cls, datos):
        return cls(**datos)


@dataclass
class Credencial:
    participante: str
    clave: bytes

    def firmar(self, evento):
        evento.origen = self.participante
        evento.firma = hmac.new(self.clave, evento.contenido(), hashlib.sha256).hexdigest()
        return evento


class Seguridad:
    def __init__(self):
        self.claves = {}

    def registrar(self, participante):
        clave = os.urandom(32)
        self.claves[participante] = clave
        return Credencial(participante, clave)

    def verificar(self, evento):
        clave = self.claves.get(evento.origen)
        if clave is None or not evento.firma:
            return False
        firma = hmac.new(clave, evento.contenido(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(firma, evento.firma)


class Journal:
    def __init__(self, ruta, reiniciar=False):
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        if reiniciar:
            self.ruta.write_text("", encoding="utf-8")
        else:
            self.ruta.touch(exist_ok=True)
        self.archivo = self.ruta.open("a", encoding="utf-8")

    def publicar(self, evento):
        self.archivo.write(json.dumps({"op": "PUB", "evento": asdict(evento)}) + "\n")
        self.archivo.flush()
        os.fsync(self.archivo.fileno())

    def confirmar(self, event_id):
        self.archivo.write(json.dumps({"op": "ACK", "event_id": event_id}) + "\n")
        self.archivo.flush()
        os.fsync(self.archivo.fileno())

    def pendientes(self):
        publicados = {}
        confirmados = set()
        with self.ruta.open(encoding="utf-8") as archivo:
            for linea in archivo:
                if not linea.strip():
                    continue
                registro = json.loads(linea)
                if registro["op"] == "PUB":
                    evento = registro["evento"]
                    publicados[evento["event_id"]] = evento
                elif registro["op"] == "ACK":
                    confirmados.add(registro["event_id"])
        return [Evento.desde_dict(evento) for event_id, evento in publicados.items() if event_id not in confirmados]

    def cerrar(self):
        if not self.archivo.closed:
            self.archivo.close()


class Bus:
    def __init__(self, particiones=1, journal=None):
        if particiones < 1:
            raise ValueError("Debe existir al menos una particion")
        self.colas = [asyncio.Queue() for _ in range(particiones)]
        self.buzones = defaultdict(asyncio.Queue)
        self.journal = journal
        self.publicados = 0

    def particion(self, tx_id):
        return zlib.crc32(tx_id.encode("utf-8")) % len(self.colas)

    async def publicar(self, evento, persistir=True):
        if persistir and self.journal:
            self.journal.publicar(evento)
        await self.colas[self.particion(evento.tx_id)].put(evento)
        self.publicados += 1

    async def recuperar(self, evento):
        await self.publicar(evento, persistir=False)

    async def notificar(self, destinatario, mensaje):
        await self.buzones[destinatario].put(mensaje)

    async def recibir(self, destinatario, timeout=None):
        operacion = self.buzones[destinatario].get()
        if timeout is None:
            return await operacion
        return await asyncio.wait_for(operacion, timeout)

    async def vaciar(self):
        await asyncio.gather(*(cola.join() for cola in self.colas))

    def profundidad(self):
        return sum(cola.qsize() for cola in self.colas)


class MotorReglas:
    def __init__(self):
        self.manejadores = defaultdict(list)
        self.roles = {}
        self.reglas = []
        self.evento_inicial = None

    def manejar(self, tipo, rol, inicial=False):
        def registrar_manejador(funcion):
            self.roles[tipo] = rol
            self.manejadores[tipo].append(funcion)
            if inicial:
                self.evento_inicial = tipo
            return funcion
        return registrar_manejador

    def regla(self, funcion):
        self.reglas.append(funcion)
        return funcion


@dataclass
class Transaccion:
    id: str
    valor: int
    comprador: str
    vendedor: str
    estado: str = "INICIADA"
    pago_confirmado: bool = False
    producto_despachado: bool = False
    entrega_confirmada: bool = False
    dinero_liberado: bool = False
    reembolsada: bool = False
    cancelada: bool = False
    motivo: str = ""
    historial: list = field(default_factory=list)
    inicio: float = field(default_factory=time.perf_counter)
    fin: Optional[float] = None

    def cambiar_estado(self, estado, motivo=""):
        self.estado = estado
        self.motivo = motivo
        self.historial.append(
            {
                "tiempo": round(time.perf_counter() - self.inicio, 6),
                "estado": estado,
                "motivo": motivo,
            }
        )

    def resumen(self):
        return {
            "id": self.id,
            "valor": self.valor,
            "comprador": self.comprador,
            "vendedor": self.vendedor,
            "estado": self.estado,
            "pago_confirmado": self.pago_confirmado,
            "producto_despachado": self.producto_despachado,
            "entrega_confirmada": self.entrega_confirmada,
            "dinero_liberado": self.dinero_liberado,
            "reembolsada": self.reembolsada,
            "cancelada": self.cancelada,
            "motivo": self.motivo,
            "latencia": round(self.fin - self.inicio, 6) if self.fin else None,
        }


class ErrorNegocio(Exception):
    pass


class FalloTemporal(Exception):
    pass


class ServicioEscrow:
    def __init__(self, bus, motor, seguridad, probabilidad_fallo=0.0, max_intentos=3, latencia=0.0):
        self.bus = bus
        self.motor = motor
        self.seguridad = seguridad
        self.probabilidad_fallo = probabilidad_fallo
        self.max_intentos = max_intentos
        self.latencia = latencia
        self.transacciones = {}
        self.procesados = set()
        self.rechazados = []
        self.dlq = []
        self.reintentos = 0
        self.duplicados = 0
        self.total_procesados = 0
        self.trabajadores = []
        self.disponible = False

    def iniciar(self):
        if self.trabajadores:
            return
        self.trabajadores = [asyncio.create_task(self._consumir(indice)) for indice in range(len(self.bus.colas))]
        self.disponible = True

    async def detener(self):
        self.disponible = False
        for tarea in self.trabajadores:
            tarea.cancel()
        await asyncio.gather(*self.trabajadores, return_exceptions=True)
        self.trabajadores = []

    async def caer(self, duracion, perder_colas=False):
        await self.detener()
        await asyncio.sleep(duracion)
        if perder_colas:
            for cola in self.bus.colas:
                while not cola.empty():
                    cola.get_nowait()
                    cola.task_done()
        self.iniciar()
        await self.reconstruir()

    async def reconstruir(self):
        if not self.bus.journal:
            return 0
        eventos = [evento for evento in self.bus.journal.pendientes() if evento.event_id not in self.procesados]
        for evento in eventos:
            await self.bus.recuperar(evento)
        return len(eventos)

    async def _consumir(self, indice):
        cola = self.bus.colas[indice]
        while True:
            evento = await cola.get()
            try:
                await self._procesar(evento)
            except asyncio.CancelledError:
                raise
            except FalloTemporal as error:
                evento.intentos += 1
                if evento.intentos < self.max_intentos:
                    self.reintentos += 1
                    await asyncio.sleep(min(0.2, 0.01 * (2 ** evento.intentos)))
                    await self.bus.recuperar(evento)
                else:
                    self.dlq.append((evento, str(error)))
            except ErrorNegocio as error:
                self._rechazar(evento, str(error))
            except Exception as error:
                evento.intentos += 1
                if evento.intentos < self.max_intentos:
                    self.reintentos += 1
                    await self.bus.recuperar(evento)
                else:
                    self.dlq.append((evento, repr(error)))
            finally:
                cola.task_done()

    def _confirmar(self, evento):
        self.procesados.add(evento.event_id)
        if self.bus.journal:
            self.bus.journal.confirmar(evento.event_id)

    def _rechazar(self, evento, motivo, marcar=True):
        self.rechazados.append((evento, motivo))
        if marcar:
            self._confirmar(evento)
        elif self.bus.journal:
            self.bus.journal.confirmar(evento.event_id)
        registrar(f"RECHAZADO {evento.tipo} [{evento.tx_id}]: {motivo}", True)

    async def _procesar(self, evento):
        if self.probabilidad_fallo and random.random() < self.probabilidad_fallo:
            raise FalloTemporal("fallo temporal de procesamiento")
        if not self.seguridad.verificar(evento):
            self._rechazar(evento, "firma invalida", marcar=False)
            return
        if evento.event_id in self.procesados:
            self.duplicados += 1
            if self.bus.journal:
                self.bus.journal.confirmar(evento.event_id)
            return
        rol = self.motor.roles.get(evento.tipo)
        if rol is None:
            raise ErrorNegocio("tipo de evento desconocido")
        transaccion = self.transacciones.get(evento.tx_id)
        if transaccion is None:
            if evento.tipo != self.motor.evento_inicial:
                raise ErrorNegocio("transaccion inexistente")
            valor = evento.datos.get("valor")
            vendedor = evento.datos.get("vendedor")
            if not isinstance(valor, int) or valor <= 0 or not vendedor:
                raise ErrorNegocio("datos de transaccion invalidos")
            transaccion = Transaccion(evento.tx_id, valor, evento.origen, vendedor)
            transaccion.cambiar_estado("INICIADA")
            self.transacciones[evento.tx_id] = transaccion
        if not self._autorizado(rol, transaccion, evento.origen):
            raise ErrorNegocio(f"origen no autorizado para el rol {rol}")
        if self.latencia:
            await asyncio.sleep(self.latencia)
        for manejador in self.motor.manejadores[evento.tipo]:
            await manejador(self, transaccion, evento)
        for regla in self.motor.reglas:
            await regla(self, transaccion)
        self._confirmar(evento)
        self.total_procesados += 1

    @staticmethod
    def _autorizado(rol, transaccion, origen):
        if rol == "comprador":
            return origen == transaccion.comprador
        if rol == "vendedor":
            return origen == transaccion.vendedor
        if rol == "pasarela":
            return origen == "PASARELA"
        return False

    def metricas(self):
        finalizadas = [tx for tx in self.transacciones.values() if tx.fin is not None]
        latencias = [tx.fin - tx.inicio for tx in finalizadas]
        return {
            "transacciones": len(self.transacciones),
            "finalizadas": len(finalizadas),
            "liberadas": sum(tx.dinero_liberado for tx in self.transacciones.values()),
            "reembolsadas": sum(tx.reembolsada for tx in self.transacciones.values()),
            "canceladas": sum(tx.cancelada for tx in self.transacciones.values()),
            "procesados": self.total_procesados,
            "reintentos": self.reintentos,
            "duplicados": self.duplicados,
            "rechazados": len(self.rechazados),
            "dlq": len(self.dlq),
            "latencia_promedio": sum(latencias) / len(latencias) if latencias else 0,
            "latencia_maxima": max(latencias, default=0),
        }
