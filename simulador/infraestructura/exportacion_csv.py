"""Exportación de trazas, métricas y resultados por proceso a CSV."""

import csv
from collections.abc import Iterable, Sequence
from io import StringIO
from pathlib import Path

from simulador.dominio.modelos import ResultadoSimulacion

COLUMNAS_TRAZA = ("algoritmo", "inicio", "fin", "duracion", "proceso", "id_cola")
COLUMNAS_RESULTADOS = (
    "algoritmo",
    "id_proceso",
    "id_cola",
    "tiempo_llegada",
    "rafaga",
    "tiempo_finalizacion",
    "tiempo_espera",
    "tiempo_retorno",
)
COLUMNAS_METRICAS = (
    "algoritmo",
    "promedio_espera",
    "promedio_retorno",
    "tiempo_cpu_ocupado",
    "tiempo_cpu_inactivo",
    "tiempo_total",
    "utilizacion_cpu",
)


def _generar_csv(
    columnas: Sequence[str],
    filas: Iterable[Sequence[object]],
) -> str:
    """Serializa una tabla con encabezado y saltos de línea estables."""

    buffer = StringIO(newline="")
    escritor = csv.writer(buffer, lineterminator="\n")
    escritor.writerow(columnas)
    escritor.writerows(filas)
    return buffer.getvalue()


def _exportar(contenido: str, ruta: str | Path) -> Path:
    """Escribe contenido UTF-8 sin traducción de saltos de línea."""

    ruta_destino = Path(ruta)
    with ruta_destino.open("w", encoding="utf-8", newline="") as archivo:
        archivo.write(contenido)
    return ruta_destino


def generar_csv_traza(resultado: ResultadoSimulacion) -> str:
    """Genera el CSV de segmentos en el orden cronológico de la traza."""

    filas = (
        (
            resultado.algoritmo.value,
            segmento.inicio,
            segmento.fin,
            segmento.duracion,
            segmento.etiqueta,
            segmento.id_cola or "",
        )
        for segmento in resultado.segmentos
    )
    return _generar_csv(COLUMNAS_TRAZA, filas)


def generar_csv_resultados(resultado: ResultadoSimulacion) -> str:
    """Genera el CSV con una fila por proceso terminado."""

    filas = (
        (
            resultado.algoritmo.value,
            item.id_proceso,
            item.id_cola or "",
            item.tiempo_llegada,
            item.rafaga,
            item.tiempo_finalizacion,
            item.tiempo_espera,
            item.tiempo_retorno,
        )
        for item in resultado.resultados
    )
    return _generar_csv(COLUMNAS_RESULTADOS, filas)


def generar_csv_metricas(resultado: ResultadoSimulacion) -> str:
    """Genera el CSV con las métricas globales de la ejecución."""

    fila = (
        resultado.algoritmo.value,
        resultado.promedio_espera,
        resultado.promedio_retorno,
        resultado.tiempo_cpu_ocupado,
        resultado.tiempo_cpu_inactivo,
        resultado.tiempo_total,
        resultado.utilizacion_cpu,
    )
    return _generar_csv(COLUMNAS_METRICAS, (fila,))


def exportar_traza(resultado: ResultadoSimulacion, ruta: str | Path) -> Path:
    """Escribe la traza en CSV y devuelve la ruta utilizada."""

    return _exportar(generar_csv_traza(resultado), ruta)


def exportar_resultados(resultado: ResultadoSimulacion, ruta: str | Path) -> Path:
    """Escribe los resultados por proceso en CSV y devuelve la ruta utilizada."""

    return _exportar(generar_csv_resultados(resultado), ruta)


def exportar_metricas(resultado: ResultadoSimulacion, ruta: str | Path) -> Path:
    """Escribe las métricas globales en CSV y devuelve la ruta utilizada."""

    return _exportar(generar_csv_metricas(resultado), ruta)
