import time

from core import ErrorNegocio, MotorReglas, registrar


def construir_motor():
    motor = MotorReglas()

    @motor.manejar("SOLICITUD_PAGO", "comprador", inicial=True)
    async def solicitud_pago(escrow, transaccion, evento):
        if transaccion.estado != "INICIADA":
            raise ErrorNegocio("la transaccion ya fue iniciada")
        await escrow.bus.notificar(
            "PASARELA",
            {"tipo": "COBRAR", "tx_id": transaccion.id, "valor": transaccion.valor},
        )

    @motor.manejar("PAGO_APROBADO", "pasarela")
    async def pago_aprobado(escrow, transaccion, evento):
        if transaccion.estado != "INICIADA":
            raise ErrorNegocio("el pago no puede aprobarse en el estado actual")
        transaccion.pago_confirmado = True
        transaccion.cambiar_estado("PAGO_RETENIDO")
        await escrow.bus.notificar(
            transaccion.vendedor,
            {"tipo": "ENVIAR_PRODUCTO", "tx_id": transaccion.id},
        )

    @motor.manejar("PRODUCTO_DESPACHADO", "vendedor")
    async def producto_despachado(escrow, transaccion, evento):
        if not transaccion.pago_confirmado:
            raise ErrorNegocio("no existe un pago retenido")
        transaccion.producto_despachado = True
        transaccion.cambiar_estado("PRODUCTO_DESPACHADO")
        await escrow.bus.notificar(
            transaccion.comprador,
            {"tipo": "PRODUCTO_EN_CAMINO", "tx_id": transaccion.id},
        )

    @motor.manejar("ENTREGA_CONFIRMADA", "comprador")
    async def entrega_confirmada(escrow, transaccion, evento):
        transaccion.entrega_confirmada = True
        transaccion.cambiar_estado("ENTREGA_CONFIRMADA")

    @motor.regla
    async def liberar_dinero(escrow, transaccion):
        if (
            transaccion.pago_confirmado
            and transaccion.producto_despachado
            and transaccion.entrega_confirmada
            and not transaccion.dinero_liberado
        ):
            transaccion.dinero_liberado = True
            transaccion.fin = time.perf_counter()
            transaccion.cambiar_estado("DINERO_LIBERADO")
            await escrow.bus.notificar(
                transaccion.vendedor,
                {"tipo": "PAGO_RECIBIDO", "tx_id": transaccion.id, "valor": transaccion.valor},
            )

    return motor
