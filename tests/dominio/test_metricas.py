"""Pruebas de construcción de trazas y cálculo de métricas."""

import pytest

from simulador.dominio import (
    Algoritmo,
    ErrorValidacion,
    Proceso,
    SegmentoEjecucion,
    Servicio,
    calcular_metricas,
    calcular_resultados,
    construir_traza,
    validar_traza,
)


def crear_proceso(
    id_proceso: str,
    tiempo_llegada: int,
    rafaga: int,
    *,
    orden_ingreso: int = 0,
    id_cola: str = "normal",
) -> Proceso:
    return Proceso(
        id_proceso=id_proceso,
        id_cliente="C001",
        servicio=Servicio.INTERNET,
        cantidad_gestiones=1,
        tiempo_llegada=tiempo_llegada,
        rafaga=rafaga,
        prioridad=1,
        id_cola=id_cola,
        orden_ingreso=orden_ingreso,
    )


def test_traza_con_idle_calcula_resultados_y_metricas() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, id_cola="alta"),
        crear_proceso("P002", 5, 2, orden_ingreso=1),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=3, id_cola="alta"),
        SegmentoEjecucion(None, inicio=3, fin=5),
        SegmentoEjecucion("P002", inicio=5, fin=7, id_cola="normal"),
    )

    resultado = calcular_metricas(
        segmentos,
        procesos,
        algoritmo=Algoritmo.FIFO,
    )

    assert [proceso.id_proceso for proceso in resultado.resultados] == ["P001", "P002"]
    assert resultado.resultados[0].tiempo_finalizacion == 3
    assert resultado.resultados[0].tiempo_espera == 0
    assert resultado.resultados[0].tiempo_retorno == 3
    assert resultado.resultados[1].tiempo_finalizacion == 7
    assert resultado.resultados[1].tiempo_espera == 0
    assert resultado.resultados[1].tiempo_retorno == 2
    assert resultado.tiempo_cpu_ocupado == 5
    assert resultado.tiempo_cpu_inactivo == 2
    assert resultado.tiempo_total == 7
    assert resultado.promedio_espera == 0
    assert resultado.promedio_retorno == pytest.approx(2.5)
    assert resultado.utilizacion_cpu == pytest.approx(5 / 7 * 100)
    assert resultado.segmentos == segmentos


def test_formulas_de_espera_y_retorno_con_procesos_en_espera() -> None:
    procesos = (
        crear_proceso("P002", 0, 3, orden_ingreso=1),
        crear_proceso("P001", 0, 2, orden_ingreso=0),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=2),
        SegmentoEjecucion("P002", inicio=2, fin=5),
    )

    resultados = calcular_resultados(segmentos, procesos)

    assert [resultado.id_proceso for resultado in resultados] == ["P001", "P002"]
    assert resultados[0].tiempo_espera == 0
    assert resultados[0].tiempo_retorno == 2
    assert resultados[1].tiempo_espera == 2
    assert resultados[1].tiempo_retorno == 5

    resultado = calcular_metricas(segmentos, procesos, algoritmo=Algoritmo.FIFO)

    assert resultado.promedio_espera == pytest.approx(1)
    assert resultado.promedio_retorno == pytest.approx(3.5)
    assert resultado.tiempo_cpu_ocupado == 5
    assert resultado.tiempo_cpu_inactivo == 0
    assert resultado.tiempo_total == 5
    assert resultado.utilizacion_cpu == pytest.approx(100)


def test_resultados_suman_rafagas_con_segmentos_multiples() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 0, 2, orden_ingreso=1),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=2),
        SegmentoEjecucion("P002", inicio=2, fin=4),
        SegmentoEjecucion("P001", inicio=4, fin=7),
    )

    resultado = calcular_metricas(segmentos, procesos, algoritmo=Algoritmo.ROUND_ROBIN)

    assert resultado.resultados[0].tiempo_finalizacion == 7
    assert resultado.resultados[0].tiempo_espera == 2
    assert resultado.resultados[0].tiempo_retorno == 7
    assert resultado.resultados[1].tiempo_finalizacion == 4
    assert resultado.resultados[1].tiempo_espera == 2
    assert resultado.resultados[1].tiempo_retorno == 4
    assert resultado.promedio_espera == pytest.approx(2)
    assert resultado.promedio_retorno == pytest.approx(5.5)
    assert resultado.utilizacion_cpu == pytest.approx(100)


def test_construir_traza_ordena_segmentos_desordenados() -> None:
    procesos = (
        crear_proceso("P001", 0, 3),
        crear_proceso("P002", 5, 2, orden_ingreso=1),
    )
    segmentos = (
        SegmentoEjecucion(None, inicio=3, fin=5),
        SegmentoEjecucion("P002", inicio=5, fin=7),
        SegmentoEjecucion("P001", inicio=0, fin=3),
    )

    traza = construir_traza(segmentos, procesos)

    assert [segmento.inicio for segmento in traza] == [0, 3, 5]
    assert [segmento.etiqueta for segmento in traza] == ["P001", "IDLE", "P002"]


def test_traza_conserva_segmentos_consecutivos_de_un_mismo_proceso() -> None:
    procesos = (crear_proceso("P001", 0, 5),)
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=2),
        SegmentoEjecucion("P001", inicio=2, fin=5),
    )

    traza = construir_traza(segmentos, procesos)

    assert len(traza) == 2
    assert [segmento.inicio for segmento in traza] == [0, 2]


def test_validar_traza_rechaza_superposicion() -> None:
    procesos = (
        crear_proceso("P001", 0, 5),
        crear_proceso("P002", 0, 5),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=3),
        SegmentoEjecucion("P002", inicio=2, fin=5),
    )

    with pytest.raises(ErrorValidacion, match="superpon"):
        construir_traza(segmentos, procesos)


def test_validar_traza_rechaza_ejecucion_antes_de_la_llegada() -> None:
    procesos = (crear_proceso("P001", 2, 2),)
    segmentos = (SegmentoEjecucion("P001", inicio=0, fin=2),)

    with pytest.raises(ErrorValidacion, match="antes de su tiempo de llegada"):
        construir_traza(segmentos, procesos)


def test_validar_traza_rechaza_retroceso_del_reloj() -> None:
    procesos = (
        crear_proceso("P001", 0, 5),
        crear_proceso("P002", 0, 1),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=2, fin=4),
        SegmentoEjecucion("P002", inicio=0, fin=1),
    )

    with pytest.raises(ErrorValidacion, match="retrocede"):
        validar_traza(segmentos, procesos)


def test_construir_traza_rechaza_hueco_sin_idle() -> None:
    procesos = (
        crear_proceso("P001", 0, 2),
        crear_proceso("P002", 0, 2),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=2),
        SegmentoEjecucion("P002", inicio=3, fin=5),
    )

    with pytest.raises(ErrorValidacion, match="IDLE"):
        construir_traza(segmentos, procesos)


def test_construir_traza_rechaza_inicio_distinto_de_cero() -> None:
    procesos = (crear_proceso("P001", 0, 2),)
    segmentos = (SegmentoEjecucion("P001", inicio=2, fin=4),)

    with pytest.raises(ErrorValidacion, match="comenzar en 0"):
        construir_traza(segmentos, procesos)


def test_validar_traza_rechaza_proceso_desconocido() -> None:
    procesos = (crear_proceso("P001", 0, 2),)
    segmentos = (SegmentoEjecucion("P999", inicio=0, fin=2),)

    with pytest.raises(ErrorValidacion, match="desconocido"):
        validar_traza(segmentos, procesos)


def test_calcular_resultados_rechaza_proceso_incompleto() -> None:
    procesos = (crear_proceso("P001", 0, 5),)
    segmentos = (SegmentoEjecucion("P001", inicio=0, fin=3),)

    with pytest.raises(ErrorValidacion, match="no completó su ráfaga"):
        calcular_resultados(segmentos, procesos)


def test_validar_traza_rechaza_rafaga_excedida() -> None:
    procesos = (crear_proceso("P001", 0, 3),)
    segmentos = (SegmentoEjecucion("P001", inicio=0, fin=4),)

    with pytest.raises(ErrorValidacion, match="excede su ráfaga"):
        validar_traza(segmentos, procesos)


def test_calcular_metricas_rechaza_carga_vacia() -> None:
    with pytest.raises(ErrorValidacion, match="sin procesos"):
        calcular_metricas((), (), algoritmo=Algoritmo.FIFO)


def test_calcular_metricas_no_modifica_la_carga_original() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, orden_ingreso=0),
        crear_proceso("P002", 5, 2, orden_ingreso=1),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=3),
        SegmentoEjecucion(None, inicio=3, fin=5),
        SegmentoEjecucion("P002", inicio=5, fin=7),
    )

    resultado = calcular_metricas(segmentos, procesos, algoritmo=Algoritmo.FIFO)

    assert procesos == (
        crear_proceso("P001", 0, 3, orden_ingreso=0),
        crear_proceso("P002", 5, 2, orden_ingreso=1),
    )
    assert procesos[0].tiempo_restante == procesos[0].rafaga
    assert resultado is not procesos
