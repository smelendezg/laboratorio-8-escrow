# Sistema ESCROW asincrónico

La solución parte del ejemplo original y cubre las cinco actividades del laboratorio. El modo local funciona únicamente con la biblioteca estándar de Python y genera evidencias en `evidencias/`.

## Requisitos

- Python 3.9 o superior.
- RabbitMQ y `aio-pika` únicamente para la actividad 5.

## Ejecución local

```bash
python3 EscrowV1.py rendimiento
python3 EscrowV1.py disponibilidad
python3 EscrowV1.py confiabilidad
python3 EscrowV1.py seguridad
python3 EscrowV1.py escalabilidad
python3 EscrowV1.py mantenibilidad
python3 EscrowV1.py actividad1
python3 EscrowV1.py actividad2
python3 EscrowV1.py actividad3
python3 EscrowV1.py actividad4
python3 EscrowV1.py todo
```

`todo` ejecuta las actividades 1 a 4. La actividad 5 se ejecuta aparte porque requiere un broker RabbitMQ.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

## RabbitMQ

Instalar la dependencia:

```bash
python3 -m pip install -r requirements.txt
```

Iniciar RabbitMQ con Docker:

```bash
docker run -d --name rabbitmq-escrow -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

En macOS también se puede iniciar con Homebrew:

```bash
brew install rabbitmq
brew services start rabbitmq
```

Ejecutar la actividad distribuida:

```bash
python3 rabbitmq_escrow.py
```

Para un servidor diferente:

```bash
RABBITMQ_URL=amqp://usuario:clave@servidor/ python3 rabbitmq_escrow.py
```

## Evidencias

Cada escenario produce archivos JSON y CSV. Los escenarios que requieren comparación visual también producen SVG. Estos archivos se pueden insertar directamente en el informe Word.

## Organización

- `EscrowV1.py`: escenarios locales y actividades 1 a 4.
- `core.py`: eventos, seguridad, journal, bus, transacciones y servicio ESCROW.
- `participantes.py`: comprador, vendedor y pasarela.
- `reglas.py`: reglas y transiciones de negocio.
- `evidencias.py`: generación de resultados y gráficas.
- `rabbitmq_escrow.py`: actividad 5 con mensajería distribuida.
- `tests/`: pruebas automatizadas.
