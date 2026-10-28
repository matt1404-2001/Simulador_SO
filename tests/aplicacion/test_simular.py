"""Pruebas de la preparación de cargas y la ejecución de algoritmos."""

import pytest

from simulador.aplicacion import ejecutar_algoritmo, preparar_carga
from simulador.dominio import (
    Algoritmo,
    ConfiguracionCola,
    ErrorConfiguracion,
    ErrorValidacion,
)
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def _crear_cola(
    id_cola: str,
    prioridad_cola: int,
    algoritmo: Algoritmo,
    *,
    quantum: int | None = None,
) -> ConfiguracionCola:
    """Crea una cola MLQ con los valores indicados."""

    return ConfiguracionCola(
        id_cola=id_cola,
        nombre=id_cola.title(),
        prioridad_cola=prioridad_cola,
        algoritmo=algoritmo,
        quantum=quantum,
    )


def test_preparar_carga_devuelve_copias_de_procesos_y_colas() -> None:
    procesos = (crear_proceso("P001", 0, 2),)
    configuracion = (_crear_cola("normal", 3, Algoritmo.FIFO),)

    procesos_copiados, configuracion_copiada = preparar_carga(procesos, configuracion)

    assert procesos_copiados == procesos
    assert procesos_copiados is not procesos
    assert procesos_copiados[0] is not procesos[0]
    assert configuracion_copiada == configuracion
    assert configuracion_copiada is not configuracion
    assert configuracion_copiada[0] is not configuracion[0]


def test_preparar_carga_rechaza_carga_vacia() -> None:
    with pytest.raises(ErrorValidacion, match="sin procesos"):
        preparar_carga(())


def test_preparar_carga_rechaza_identificadores_duplicados() -> None:
    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P001", 1, 2, orden_ingreso=1),
    )

    with pytest.raises(ErrorValidacion, match="duplicados"):
        preparar_carga(procesos)


def test_preparar_carga_rechaza_colas_duplicadas() -> None:
    procesos = (crear_proceso("P001", 0, 2),)
    configuracion = (
        _crear_cola("normal", 3, Algoritmo.FIFO),
        _crear_cola("normal", 4, Algoritmo.FIFO),
    )

    with pytest.raises(ErrorConfiguracion, match="colas duplicadas"):
        preparar_carga(procesos, configuracion)


def test_ejecuta_fifo_desde_una_carga_preparada() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 2, 3, orden_ingreso=1),
    )

    resultado = ejecutar_algoritmo(procesos, Algoritmo.FIFO)

    assert resultado.algoritmo is Algoritmo.FIFO
    assert describir_segmentos(resultado) == [
        ("P001", 0, 5),
        ("P002", 5, 8),
    ]
    assert resultado.promedio_espera == pytest.approx(1.5)
    assert resultado.promedio_retorno == pytest.approx(5.5)
    assert resultado.utilizacion_cpu == pytest.approx(100)
    verificar_invariantes(resultado)


def test_ejecuta_sjf_desde_una_carga_preparada() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 0, 2, orden_ingreso=1),
    )

    resultado = ejecutar_algoritmo(procesos, Algoritmo.SJF)

    assert resultado.algoritmo is Algoritmo.SJF
    assert describir_segmentos(resultado) == [
        ("P002", 0, 2),
        ("P001", 2, 7),
    ]
    assert resultado.promedio_espera == pytest.approx(1)
    assert resultado.promedio_retorno == pytest.approx(4.5)
    verificar_invariantes(resultado)


def test_ejecuta_round_robin_con_su_quantum() -> None:
    procesos = (
        crear_proceso("P001", 0, 4, orden_ingreso=0),
        crear_proceso("P002", 1, 3, orden_ingreso=1),
    )

    resultado = ejecutar_algoritmo(procesos, Algoritmo.ROUND_ROBIN, quantum=2)

    assert resultado.algoritmo is Algoritmo.ROUND_ROBIN
    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P002", 2, 4),
        ("P001", 4, 6),
        ("P002", 6, 7),
    ]
    assert resultado.promedio_espera == pytest.approx(2.5)
    assert resultado.promedio_retorno == pytest.approx(6)
    verificar_invariantes(resultado)


def test_ejecuta_mlq_desde_una_carga_preparada() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, orden_ingreso=0, id_cola="alta"),
        crear_proceso("P002", 0, 2, orden_ingreso=1, id_cola="baja"),
    )
    configuracion = (
        _crear_cola("alta", 1, Algoritmo.ROUND_ROBIN, quantum=2),
        _crear_cola("baja", 2, Algoritmo.FIFO),
    )

    resultado = ejecutar_algoritmo(procesos, Algoritmo.MLQ, configuracion=configuracion)

    assert resultado.algoritmo is Algoritmo.MLQ
    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P001", 2, 3),
        ("P002", 3, 5),
    ]
    assert resultado.promedio_espera == pytest.approx(1.5)
    assert resultado.promedio_retorno == pytest.approx(4)
    assert resultado.configuraciones_colas == configuracion
    verificar_invariantes(resultado)


def test_ejecutar_algoritmo_no_modifica_la_carga_original() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 2, 3, orden_ingreso=1),
    )
    copia = tuple(procesos)

    ejecutar_algoritmo(procesos, Algoritmo.FIFO)

    assert procesos == copia


def test_round_robin_individual_requiere_quantum() -> None:
    procesos = (crear_proceso("P001", 0, 2),)

    with pytest.raises(ErrorConfiguracion, match="requiere quantum"):
        ejecutar_algoritmo(procesos, Algoritmo.ROUND_ROBIN)


def test_algoritmo_no_apropiativo_rechaza_quantum() -> None:
    procesos = (crear_proceso("P001", 0, 2),)

    with pytest.raises(ErrorConfiguracion, match="solo se configura"):
        ejecutar_algoritmo(procesos, Algoritmo.FIFO, quantum=2)


def test_mlq_rechaza_quantum_global() -> None:
    procesos = (crear_proceso("P001", 0, 2, id_cola="alta"),)
    configuracion = (_crear_cola("alta", 1, Algoritmo.ROUND_ROBIN, quantum=2),)

    with pytest.raises(ErrorConfiguracion, match="quantum de cada cola"):
        ejecutar_algoritmo(
            procesos,
            Algoritmo.MLQ,
            quantum=2,
            configuracion=configuracion,
        )


def test_rechaza_un_algoritmo_ajeno_al_dominio() -> None:
    procesos = (crear_proceso("P001", 0, 2),)

    with pytest.raises(ErrorConfiguracion, match="Algoritmo válido"):
        ejecutar_algoritmo(procesos, "FIFO")  # type: ignore[arg-type]
