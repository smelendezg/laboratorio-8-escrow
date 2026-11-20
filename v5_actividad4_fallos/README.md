# Versión 5 – Actividad 4: análisis de fallos

Cambios respecto a la versión 4:

- `participantes.py`: opciones para simular fallos (`responder` y `reembolsar`
  en la pasarela, `despachar` en el vendedor, `confirmar` en el comprador).
- `reglas.py`: evento `DISPUTA_ABIERTA` (rol `escrow`) y estado `EN_DISPUTA`.
- `core.py`: el ESCROW puede emitir eventos propios (rol `escrow`).
- `EscrowV1.py`: escenario `actividad4` con pasarela que no responde, vendedor
  que no despacha, comprador que no confirma y evento duplicado, junto con los
  mecanismos de recuperación propuestos.

```bash
python3 EscrowV1.py actividad4
python3 EscrowV1.py todo        # actividades 1 a 4
```
