"""Pruebas del planificador MLQ configurable."""

import pytest

from simulador.dominio import (
    Algoritmo,
    ConfiguracionCola,
    ErrorConfiguracion,
    ErrorValidacion,
    EstadoProceso,
)
from simulador.dominio.planificadores import PlanificadorMLQ
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def crear_cola(
    id_cola: str,
    prioridad_cola: int,
    algoritmo: Algoritmo,
    *,
    quantum: int | None = None,
) -> ConfiguracionCola:
    """Crea una cola MLQ con el algoritmo y la prioridad indicados."""

    return ConfiguracionCola(
        id_cola=id_cola,
        nombre=id_cola.title(),
        prioridad_cola=prioridad_cola,
        algoritmo=algoritmo,
        quantum=quantum,
    )


def test_mlq_atiende_primero_la_cola_de_menor_prioridad_numerica() -> None:
    configuracion = (
        crear_cola("baja", 4, Algoritmo.FIFO),
        crear_cola("alta", 1, Algoritmo.FIFO),
    )
    procesos = (
        crear_proceso("P001", 0, 3, id_cola="baja", orden_ingreso=0),
        crear_proceso("P002", 0, 2, id_cola="alta", orden_ingreso=1),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P002", 0, 2),
        ("P001", 2, 5),
    ]
    assert resultado.algoritmo is Algoritmo.MLQ
    verificar_invariantes(resultado)


def test_mlq_desempata_por_indice_de_configuracion() -> None:
    configuracion = (
        crear_cola("zona_b", 1, Algoritmo.FIFO),
        crear_cola("zona_a", 1, Algoritmo.FIFO),
    )
    procesos = (
        crear_proceso("P001", 0, 2, id_cola="zona_a", orden_ingreso=0),
        crear_proceso("P002", 0, 2, id_cola="zona_b", orden_ingreso=1),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P002", 0, 2),
        ("P001", 2, 4),
    ]
    verificar_invariantes(resultado)


def test_mlq_ignora_una_cola_configurada_sin_procesos() -> None:
    configuracion = (
        crear_cola("alta", 1, Algoritmo.FIFO),
        crear_cola("baja", 2, Algoritmo.FIFO),
    )
    procesos = (crear_proceso("P001", 0, 2, id_cola="baja"),)

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [("P001", 0, 2)]
    assert [segmento.id_cola for segmento in resultado.segmentos] == ["baja"]
    verificar_invariantes(resultado)


def test_mlq_rechaza_un_proceso_sin_cola_configurada() -> None:
    configuracion = (crear_cola("alta", 1, Algoritmo.FIFO),)
    procesos = (crear_proceso("P001", 0, 2, id_cola="desconocida"),)

    with pytest.raises(ErrorValidacion, match="cola configurada"):
        PlanificadorMLQ().planificar(procesos, configuracion)


def test_mlq_rechaza_una_carga_sin_colas_configuradas() -> None:
    procesos = (crear_proceso("P001", 0, 2, id_cola="normal"),)

    with pytest.raises(ErrorValidacion, match="cola configurada"):
        PlanificadorMLQ().planificar(procesos, ())


def test_mlq_rechaza_colas_duplicadas_en_la_configuracion() -> None:
    configuracion = (
        crear_cola("alta", 1, Algoritmo.FIFO),
        crear_cola("alta", 2, Algoritmo.FIFO),
    )
    procesos = (crear_proceso("P001", 0, 2, id_cola="alta"),)

    with pytest.raises(ErrorConfiguracion, match="duplicada"):
        PlanificadorMLQ().planificar(procesos, configuracion)


def test_mlq_no_interrumpe_fifo_por_una_llegada_a_cola_superior() -> None:
    configuracion = (
        crear_cola("alta", 1, Algoritmo.FIFO),
        crear_cola("baja", 2, Algoritmo.FIFO),
    )
    procesos = (
        crear_proceso("P001", 0, 5, id_cola="baja", orden_ingreso=0),
        crear_proceso("P002", 2, 1, id_cola="alta", orden_ingreso=1),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 5),
        ("P002", 5, 6),
    ]
    verificar_invariantes(resultado)


def test_mlq_no_interrumpe_sjf_por_una_llegada_a_cola_superior() -> None:
    configuracion = (
        crear_cola("alta", 1, Algoritmo.FIFO),
        crear_cola("media", 2, Algoritmo.SJF),
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
    verificar_invariantes(resultado)


def test_mlq_reevalua_las_colas_al_terminar_un_quantum() -> None:
    configuracion = (
        crear_cola("alta", 1, Algoritmo.FIFO),
        crear_cola("media", 2, Algoritmo.ROUND_ROBIN, quantum=3),
    )
    procesos = (
        crear_proceso("P001", 0, 6, id_cola="media", orden_ingreso=0),
        crear_proceso("P002", 2, 1, id_cola="alta", orden_ingreso=1),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 3),
        ("P002", 3, 4),
        ("P001", 4, 7),
    ]
    verificar_invariantes(resultado)


def test_mlq_mantiene_el_turno_circular_dentro_de_la_cola_round_robin() -> None:
    configuracion = (crear_cola("alta", 1, Algoritmo.ROUND_ROBIN, quantum=2),)
    procesos = (
        crear_proceso("P001", 0, 4, id_cola="alta", orden_ingreso=0),
        crear_proceso("P002", 1, 1, id_cola="alta", orden_ingreso=1),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P002", 2, 3),
        ("P001", 3, 5),
    ]
    verificar_invariantes(resultado)


def test_mlq_aplica_sjf_dentro_de_la_cola() -> None:
    configuracion = (crear_cola("media", 2, Algoritmo.SJF),)
    procesos = (
        crear_proceso("P001", 0, 5, id_cola="media", orden_ingreso=0),
        crear_proceso("P002", 0, 2, id_cola="media", orden_ingreso=1),
        crear_proceso("P003", 0, 3, id_cola="media", orden_ingreso=2),
    )

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("P002", 0, 2),
        ("P003", 2, 5),
        ("P001", 5, 10),
    ]
    verificar_invariantes(resultado)


def test_mlq_inserta_idle_hasta_la_siguiente_llegada() -> None:
    configuracion = (crear_cola("alta", 1, Algoritmo.FIFO),)
    procesos = (crear_proceso("P001", 3, 2, id_cola="alta"),)

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert describir_segmentos(resultado) == [
        ("IDLE", 0, 3),
        ("P001", 3, 5),
    ]
    assert resultado.tiempo_cpu_inactivo == 3
    assert resultado.utilizacion_cpu == pytest.approx(40)
    verificar_invariantes(resultado)


def test_mlq_conserva_la_configuracion_recibida() -> None:
    configuracion = (crear_cola("alta", 1, Algoritmo.FIFO),)
    procesos = (crear_proceso("P001", 0, 2, id_cola="alta"),)

    resultado = PlanificadorMLQ().planificar(procesos, configuracion)

    assert resultado.configuraciones_colas == configuracion
    assert resultado.configuraciones_colas[0] is not configuracion[0]


def test_mlq_no_modifica_la_carga_original() -> None:
    configuracion = (
        crear_cola("alta", 1, Algoritmo.ROUND_ROBIN, quantum=2),
        crear_cola("baja", 2, Algoritmo.FIFO),
    )
    procesos = (
        crear_proceso("P001", 0, 5, id_cola="alta", orden_ingreso=0),
        crear_proceso("P002", 1, 3, id_cola="baja", orden_ingreso=1),
    )
    copia = tuple(procesos)

    PlanificadorMLQ().planificar(procesos, configuracion)

    assert procesos == copia
    assert [proceso.tiempo_restante for proceso in procesos] == [5, 3]
    assert all(proceso.estado is EstadoProceso.NUEVO for proceso in procesos)


def test_mlq_rechaza_carga_vacia() -> None:
    configuracion = (crear_cola("alta", 1, Algoritmo.FIFO),)

    with pytest.raises(ErrorValidacion, match="sin procesos"):
        PlanificadorMLQ().planificar((), configuracion)


def test_mlq_rechaza_identificadores_duplicados() -> None:
    configuracion = (crear_cola("alta", 1, Algoritmo.FIFO),)
    procesos = (
        crear_proceso("P001", 0, 2, id_cola="alta", orden_ingreso=0),
        crear_proceso("P001", 1, 2, id_cola="alta", orden_ingreso=1),
    )

    with pytest.raises(ErrorValidacion, match="duplicados"):
        PlanificadorMLQ().planificar(procesos, configuracion)
