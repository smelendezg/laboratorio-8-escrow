import asyncio
import random

from core import Evento, registrar


async def pausa(base, escala):
    await asyncio.sleep(base * escala * random.uniform(0.8, 1.2))


class Pasarela:
    def __init__(self, bus, credencial, escala=1.0):
        self.bus = bus
        self.credencial = credencial
        self.escala = escala
        self.tareas = set()

    async def ejecutar(self):
        while True:
            mensaje = await self.bus.recibir("PASARELA")
            tarea = asyncio.create_task(self._atender(mensaje))
            self.tareas.add(tarea)
            tarea.add_done_callback(self.tareas.discard)

    async def _atender(self, mensaje):
        if mensaje["tipo"] == "COBRAR":
            await pausa(0.6, self.escala)
            evento = self.credencial.firmar(Evento("PAGO_APROBADO", mensaje["tx_id"]))
            await self.bus.publicar(evento)
        elif mensaje["tipo"] == "REEMBOLSAR":
            await pausa(0.4, self.escala)
            evento = self.credencial.firmar(Evento("REEMBOLSO_COMPLETADO", mensaje["tx_id"]))
            await self.bus.publicar(evento)


class Vendedor:
    def __init__(self, bus, credencial, escala=1.0):
        self.bus = bus
        self.credencial = credencial
        self.escala = escala
        self.tareas = set()

    async def ejecutar(self):
        while True:
            mensaje = await self.bus.recibir(self.credencial.participante)
            if mensaje["tipo"] == "ENVIAR_PRODUCTO":
                tarea = asyncio.create_task(self._enviar(mensaje["tx_id"]))
                self.tareas.add(tarea)
                tarea.add_done_callback(self.tareas.discard)
            elif mensaje["tipo"] == "PAGO_RECIBIDO":
                registrar(
                    f"{self.credencial.participante}: pago recibido por ${mensaje['valor']:,}"
                )

    async def _enviar(self, tx_id):
        await pausa(0.5, self.escala)
        evento = self.credencial.firmar(Evento("PRODUCTO_DESPACHADO", tx_id))
        await self.bus.publicar(evento)


class Comprador:
    def __init__(self, bus, credencial, vendedor, valor, tx_id, escala=1.0):
        self.bus = bus
        self.credencial = credencial
        self.vendedor = vendedor
        self.valor = valor
        self.tx_id = tx_id
        self.escala = escala

    async def ejecutar(self):
        evento = Evento(
            "SOLICITUD_PAGO",
            self.tx_id,
            datos={"valor": self.valor, "vendedor": self.vendedor},
        )
        await self.bus.publicar(self.credencial.firmar(evento))
        while True:
            mensaje = await self.bus.recibir(self.credencial.participante)
            if mensaje["tipo"] == "PRODUCTO_EN_CAMINO" and mensaje["tx_id"] == self.tx_id:
                await pausa(0.7, self.escala)
                confirmacion = self.credencial.firmar(Evento("ENTREGA_CONFIRMADA", self.tx_id))
                await self.bus.publicar(confirmacion)
                return
