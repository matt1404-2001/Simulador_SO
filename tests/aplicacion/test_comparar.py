"""Pruebas de la comparación de FIFO, SJF y Round Robin."""

import pytest

from simulador.aplicacion import comparar_algoritmos
from simulador.dominio import Algoritmo, ErrorConfiguracion
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def test_comparacion_ejecuta_los_tres_algoritmos_sobre_la_misma_carga() -> None:
    procesos = (
        crear_proceso("P001", 0, 6, orden_ingreso=0),
        crear_proceso("P002", 0, 2, orden_ingreso=1),
        crear_proceso("P003", 0, 4, orden_ingreso=2),
    )

    comparacion = comparar_algoritmos(procesos, quantum=4)

    assert [resultado.algoritmo for resultado in comparacion.resultados] == [
        Algoritmo.FIFO,
        Algoritmo.SJF,
        Algoritmo.ROUND_ROBIN,
    ]
    assert describir_segmentos(comparacion.fifo) == [
        ("P001", 0, 6),
        ("P002", 6, 8),
        ("P003", 8, 12),
    ]
    assert describir_segmentos(comparacion.sjf) == [
        ("P002", 0, 2),
        ("P003", 2, 6),
        ("P001", 6, 12),
    ]
    assert describir_segmentos(comparacion.round_robin) == [
        ("P001", 0, 4),
        ("P002", 4, 6),
        ("P003", 6, 10),
        ("P001", 10, 12),
    ]


def test_cada_algoritmo_conserva_su_utilizacion_cpu() -> None:
    procesos = (
        crear_proceso("P001", 0, 10, orden_ingreso=0),
        crear_proceso("P002", 20, 2, orden_ingreso=1),
    )

    comparacion = comparar_algoritmos(procesos, quantum=4)

    for resultado in comparacion.resultados:
        assert resultado.tiempo_cpu_ocupado == 12
        assert resultado.tiempo_cpu_inactivo == 10
        assert resultado.tiempo_total == 22
        assert resultado.utilizacion_cpu == pytest.approx(12 / 22 * 100)
        verificar_invariantes(resultado)


def test_los_resultados_son_independientes_y_la_carga_no_cambia() -> None:
    procesos = (
        crear_proceso("P001", 0, 6, orden_ingreso=0),
        crear_proceso("P002", 0, 2, orden_ingreso=1),
        crear_proceso("P003", 0, 4, orden_ingreso=2),
    )
    copia = tuple(procesos)

    comparacion = comparar_algoritmos(procesos, quantum=4)

    assert procesos == copia
    assert comparacion.fifo is not comparacion.sjf
    assert comparacion.fifo is not comparacion.round_robin
    assert comparacion.fifo.segmentos is not comparacion.sjf.segmentos
    assert all(resultado.tiempo_cpu_ocupado == 12 for resultado in comparacion.resultados)


def test_comparacion_rechaza_un_quantum_invalido() -> None:
    procesos = (crear_proceso("P001", 0, 2),)

    with pytest.raises(ErrorConfiguracion, match="mayor que cero"):
        comparar_algoritmos(procesos, quantum=0)
