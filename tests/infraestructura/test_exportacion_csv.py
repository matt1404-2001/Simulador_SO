"""Pruebas de la exportación de resultados a CSV."""

import csv
from io import StringIO
from pathlib import Path

import pytest

from simulador.aplicacion import ejecutar_algoritmo
from simulador.dominio import Algoritmo, ResultadoSimulacion
from simulador.infraestructura import (
    COLUMNAS_METRICAS,
    COLUMNAS_RESULTADOS,
    COLUMNAS_TRAZA,
    exportar_metricas,
    exportar_resultados,
    exportar_traza,
    generar_csv_metricas,
    generar_csv_resultados,
    generar_csv_traza,
)
from tests.dominio.ayudas import crear_proceso


@pytest.fixture
def resultado() -> ResultadoSimulacion:
    """Ejecuta una carga pequeña que produce un tramo IDLE."""

    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P002", 5, 1, orden_ingreso=1),
    )
    return ejecutar_algoritmo(procesos, Algoritmo.FIFO)


def _leer(contenido: str) -> tuple[list[str], list[dict[str, str]]]:
    """Devuelve el encabezado y las filas de un CSV en memoria."""

    lector = csv.DictReader(StringIO(contenido))
    filas = list(lector)
    return list(lector.fieldnames or ()), filas


def test_traza_exportada_tiene_encabezado_y_sigue_la_traza(
    resultado: ResultadoSimulacion,
) -> None:
    encabezado, filas = _leer(generar_csv_traza(resultado))

    assert encabezado == list(COLUMNAS_TRAZA)
    assert [
        (
            fila["proceso"],
            int(fila["inicio"]),
            int(fila["fin"]),
            int(fila["duracion"]),
            fila["id_cola"],
        )
        for fila in filas
    ] == [
        ("P001", 0, 2, 2, "normal"),
        ("IDLE", 2, 5, 3, ""),
        ("P002", 5, 6, 1, "normal"),
    ]
    assert all(fila["algoritmo"] == "FIFO" for fila in filas)


def test_resultados_exportados_coinciden_con_los_procesos(
    resultado: ResultadoSimulacion,
) -> None:
    encabezado, filas = _leer(generar_csv_resultados(resultado))

    assert encabezado == list(COLUMNAS_RESULTADOS)
    assert [fila["id_proceso"] for fila in filas] == ["P001", "P002"]
    assert [fila["id_cola"] for fila in filas] == ["normal", "normal"]
    assert [int(fila["tiempo_finalizacion"]) for fila in filas] == [2, 6]
    assert [float(fila["tiempo_espera"]) for fila in filas] == [0, 0]
    assert [float(fila["tiempo_retorno"]) for fila in filas] == [2, 1]


def test_metricas_exportadas_coinciden_con_el_resultado(
    resultado: ResultadoSimulacion,
) -> None:
    encabezado, filas = _leer(generar_csv_metricas(resultado))

    assert encabezado == list(COLUMNAS_METRICAS)
    assert len(filas) == 1
    fila = filas[0]
    assert fila["algoritmo"] == "FIFO"
    assert float(fila["promedio_espera"]) == pytest.approx(resultado.promedio_espera)
    assert float(fila["promedio_retorno"]) == pytest.approx(resultado.promedio_retorno)
    assert int(fila["tiempo_cpu_ocupado"]) == 3
    assert int(fila["tiempo_cpu_inactivo"]) == 3
    assert int(fila["tiempo_total"]) == 6
    assert float(fila["utilizacion_cpu"]) == pytest.approx(50)


def test_exportar_traza_escribe_el_archivo_en_utf8(
    tmp_path: Path,
    resultado: ResultadoSimulacion,
) -> None:
    ruta = tmp_path / "traza.csv"

    ruta_escrita = exportar_traza(resultado, ruta)

    assert ruta_escrita == ruta
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    assert lineas[0] == ",".join(COLUMNAS_TRAZA)
    assert lineas[1] == "FIFO,0,2,2,P001,normal"


def test_exportar_metricas_usa_el_mismo_formato(
    tmp_path: Path,
    resultado: ResultadoSimulacion,
) -> None:
    ruta = exportar_metricas(resultado, tmp_path / "metricas.csv")

    assert ruta.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNAS_METRICAS)


def test_exportar_resultados_usa_el_mismo_formato(
    tmp_path: Path,
    resultado: ResultadoSimulacion,
) -> None:
    ruta = exportar_resultados(resultado, tmp_path / "resultados.csv")

    assert ruta.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUMNAS_RESULTADOS)
