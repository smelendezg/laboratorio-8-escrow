# Versión 2 – Actividad 1: atributos de calidad

Cambios respecto a la versión 1:

- `core.py`: `Evento` con `tx_id`, `event_id` y firma HMAC-SHA256; `Seguridad`;
  `Journal` (PUB/ACK en disco); `Bus` con colas particionadas por `tx_id` y
  buzones por participante; `MotorReglas`; `Transaccion`; `ServicioEscrow` con
  idempotencia, autorización por rol, reintentos con backoff y DLQ.
- `reglas.py`: flujo base registrado en el motor de reglas (solicitud de pago,
  pago aprobado, despacho, entrega y regla de liberación).
- `participantes.py`: comprador, vendedor y pasarela que reaccionan a
  notificaciones del ESCROW en lugar de tiempos fijos.
- `EscrowV1.py`: simulador configurable y un escenario por atributo.
- `evidencias.py`: guarda resultados JSON/CSV y gráficas SVG en `evidencias/`.

```bash
python3 EscrowV1.py rendimiento      # 1 vs 100 transacciones
python3 EscrowV1.py disponibilidad   # caída temporal del ESCROW + journal
python3 EscrowV1.py confiabilidad    # 25 % de fallos, reintentos y DLQ
python3 EscrowV1.py seguridad        # 3 confirmaciones falsas
python3 EscrowV1.py escalabilidad    # 1.000 compradores con 1–16 particiones
python3 EscrowV1.py mantenibilidad   # revisión manual y comisión del 3 %
python3 EscrowV1.py actividad1       # los seis anteriores
python3 -m unittest discover -s tests -v
```

En esta versión todavía no existen la cancelación ni el reembolso, y la
confirmación de entrega no valida que exista un despacho (se agrega en la v3).
