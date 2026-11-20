import argparse
import asyncio
import json
import time

from core import Bus, Evento, Journal, Registro, Seguridad, ServicioEscrow, registrar
from evidencias import CARPETA, grafica_barras, guardar_json, guardar_transacciones
from participantes import Comprador, Pasarela, Vendedor
from reglas import construir_motor


def percentil(valores, porcentaje):
    if not valores:
        return 0
    ordenados = sorted(valores)
    posicion = round((porcentaje / 100) * (len(ordenados) - 1))
    return ordenados[posicion]


async def simular(
    nombre,
    cantidad,
    particiones=1,
    escala=0.05,
    valores=None,
    vendedores=None,
    usar_journal=True,
    probabilidad_fallo=0,
    max_intentos=3,
    latencia=0,
    caida=None,
    limite=10,
    motor=None,
):
    Registro.visible = False
    Registro.inicio = time.perf_counter()
    ruta_journal = CARPETA / "journals" / f"{nombre}.jsonl"
    journal = Journal(ruta_journal, reiniciar=True) if usar_journal else None
    bus = Bus(particiones, journal)
    seguridad = Seguridad()
    credencial_pasarela = seguridad.registrar("PASARELA")
    total_vendedores = vendedores or cantidad
    credenciales_vendedores = [
        seguridad.registrar(f"VENDEDOR-{indice + 1}") for indice in range(total_vendedores)
    ]
    servicio = ServicioEscrow(
        bus,
        motor or construir_motor(),
        seguridad,
        probabilidad_fallo=probabilidad_fallo,
        max_intentos=max_intentos,
        latencia=latencia,
    )
    servicio.iniciar()
    pasarela = Pasarela(bus, credencial_pasarela, escala)
    objetos_vendedores = [
        Vendedor(bus, credencial, escala) for credencial in credenciales_vendedores
    ]
    tareas_servicio = [asyncio.create_task(pasarela.ejecutar())]
    tareas_servicio.extend(
        asyncio.create_task(vendedor.ejecutar()) for vendedor in objetos_vendedores
    )
    muestras = []

    async def medir():
        while True:
            muestras.append(
                {
                    "tiempo": time.perf_counter() - Registro.inicio,
                    "cola": bus.profundidad(),
                    "disponible": servicio.disponible,
                }
            )
            await asyncio.sleep(0.01)

    tarea_medicion = asyncio.create_task(medir())
    tarea_caida = None
    if caida:
        inicio_caida, duracion, perder_colas = caida

        async def provocar_caida():
            await asyncio.sleep(inicio_caida)
            await servicio.caer(duracion, perder_colas)

        tarea_caida = asyncio.create_task(provocar_caida())
    tareas_compradores = []
    credenciales_compradores = []
    for indice in range(cantidad):
        credencial = seguridad.registrar(f"COMPRADOR-{indice + 1}")
        credenciales_compradores.append(credencial)
        valor = valores[indice] if valores else 100_000 + (indice * 25_000)
        vendedor = credenciales_vendedores[indice % total_vendedores].participante
        comprador = Comprador(
            bus,
            credencial,
            vendedor,
            valor,
            f"ESCROW-{indice + 1:04d}",
            escala,
        )
        tareas_compradores.append(asyncio.create_task(comprador.ejecutar()))
    inicio = time.perf_counter()
    timeout = False
    try:
        await asyncio.wait_for(asyncio.gather(*tareas_compradores), limite)
        if tarea_caida:
            await asyncio.wait_for(tarea_caida, limite)
        await asyncio.wait_for(bus.vaciar(), limite)
        await asyncio.sleep(0.02)
        await asyncio.wait_for(bus.vaciar(), limite)
    except asyncio.TimeoutError:
        timeout = True
    duracion = time.perf_counter() - inicio
    tarea_medicion.cancel()
    for tarea in tareas_compradores:
        tarea.cancel()
    if tarea_caida:
        tarea_caida.cancel()
    await servicio.detener()
    for tarea in tareas_servicio:
        tarea.cancel()
    for objeto in [pasarela, *objetos_vendedores]:
        for tarea in objeto.tareas:
            tarea.cancel()
    await asyncio.gather(
        tarea_medicion,
        *tareas_compradores,
        *tareas_servicio,
        *list(pasarela.tareas),
        *(tarea for vendedor in objetos_vendedores for tarea in vendedor.tareas),
        return_exceptions=True,
    )
    if journal:
        journal.cerrar()
    transacciones = list(servicio.transacciones.values())
    metricas = servicio.metricas()
    latencias = [tx.fin - tx.inicio for tx in transacciones if tx.fin]
    metricas.update(
        {
            "nombre": nombre,
            "solicitadas": cantidad,
            "particiones": particiones,
            "duracion": duracion,
            "timeout": timeout,
            "throughput": servicio.total_procesados / duracion if duracion else 0,
            "p95": percentil(latencias, 95),
            "cola_maxima": max((muestra["cola"] for muestra in muestras), default=0),
        }
    )
    return {
        "metricas": metricas,
        "transacciones": transacciones,
        "muestras": muestras,
        "servicio": servicio,
        "bus": bus,
        "seguridad": seguridad,
        "credenciales_compradores": credenciales_compradores,
        "credenciales_vendedores": credenciales_vendedores,
        "credencial_pasarela": credencial_pasarela,
    }


def mostrar(titulo, resultado):
    print(f"\n{titulo}")
    print(json.dumps(resultado["metricas"], indent=2, ensure_ascii=False))


def guardar_resultado(nombre, resultado):
    metricas = resultado["metricas"]
    guardar_json(nombre, metricas)
    guardar_transacciones(nombre, resultado["transacciones"])


async def actividad_rendimiento():
    base = await simular("rendimiento_1", 1, escala=0.05)
    carga = await simular("rendimiento_100", 100, escala=0.05)
    mostrar("Rendimiento con 1 transaccion", base)
    mostrar("Rendimiento con 100 transacciones", carga)
    guardar_resultado("rendimiento_1", base)
    guardar_resultado("rendimiento_100", carga)
    grafica_barras(
        "rendimiento_comparacion",
        "Tiempo total por carga",
        ["1 transaccion", "100 transacciones"],
        [base["metricas"]["duracion"], carga["metricas"]["duracion"]],
        "s",
    )
    return {"una": base["metricas"], "cien": carga["metricas"]}


async def actividad_disponibilidad():
    resultado = await simular(
        "disponibilidad",
        20,
        particiones=4,
        escala=0.15,
        caida=(0.03, 0.15, True),
        limite=5,
    )
    mostrar("Disponibilidad con caida y recuperacion", resultado)
    guardar_resultado("disponibilidad", resultado)
    guardar_json("disponibilidad_muestras", resultado["muestras"])
    return resultado["metricas"]


async def actividad_confiabilidad():
    resultado = await simular(
        "confiabilidad",
        50,
        particiones=4,
        escala=0.04,
        probabilidad_fallo=0.25,
        max_intentos=6,
        limite=8,
    )
    mostrar("Confiabilidad con fallos temporales", resultado)
    guardar_resultado("confiabilidad", resultado)
    return resultado["metricas"]


async def actividad_seguridad():
    Registro.visible = False
    bus = Bus(1)
    seguridad = Seguridad()
    comprador = seguridad.registrar("COMPRADOR-1")
    vendedor = seguridad.registrar("VENDEDOR-1")
    pasarela = seguridad.registrar("PASARELA")
    intruso = seguridad.registrar("COMPRADOR-INTRUSO")
    servicio = ServicioEscrow(bus, construir_motor(), seguridad)
    servicio.iniciar()
    inicio = comprador.firmar(
        Evento(
            "SOLICITUD_PAGO",
            "SEG-001",
            datos={"valor": 800_000, "vendedor": vendedor.participante},
        )
    )
    await bus.publicar(inicio)
    await bus.vaciar()
    await bus.publicar(pasarela.firmar(Evento("PAGO_APROBADO", "SEG-001")))
    await bus.vaciar()
    await bus.publicar(Evento("ENTREGA_CONFIRMADA", "SEG-001", origen="COMPRADOR-1"))
    await bus.publicar(intruso.firmar(Evento("ENTREGA_CONFIRMADA", "SEG-001")))
    alterado = comprador.firmar(Evento("ENTREGA_CONFIRMADA", "SEG-001"))
    alterado.datos["forzado"] = True
    await bus.publicar(alterado)
    await bus.vaciar()
    estado = servicio.transacciones["SEG-001"].resumen()
    resultado = {
        "ataques_rechazados": len(servicio.rechazados),
        "dinero_liberado": estado["dinero_liberado"],
        "estado": estado["estado"],
        "motivos": [motivo for evento, motivo in servicio.rechazados],
    }
    print("\nSeguridad")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    guardar_json("seguridad", resultado)
    await servicio.detener()
    return resultado


async def actividad_escalabilidad():
    resultados = []
    for particiones in [1, 2, 4, 8, 16]:
        resultado = await simular(
            f"escalabilidad_{particiones}",
            1000,
            particiones=particiones,
            vendedores=50,
            escala=0.02,
            latencia=0.0005,
            limite=20,
        )
        resultados.append(resultado)
        mostrar(f"Escalabilidad con {particiones} particiones", resultado)
        guardar_resultado(f"escalabilidad_{particiones}", resultado)
    grafica_barras(
        "escalabilidad_throughput",
        "Throughput para 1.000 compradores",
        [str(resultado["metricas"]["particiones"]) for resultado in resultados],
        [resultado["metricas"]["throughput"] for resultado in resultados],
        " ev/s",
    )
    return [resultado["metricas"] for resultado in resultados]


async def actividad_mantenibilidad():
    motor = construir_motor()

    @motor.manejar("SOLICITUD_PAGO", "comprador")
    async def validar_monto(escrow, transaccion, evento):
        transaccion.revision_manual = transaccion.valor >= 5_000_000

    @motor.regla
    async def calcular_comision(escrow, transaccion):
        if transaccion.dinero_liberado and not hasattr(transaccion, "comision"):
            transaccion.comision = round(transaccion.valor * 0.03)

    resultado = await simular(
        "mantenibilidad",
        2,
        valores=[750_000, 6_500_000],
        motor=motor,
    )
    datos = {
        "metricas": resultado["metricas"],
        "reglas_agregadas": ["revision manual desde $5.000.000", "comision del 3%"],
        "resultados": [
            {
                **tx.resumen(),
                "revision_manual": getattr(tx, "revision_manual", False),
                "comision": getattr(tx, "comision", 0),
            }
            for tx in resultado["transacciones"]
        ],
    }
    print("\nMantenibilidad")
    print(json.dumps(datos, indent=2, ensure_ascii=False))
    guardar_json("mantenibilidad", datos)
    return datos


async def actividad_1():
    resultado = {
        "rendimiento": await actividad_rendimiento(),
        "disponibilidad": await actividad_disponibilidad(),
        "confiabilidad": await actividad_confiabilidad(),
        "seguridad": await actividad_seguridad(),
        "escalabilidad": await actividad_escalabilidad(),
        "mantenibilidad": await actividad_mantenibilidad(),
    }
    guardar_json("actividad_1_resumen", resultado)


async def todo_local():
    await actividad_1()
    print(f"\nEvidencias guardadas en {CARPETA}")


async def ejecutar(modo):
    opciones = {
        "rendimiento": actividad_rendimiento,
        "disponibilidad": actividad_disponibilidad,
        "confiabilidad": actividad_confiabilidad,
        "seguridad": actividad_seguridad,
        "escalabilidad": actividad_escalabilidad,
        "mantenibilidad": actividad_mantenibilidad,
        "actividad1": actividad_1,
        "todo": todo_local,
    }
    await opciones[modo]()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "modo",
        nargs="?",
        default="todo",
        choices=[
            "rendimiento",
            "disponibilidad",
            "confiabilidad",
            "seguridad",
            "escalabilidad",
            "mantenibilidad",
            "actividad1",
            "todo",
        ],
    )
    argumentos = parser.parse_args()
    asyncio.run(ejecutar(argumentos.modo))


if __name__ == "__main__":
    main()
