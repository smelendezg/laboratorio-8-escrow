import asyncio
from datetime import datetime

# -----------------------------------------
# COLA DE MENSAJES
# -----------------------------------------

cola_eventos = asyncio.Queue()

# -----------------------------------------
# ESTADO DE LA TRANSACCION
# -----------------------------------------

transaccion = {
    "id": "ESCROW-001",
    "valor": 500000,
    "pago_confirmado": False,
    "producto_despachado": False,
    "entrega_confirmada": False,
    "dinero_liberado": False
}

def registrar(mensaje):
    hora = datetime.now().strftime("%H:%M:%S")
    print(f"[{hora}] {mensaje}")


# -----------------------------------------
# PARTICIPANTE: COMPRADOR
# -----------------------------------------

async def comprador():

    registrar("COMPRADOR: Iniciando transaccion")
    await asyncio.sleep(1)
    registrar("COMPRADOR: Realizando pago")
    await cola_eventos.put({
        "tipo": "SOLICITUD_PAGO",
        "origen": "COMPRADOR"
    })

    # Espera simulada de recepción del producto
    await asyncio.sleep(5)
    registrar("COMPRADOR: Producto recibido")
    await cola_eventos.put({
        "tipo": "ENTREGA_CONFIRMADA",
        "origen": "COMPRADOR"
    })

# -----------------------------------------
# PARTICIPANTE: PASARELA DE PAGO
# -----------------------------------------

async def pasarela_pago():

    await asyncio.sleep(2)
    registrar("PASARELA: Pago aprobado")
    await cola_eventos.put({
        "tipo": "PAGO_APROBADO",
        "origen": "PASARELA"
    })

# -----------------------------------------
# PARTICIPANTE: VENDEDOR
# -----------------------------------------

async def vendedor():

    await asyncio.sleep(3)
    registrar("VENDEDOR: Preparando despacho")
    await cola_eventos.put({
        "tipo": "PRODUCTO_DESPACHADO",
        "origen": "VENDEDOR"
    })

# -----------------------------------------
# SERVICIO ESCROW
# -----------------------------------------

async def servicio_escrow():

    while True:

        evento = await cola_eventos.get()
        tipo = evento["tipo"]
        registrar(
            f"ESCROW: Procesando evento {tipo}"
        )
        if tipo == "SOLICITUD_PAGO":
            registrar("ESCROW: Solicitud de pago recibida")
        elif tipo == "PAGO_APROBADO":
            transaccion["pago_confirmado"] = True
            registrar(
                "ESCROW: Dinero retenido en garantia"
            )

        elif tipo == "PRODUCTO_DESPACHADO":

            transaccion["producto_despachado"] = True
            registrar(
                "ESCROW: Despacho registrado"
            )

        elif tipo == "ENTREGA_CONFIRMADA":

            transaccion["entrega_confirmada"] = True
            registrar(
                "ESCROW: Entrega confirmada"
            )

        # Validacion de las reglas de negocio

        if (
            transaccion["pago_confirmado"]
            and transaccion["producto_despachado"]
            and transaccion["entrega_confirmada"]
            and not transaccion["dinero_liberado"]
        ):

            transaccion["dinero_liberado"] = True
            registrar(
                "ESCROW: DINERO LIBERADO AL VENDEDOR"
            )
            registrar(
                f"Valor liberado: ${transaccion['valor']:,}"
            )

        cola_eventos.task_done()

# -----------------------------------------
# PROGRAMA PRINCIPAL
# -----------------------------------------

async def main():

    registrar("INICIANDO SISTEMA ESCROW")

    # Consumidor de mensajes
    tarea_escrow = asyncio.create_task(
        servicio_escrow()
    )

    # Participantes independientes
    tareas = [
        asyncio.create_task(comprador()),
        asyncio.create_task(pasarela_pago()),
        asyncio.create_task(vendedor())
    ]

    # Esperar a que los participantes terminen
    await asyncio.gather(*tareas)

    # Esperar a que se procesen todos los eventos
    await cola_eventos.join()

    registrar("RESUMEN DE LA TRANSACCION")

    print(transaccion)

    # Finalizar consumidor
    tarea_escrow.cancel()

    try:
        await tarea_escrow
    except asyncio.CancelledError:
        pass


# -----------------------------------------
# EJECUCION
# -----------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
