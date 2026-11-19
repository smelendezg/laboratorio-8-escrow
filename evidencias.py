import csv
import json
from html import escape
from pathlib import Path


CARPETA = Path(__file__).resolve().parent / "evidencias"
CARPETA.mkdir(parents=True, exist_ok=True)


def guardar_json(nombre, datos):
    ruta = CARPETA / f"{nombre}.json"
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


def guardar_transacciones(nombre, transacciones):
    ruta = CARPETA / f"{nombre}.csv"
    filas = [transaccion.resumen() for transaccion in transacciones]
    if not filas:
        ruta.write_text("", encoding="utf-8")
        return ruta
    with ruta.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]))
        escritor.writeheader()
        escritor.writerows(filas)
    return ruta


def grafica_barras(nombre, titulo, etiquetas, valores, unidad=""):
    ruta = CARPETA / f"{nombre}.svg"
    ancho = 900
    alto = 480
    margen_izquierdo = 80
    margen_inferior = 90
    area_ancho = ancho - margen_izquierdo - 40
    area_alto = alto - 90 - margen_inferior
    maximo = max(valores, default=1) or 1
    paso = area_ancho / max(len(valores), 1)
    barras = []
    for indice, (etiqueta, valor) in enumerate(zip(etiquetas, valores)):
        altura = area_alto * valor / maximo
        x = margen_izquierdo + indice * paso + paso * 0.15
        y = 70 + area_alto - altura
        ancho_barra = paso * 0.7
        barras.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{ancho_barra:.2f}" height="{altura:.2f}" fill="#2463a6" rx="3"/>'
        )
        barras.append(
            f'<text x="{x + ancho_barra / 2:.2f}" y="{y - 8:.2f}" text-anchor="middle" font-size="13">{valor:.3f}{escape(unidad)}</text>'
        )
        barras.append(
            f'<text x="{x + ancho_barra / 2:.2f}" y="{70 + area_alto + 24:.2f}" text-anchor="middle" font-size="12">{escape(str(etiqueta))}</text>'
        )
    contenido = "".join(barras)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" viewBox="0 0 {ancho} {alto}">
<rect width="100%" height="100%" fill="white"/>
<text x="{ancho / 2}" y="34" text-anchor="middle" font-family="Arial" font-size="22" font-weight="bold">{escape(titulo)}</text>
<line x1="{margen_izquierdo}" y1="70" x2="{margen_izquierdo}" y2="{70 + area_alto}" stroke="#333"/>
<line x1="{margen_izquierdo}" y1="{70 + area_alto}" x2="{ancho - 40}" y2="{70 + area_alto}" stroke="#333"/>
<g font-family="Arial" fill="#222">{contenido}</g>
</svg>'''
    ruta.write_text(svg, encoding="utf-8")
    return ruta
