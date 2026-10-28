"""Pruebas del planificador FIFO."""

import pytest

from simulador.dominio import (
    Algoritmo,
    ConfiguracionCola,
    ErrorValidacion,
    EstadoProceso,
)
from simulador.dominio.planificadores import PlanificadorFIFO
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def test_fifo_atiende_por_llegada_sin_reordenar_por_rafaga() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, orden_ingreso=0),
        crear_proceso("P002", 2, 2, orden_ingreso=1),
        crear_proceso("P003", 2, 1, orden_ingreso=2),
    )

    resultado = PlanificadorFIFO().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 3),
        ("P002", 3, 5),
        ("P003", 5, 6),
    ]
    assert resultado.algoritmo is Algoritmo.FIFO
    resultados = resultado.resultados
    assert [resultado_proceso.tiempo_finalizacion for resultado_proceso in resultados] == [
        3,
        5,
        6,
    ]
    assert [resultado_proceso.tiempo_espera for resultado_proceso in resultados] == [
        0,
        1,
        3,
    ]
    assert resultado.promedio_espera == pytest.approx(4 / 3)
    verificar_invariantes(resultado)


def test_fifo_desempata_por_orden_de_ingreso() -> None:
    procesos = (
        crear_proceso("P002", 0, 1, orden_ingreso=1),
        crear_proceso("P001", 0, 1, orden_ingreso=0),
    )

    resultado = PlanificadorFIFO().planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == ["P001", "P002"]


def test_fifo_desempata_por_id_proceso_cuando_el_ingreso_empata() -> None:
    procesos = (
        crear_proceso("P003", 0, 1),
        crear_proceso("P001", 0, 1),
        crear_proceso("P002", 0, 1),
    )

    resultado = PlanificadorFIFO().planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == [
        "P001",
        "P002",
        "P003",
    ]


def test_fifo_inserta_idle_inicial_hasta_la_primera_llegada() -> None:
    procesos = (crear_proceso("P001", 3, 2),)

    resultado = PlanificadorFIFO().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("IDLE", 0, 3),
        ("P001", 3, 5),
    ]
    assert resultado.tiempo_cpu_inactivo == 3
    assert resultado.tiempo_total == 5
    assert resultado.utilizacion_cpu == pytest.approx(40)
    assert resultado.resultados[0].tiempo_espera == 0
    verificar_invariantes(resultado)


def test_fifo_inserta_idle_entre_llegadas_distantes() -> None:
    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P002", 6, 3, orden_ingreso=1),
    )

    resultado = PlanificadorFIFO().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("IDLE", 2, 6),
        ("P002", 6, 9),
    ]
    assert resultado.tiempo_cpu_inactivo == 4
    assert resultado.tiempo_total == 9
    assert resultado.utilizacion_cpu == pytest.approx(5 / 9 * 100)
    assert resultado.resultados[1].tiempo_espera == 0
    verificar_invariantes(resultado)


def test_fifo_no_inserta_idle_si_la_llegada_coincide_con_la_finalizacion() -> None:
    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P002", 2, 1, orden_ingreso=1),
    )

    resultado = PlanificadorFIFO().planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == ["P001", "P002"]
    assert resultado.tiempo_cpu_inactivo == 0
    assert resultado.utilizacion_cpu == pytest.approx(100)


def test_fifo_conserva_la_configuracion_recibida() -> None:
    configuracion = (
        ConfiguracionCola(
            id_cola="normal",
            nombre="Normal",
            prioridad_cola=3,
            algoritmo=Algoritmo.FIFO,
        ),
    )

    resultado = PlanificadorFIFO().planificar((crear_proceso("P001", 0, 2),), configuracion)

    assert resultado.configuraciones_colas == configuracion


def test_fifo_no_modifica_la_carga_original() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, orden_ingreso=0),
        crear_proceso("P002", 1, 2, orden_ingreso=1),
    )
    copia = tuple(procesos)

    PlanificadorFIFO().planificar(procesos, ())

    assert procesos == copia
    assert [proceso.tiempo_restante for proceso in procesos] == [3, 2]
    assert all(proceso.estado is EstadoProceso.NUEVO for proceso in procesos)


def test_fifo_rechaza_carga_vacia() -> None:
    with pytest.raises(ErrorValidacion, match="sin procesos"):
        PlanificadorFIFO().planificar((), ())
