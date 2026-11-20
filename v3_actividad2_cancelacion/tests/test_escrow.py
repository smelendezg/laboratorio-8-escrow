import tempfile
import unittest
from pathlib import Path

from core import Bus, Evento, Journal, Registro, Seguridad, ServicioEscrow
from reglas import construir_motor


class PruebasEscrow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Registro.visible = False
        self.seguridad = Seguridad()
        self.comprador = self.seguridad.registrar("COMPRADOR-1")
        self.vendedor = self.seguridad.registrar("VENDEDOR-1")
        self.pasarela = self.seguridad.registrar("PASARELA")
        self.bus = Bus(2)
        self.servicio = ServicioEscrow(self.bus, construir_motor(), self.seguridad)
        self.servicio.iniciar()

    async def asyncTearDown(self):
        await self.servicio.detener()

    async def iniciar(self, tx_id="TX-1"):
        evento = Evento(
            "SOLICITUD_PAGO",
            tx_id,
            datos={"valor": 500_000, "vendedor": "VENDEDOR-1"},
        )
        await self.bus.publicar(self.comprador.firmar(evento))
        await self.bus.vaciar()

    async def test_flujo_exitoso(self):
        await self.iniciar()
        await self.bus.publicar(self.pasarela.firmar(Evento("PAGO_APROBADO", "TX-1")))
        await self.bus.publicar(self.vendedor.firmar(Evento("PRODUCTO_DESPACHADO", "TX-1")))
        await self.bus.publicar(self.comprador.firmar(Evento("ENTREGA_CONFIRMADA", "TX-1")))
        await self.bus.vaciar()
        transaccion = self.servicio.transacciones["TX-1"]
        self.assertTrue(transaccion.dinero_liberado)
        self.assertEqual(transaccion.estado, "DINERO_LIBERADO")

    async def test_rechaza_entrega_sin_despacho(self):
        await self.iniciar()
        await self.bus.publicar(self.comprador.firmar(Evento("ENTREGA_CONFIRMADA", "TX-1")))
        await self.bus.vaciar()
        transaccion = self.servicio.transacciones["TX-1"]
        self.assertFalse(transaccion.entrega_confirmada)
        self.assertFalse(transaccion.dinero_liberado)
        self.assertEqual(len(self.servicio.rechazados), 1)

    async def test_cancelacion_antes_del_pago(self):
        await self.iniciar()
        evento = Evento("CANCELACION_SOLICITADA", "TX-1", datos={"motivo": "prueba"})
        await self.bus.publicar(self.comprador.firmar(evento))
        await self.bus.vaciar()
        transaccion = self.servicio.transacciones["TX-1"]
        self.assertTrue(transaccion.cancelada)
        self.assertEqual(transaccion.estado, "CANCELADA")

    async def test_reembolso(self):
        await self.iniciar()
        await self.bus.publicar(self.pasarela.firmar(Evento("PAGO_APROBADO", "TX-1")))
        await self.bus.vaciar()
        await self.bus.publicar(self.comprador.firmar(Evento("REEMBOLSO_SOLICITADO", "TX-1")))
        await self.bus.vaciar()
        await self.bus.publicar(self.pasarela.firmar(Evento("REEMBOLSO_COMPLETADO", "TX-1")))
        await self.bus.vaciar()
        transaccion = self.servicio.transacciones["TX-1"]
        self.assertTrue(transaccion.reembolsada)
        self.assertEqual(transaccion.estado, "REEMBOLSADA")

    async def test_evento_duplicado(self):
        evento = self.comprador.firmar(
            Evento(
                "SOLICITUD_PAGO",
                "TX-1",
                datos={"valor": 500_000, "vendedor": "VENDEDOR-1"},
            )
        )
        await self.bus.publicar(evento)
        await self.bus.vaciar()
        await self.bus.publicar(evento)
        await self.bus.vaciar()
        self.assertEqual(len(self.servicio.transacciones), 1)
        self.assertEqual(self.servicio.duplicados, 1)

    async def test_firma_invalida(self):
        await self.iniciar()
        evento = Evento("ENTREGA_CONFIRMADA", "TX-1", origen="COMPRADOR-1")
        await self.bus.publicar(evento)
        await self.bus.vaciar()
        self.assertEqual(len(self.servicio.rechazados), 1)
        self.assertFalse(self.servicio.transacciones["TX-1"].entrega_confirmada)


class PruebasJournal(unittest.TestCase):
    def test_conserva_eventos_al_reabrir(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "journal.jsonl"
            primero = Journal(ruta, reiniciar=True)
            primero.publicar(Evento("PRUEBA", "TX-1"))
            primero.cerrar()
            segundo = Journal(ruta)
            self.assertEqual(len(segundo.pendientes()), 1)
            segundo.cerrar()


if __name__ == "__main__":
    unittest.main()
