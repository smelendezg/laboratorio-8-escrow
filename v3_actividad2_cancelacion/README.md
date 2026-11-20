# Versión 3 – Actividad 2: cancelación, reembolso y validación del despacho

Cambios respecto a la versión 2:

- `reglas.py`: eventos `CANCELACION_SOLICITADA`, `REEMBOLSO_SOLICITADO` y
  `REEMBOLSO_COMPLETADO`; estados `CANCELADA`, `REEMBOLSO_PENDIENTE` y
  `REEMBOLSADA`. `ENTREGA_CONFIRMADA` se rechaza si no existe un despacho
  registrado y el despacho exige el estado `PAGO_RETENIDO`. La regla de
  liberación no actúa sobre transacciones canceladas o reembolsadas.
- `core.py`: `Transaccion` agrega `cancelada` y `reembolsada` (y métricas).
- `participantes.py`: la pasarela atiende `REEMBOLSAR`.
- `EscrowV1.py`: escenario `actividad2` (CANCEL-001, REFUND-001, INVALIDA-001).
- `tests/`: pruebas de cancelación, reembolso y entrega sin despacho.

```bash
python3 EscrowV1.py actividad2
python3 -m unittest discover -s tests -v
```
