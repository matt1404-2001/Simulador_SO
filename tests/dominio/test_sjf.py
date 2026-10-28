"""Pruebas del planificador SJF no apropiativo."""

import pytest

from simulador.dominio import Algoritmo, ErrorValidacion, EstadoProceso
from simulador.dominio.planificadores import PlanificadorSJF
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def test_sjf_elige_la_menor_rafaga_entre_los_ya_llegados() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 0, 2, orden_ingreso=1),
        crear_proceso("P003", 0, 4, orden_ingreso=2),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P002", 0, 2),
        ("P003", 2, 6),
        ("P001", 6, 11),
    ]
    assert resultado.algoritmo is Algoritmo.SJF
    resultados = resultado.resultados
    assert [resultado_proceso.tiempo_finalizacion for resultado_proceso in resultados] == [
        11,
        2,
        6,
    ]
    assert [resultado_proceso.tiempo_espera for resultado_proceso in resultados] == [
        6,
        0,
        2,
    ]
    assert resultado.promedio_espera == pytest.approx(8 / 3)
    assert resultado.promedio_retorno == pytest.approx(19 / 3)
    verificar_invariantes(resultado)


def test_sjf_reevalua_la_menor_rafaga_en_cada_despacho() -> None:
    procesos = (
        crear_proceso("P001", 0, 6, orden_ingreso=0),
        crear_proceso("P002", 1, 4, orden_ingreso=1),
        crear_proceso("P003", 2, 2, orden_ingreso=2),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 6),
        ("P003", 6, 8),
        ("P002", 8, 12),
    ]
    assert resultado.resultados[1].tiempo_espera == 7
    assert resultado.resultados[2].tiempo_espera == 4
    verificar_invariantes(resultado)


def test_sjf_no_adelanta_un_proceso_que_llega_durante_la_ejecucion() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 1, 1, orden_ingreso=1),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 5),
        ("P002", 5, 6),
    ]
    assert resultado.resultados[1].tiempo_espera == 4


def test_sjf_desempata_por_tiempo_de_llegada() -> None:
    procesos = (
        crear_proceso("P001", 2, 3),
        crear_proceso("P002", 0, 3),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == ["P002", "P001"]


def test_sjf_desempata_por_orden_de_ingreso() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, orden_ingreso=1),
        crear_proceso("P002", 0, 3, orden_ingreso=0),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == ["P002", "P001"]


def test_sjf_desempata_por_id_proceso() -> None:
    procesos = (
        crear_proceso("P003", 0, 2),
        crear_proceso("P001", 0, 2),
        crear_proceso("P002", 0, 2),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == [
        "P001",
        "P002",
        "P003",
    ]


def test_sjf_consume_exactamente_la_rafaga() -> None:
    procesos = (
        crear_proceso("P001", 0, 4, orden_ingreso=0),
        crear_proceso("P002", 0, 1, orden_ingreso=1),
    )

    resultado = PlanificadorSJF().planificar(procesos, ())

    ejecutado: dict[str, int] = {}
    for segmento in resultado.segmentos:
        if segmento.id_proceso is not None:
            ejecutado[segmento.id_proceso] = (
                ejecutado.get(segmento.id_proceso, 0) + segmento.duracion
            )

    assert ejecutado == {"P001": 4, "P002": 1}
    assert resultado.tiempo_cpu_ocupado == 5
    assert resultado.utilizacion_cpu == pytest.approx(100)
    verificar_invariantes(resultado)


def test_sjf_inserta_idle_inicial_hasta_la_primera_llegada() -> None:
    procesos = (crear_proceso("P001", 4, 2),)

    resultado = PlanificadorSJF().planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("IDLE", 0, 4),
        ("P001", 4, 6),
    ]
    assert resultado.tiempo_cpu_inactivo == 4
    assert resultado.resultados[0].tiempo_espera == 0
    verificar_invariantes(resultado)


def test_sjf_no_modifica_la_carga_original() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 0, 2, orden_ingreso=1),
    )
    copia = tuple(procesos)

    PlanificadorSJF().planificar(procesos, ())

    assert procesos == copia
    assert [proceso.tiempo_restante for proceso in procesos] == [5, 2]
    assert all(proceso.estado is EstadoProceso.NUEVO for proceso in procesos)


def test_sjf_rechaza_carga_vacia() -> None:
    with pytest.raises(ErrorValidacion, match="sin procesos"):
        PlanificadorSJF().planificar((), ())
