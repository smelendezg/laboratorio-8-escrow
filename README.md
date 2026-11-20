# Laboratorio 8 – Comunicación asincrónica (Sistema ESCROW)

Sarah Del Sol Meléndez Galindo, Laura Palacios Ochoa, Laura Natalia Olmos Parra.

El código está versionado por actividad. Cada carpeta es una versión completa
y ejecutable, y cada una corresponde a un commit con su etiqueta en Git.

| Versión | Carpeta | Tag | Contenido |
|---|---|---|---|
| 1 | `v1_original/` | `v1` | Código original del docente |
| 2 | `v2_actividad1_calidad/` | `v2` | Actividad 1: rendimiento, disponibilidad, confiabilidad, seguridad, escalabilidad y mantenibilidad |
| 3 | `v3_actividad2_cancelacion/` | `v3` | Actividad 2: cancelación, reembolso y rechazo de entrega sin despacho |
| 4 | `v4_actividad3_concurrencia/` | `v4` | Actividad 3: 10 compradores, 10 vendedores y 10 transacciones |
| 5 | `v5_actividad4_fallos/` | `v5` | Actividad 4: pasarela, vendedor y comprador que fallan; eventos duplicados |
| 6 | `v6_actividad5_rabbitmq/` | `v6` | Actividad 5: RabbitMQ (versión final) |

Cada carpeta tiene su propio `README.md` con los cambios respecto a la versión
anterior y los comandos para ejecutarla. Las versiones 1 a 5 solo necesitan
Python 3.9 o superior, la 6 requiere además RabbitMQ y `aio-pika`.

Como cada versión es una carpeta completa, los cambios entre dos versiones
se pueden comparar entre carpetas, por ejemplo:

```bash
diff -r v2_actividad1_calidad v3_actividad2_cancelacion
```

## Evidencias

Al ejecutar los escenarios de las versiones 2 a 6 se crea automáticamente la carpeta `evidencias/` con los resultados (JSON, CSV, journals y gráficas SVG).

## Nota sobre `escrow_v2.py`

En las versiones 2 a 6, `escrow_v2.py` es solo un punto de entrada alternativo que llama a `EscrowV1.main()`.
