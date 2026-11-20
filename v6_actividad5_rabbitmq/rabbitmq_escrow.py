import asyncio
import json
import os
import uuid
from dataclasses import dataclass


try:
    import aio_pika
except ImportError:
    aio_pika = None


EXCHANGE = "escrow.eventos"


@dataclass
class Estado:
    tx_id: str
    valor: int
    pago: bool = False
    despacho: bool = False
    entrega: bool = False
    liberado: bool = False
    estado: str = "INICIADA"


def mensaje(tipo, tx_id, datos=None, event_id=None):
    return {
        "tipo": tipo,
        "tx_id": tx_id,
        "datos": datos or {},
        "event_id": event_id or uuid.uuid4().hex,
    }


async def publicar(exchange, ruta, contenido):
    cuerpo = json.dumps(contenido).encode("utf-8")
    await exchange.publish(
        aio_pika.Message(
            cuerpo,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            correlation_id=contenido["tx_id"],
            message_id=contenido["event_id"],
        ),
        routing_key=ruta,
    )


async def ejecutar():
    if aio_pika is None:
        raise SystemExit("Instala aio-pika con: python -m pip install aio-pika")
    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost/")
    conexion = await aio_pika.connect_robust(url)
    canal = await conexion.channel()
    await canal.set_qos(prefetch_count=20)
    exchange = await canal.declare_exchange(EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)
    dlx = await canal.declare_exchange("escrow.dlx", aio_pika.ExchangeType.DIRECT, durable=True)
    cola_dlq = await canal.declare_queue("escrow.dlq", durable=True)
    await cola_dlq.bind(dlx, "fallidos")
    argumentos = {"x-dead-letter-exchange": "escrow.dlx", "x-dead-letter-routing-key": "fallidos"}
    colas = {}
    for nombre in ["escrow", "pasarela", "vendedor", "comprador"]:
        cola = await canal.declare_queue(f"escrow.{nombre}", durable=True, arguments=argumentos)
        await cola.bind(exchange, nombre)
        colas[nombre] = cola
    estado = Estado("RABBIT-001", 650_000)
    procesados = set()
    finalizado = asyncio.Event()

    async def consumidor_escrow(mensaje_rabbit):
        async with mensaje_rabbit.process(requeue=False):
            evento = json.loads(mensaje_rabbit.body)
            if evento["event_id"] in procesados:
                return
            procesados.add(evento["event_id"])
            tipo = evento["tipo"]
            if tipo == "SOLICITUD_PAGO":
                await publicar(exchange, "pasarela", mensaje("COBRAR", estado.tx_id, {"valor": estado.valor}))
            elif tipo == "PAGO_APROBADO":
                estado.pago = True
                estado.estado = "PAGO_RETENIDO"
                await publicar(exchange, "vendedor", mensaje("ENVIAR_PRODUCTO", estado.tx_id))
            elif tipo == "PRODUCTO_DESPACHADO":
                if not estado.pago:
                    raise ValueError("No existe pago retenido")
                estado.despacho = True
                estado.estado = "PRODUCTO_DESPACHADO"
                await publicar(exchange, "comprador", mensaje("PRODUCTO_EN_CAMINO", estado.tx_id))
            elif tipo == "ENTREGA_CONFIRMADA":
                if not estado.despacho:
                    raise ValueError("No existe despacho registrado")
                estado.entrega = True
                estado.estado = "ENTREGA_CONFIRMADA"
            if estado.pago and estado.despacho and estado.entrega and not estado.liberado:
                estado.liberado = True
                estado.estado = "DINERO_LIBERADO"
                finalizado.set()

    async def consumidor_pasarela(mensaje_rabbit):
        async with mensaje_rabbit.process(requeue=False):
            evento = json.loads(mensaje_rabbit.body)
            if evento["tipo"] == "COBRAR":
                await publicar(exchange, "escrow", mensaje("PAGO_APROBADO", evento["tx_id"]))

    async def consumidor_vendedor(mensaje_rabbit):
        async with mensaje_rabbit.process(requeue=False):
            evento = json.loads(mensaje_rabbit.body)
            if evento["tipo"] == "ENVIAR_PRODUCTO":
                await publicar(exchange, "escrow", mensaje("PRODUCTO_DESPACHADO", evento["tx_id"]))

    async def consumidor_comprador(mensaje_rabbit):
        async with mensaje_rabbit.process(requeue=False):
            evento = json.loads(mensaje_rabbit.body)
            if evento["tipo"] == "PRODUCTO_EN_CAMINO":
                await publicar(exchange, "escrow", mensaje("ENTREGA_CONFIRMADA", evento["tx_id"]))

    etiquetas = [
        await colas["escrow"].consume(consumidor_escrow),
        await colas["pasarela"].consume(consumidor_pasarela),
        await colas["vendedor"].consume(consumidor_vendedor),
        await colas["comprador"].consume(consumidor_comprador),
    ]
    await publicar(
        exchange,
        "escrow",
        mensaje("SOLICITUD_PAGO", estado.tx_id, {"valor": estado.valor}),
    )
    try:
        await asyncio.wait_for(finalizado.wait(), 15)
    finally:
        for cola, etiqueta in zip(colas.values(), etiquetas):
            await cola.cancel(etiqueta)
        await conexion.close()
    print(json.dumps(estado.__dict__, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(ejecutar())
