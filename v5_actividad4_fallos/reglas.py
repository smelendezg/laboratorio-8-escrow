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
        if transaccion.estado != "PAGO_RETENIDO":
            raise ErrorNegocio("el producto no puede despacharse en el estado actual")
        transaccion.producto_despachado = True
        transaccion.cambiar_estado("PRODUCTO_DESPACHADO")
        await escrow.bus.notificar(
            transaccion.comprador,
            {"tipo": "PRODUCTO_EN_CAMINO", "tx_id": transaccion.id},
        )

    @motor.manejar("ENTREGA_CONFIRMADA", "comprador")
    async def entrega_confirmada(escrow, transaccion, evento):
        if not transaccion.producto_despachado:
            raise ErrorNegocio("no existe un despacho registrado")
        if transaccion.estado != "PRODUCTO_DESPACHADO":
            raise ErrorNegocio("la entrega no puede confirmarse en el estado actual")
        transaccion.entrega_confirmada = True
        transaccion.cambiar_estado("ENTREGA_CONFIRMADA")

    @motor.manejar("CANCELACION_SOLICITADA", "comprador")
    async def cancelacion(escrow, transaccion, evento):
        if transaccion.dinero_liberado:
            raise ErrorNegocio("no se puede cancelar despues de liberar el dinero")
        if transaccion.producto_despachado:
            raise ErrorNegocio("una transaccion despachada debe pasar a disputa")
        if transaccion.estado in {"CANCELADA", "REEMBOLSO_PENDIENTE", "REEMBOLSADA"}:
            raise ErrorNegocio("la transaccion ya esta cerrada")
        motivo = evento.datos.get("motivo", "cancelacion solicitada por el comprador")
        if transaccion.pago_confirmado:
            transaccion.cambiar_estado("REEMBOLSO_PENDIENTE", motivo)
            await escrow.bus.notificar(
                "PASARELA",
                {"tipo": "REEMBOLSAR", "tx_id": transaccion.id, "valor": transaccion.valor},
            )
        else:
            transaccion.cancelada = True
            transaccion.fin = time.perf_counter()
            transaccion.cambiar_estado("CANCELADA", motivo)

    @motor.manejar("REEMBOLSO_SOLICITADO", "comprador")
    async def solicitar_reembolso(escrow, transaccion, evento):
        if not transaccion.pago_confirmado:
            raise ErrorNegocio("no existe un pago para reembolsar")
        if transaccion.dinero_liberado:
            raise ErrorNegocio("el dinero ya fue liberado")
        if transaccion.reembolsada or transaccion.estado == "REEMBOLSO_PENDIENTE":
            raise ErrorNegocio("el reembolso ya fue solicitado")
        motivo = evento.datos.get("motivo", "reembolso solicitado por el comprador")
        transaccion.cambiar_estado("REEMBOLSO_PENDIENTE", motivo)
        await escrow.bus.notificar(
            "PASARELA",
            {"tipo": "REEMBOLSAR", "tx_id": transaccion.id, "valor": transaccion.valor},
        )

    @motor.manejar("REEMBOLSO_COMPLETADO", "pasarela")
    async def completar_reembolso(escrow, transaccion, evento):
        if transaccion.estado != "REEMBOLSO_PENDIENTE":
            raise ErrorNegocio("no existe un reembolso pendiente")
        transaccion.reembolsada = True
        transaccion.cancelada = True
        transaccion.fin = time.perf_counter()
        transaccion.cambiar_estado("REEMBOLSADA", transaccion.motivo)
        await escrow.bus.notificar(
            transaccion.comprador,
            {"tipo": "DINERO_REEMBOLSADO", "tx_id": transaccion.id, "valor": transaccion.valor},
        )

    @motor.manejar("DISPUTA_ABIERTA", "escrow")
    async def abrir_disputa(escrow, transaccion, evento):
        if transaccion.dinero_liberado or transaccion.reembolsada:
            raise ErrorNegocio("una transaccion cerrada no puede entrar en disputa")
        transaccion.cambiar_estado("EN_DISPUTA", evento.datos.get("motivo", "tiempo de espera agotado"))

    @motor.regla
    async def liberar_dinero(escrow, transaccion):
        if (
            transaccion.pago_confirmado
            and transaccion.producto_despachado
            and transaccion.entrega_confirmada
            and not transaccion.dinero_liberado
            and not transaccion.cancelada
            and not transaccion.reembolsada
        ):
            transaccion.dinero_liberado = True
            transaccion.fin = time.perf_counter()
            transaccion.cambiar_estado("DINERO_LIBERADO")
            await escrow.bus.notificar(
                transaccion.vendedor,
                {"tipo": "PAGO_RECIBIDO", "tx_id": transaccion.id, "valor": transaccion.valor},
            )

    return motor
