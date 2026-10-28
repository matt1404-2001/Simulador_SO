"""Pruebas de integración de MLQ con configuraciones mixtas."""

import pytest

from simulador.dominio import Algoritmo, ConfiguracionCola
from simulador.dominio.planificadores import PlanificadorMLQ
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def test_mlq_integra_fifo_sjf_y_round_robin_en_una_sola_traza() -> None:
    configuracion = (
        ConfiguracionCola(
            id_cola="alta",
            nombre="Alta",
            prioridad_cola=1,
            algoritmo=Algoritmo.ROUND_ROBIN,
            quantum=2,
        ),
        ConfiguracionCola(
            id_cola="media",
            nombre="Media",
            prioridad_cola=2,
            algoritmo=Algoritmo.SJF,
        ),
        ConfiguracionCola(
            id_cola="normal",
            nombre="Normal",
            prioridad_cola=3,
            algoritmo=Algoritmo.FIFO,
        ),
    )
    procesos = (
        crear_proceso("P001", 0, 5, id_cola="alta", orden_ingreso=0),
        crear_proceso("P002", 1, 4, id_cola="media", orden_ingreso=1),
        crear_proceso("P003", 1, 2, id_cola="normal", orden_ingreso=2),
        crear_proceso("P004", 2, 1, id_cola="media", orden_ingreso=3),
        crear_proceso("P005", 20, 1, id_cola="normal", orden_ingreso=4),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P001", 2, 4),
        ("P001", 4, 5),
        ("P004", 5, 6),
        ("P002", 6, 10),
        ("P003", 10, 12),
        ("IDLE", 12, 20),
        ("P005", 20, 21),
    ]
    assert resultado.algoritmo is Algoritmo.MLQ
    assert resultado.tiempo_cpu_ocupado == 13
    assert resultado.tiempo_cpu_inactivo == 8
    assert resultado.tiempo_total == 21
    assert resultado.utilizacion_cpu == pytest.approx(13 / 21 * 100)
    assert resultado.promedio_espera == pytest.approx(17 / 5)
    assert resultado.promedio_retorno == pytest.approx(30 / 5)
    assert [segmento.id_cola for segmento in resultado.segmentos] == [
        "alta",
        "alta",
        "alta",
        "media",
        "media",
        "normal",
        None,
        "normal",
    ]
    verificar_invariantes(resultado)


def test_mlq_espera_el_fin_de_sjf_antes_de_atender_una_cola_superior() -> None:
    configuracion = (
        ConfiguracionCola(
            id_cola="alta",
            nombre="Alta",
            prioridad_cola=1,
            algoritmo=Algoritmo.FIFO,
        ),
        ConfiguracionCola(
            id_cola="media",
            nombre="Media",
            prioridad_cola=2,
            algoritmo=Algoritmo.SJF,
        ),
    )
    procesos = (
        crear_proceso("P001", 0, 6, id_cola="media", orden_ingreso=0),
        crear_proceso("P002", 3, 2, id_cola="alta", orden_ingreso=1),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 6),
        ("P002", 6, 8),
    ]
    assert resultado.promedio_espera == pytest.approx(3 / 2)
    assert resultado.promedio_retorno == pytest.approx(11 / 2)
    verificar_invariantes(resultado)
