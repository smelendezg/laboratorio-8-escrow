# Versión 4 – Actividad 3: diez transacciones simultáneas

Cambios respecto a la versión 3:

- `EscrowV1.py`: escenario `actividad3` con 10 compradores, 10 vendedores y
  10 transacciones de valores diferentes (125.000 a 1.100.000), 4 particiones,
  lanzadas con `asyncio.create_task` y esperadas con `asyncio.gather`. Genera
  `evidencias/actividad_3.csv` y la gráfica `actividad_3_latencias.svg`.

```bash
python3 EscrowV1.py actividad3
```
