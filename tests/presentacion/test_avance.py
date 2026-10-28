"""Pruebas de la reconstrucción paso a paso de una traza."""

import pytest

from simulador.dominio import (
    Algoritmo,
    ErrorValidacion,
    ResultadoProceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
    calcular_metricas,
)
from simulador.dominio.enumeraciones import EstadoProceso
from simulador.presentacion.avance import construir_pasos
from tests.presentacion.ayudas import crear_proceso, resultado_con_idle


def _fichas(paso) -> dict[str, object]:
    return {ficha.id_proceso: ficha for ficha in paso.procesos}


def test_reconstruye_el_estado_y_el_tiempo_restante_paso_a_paso() -> None:
    pasos = construir_pasos(resultado_con_idle())

    assert len(pasos) == 4
    assert pasos[0].indice == 0
    assert pasos[0].tiempo == 0
    assert pasos[0].segmento is None
    inicial = _fichas(pasos[0])
    assert inicial["P001"].estado is EstadoProceso.LISTO
    assert inicial["P001"].tiempo_restante == 2
    assert inicial["P002"].estado is EstadoProceso.NUEVO
    assert inicial["P002"].tiempo_restante == 2

    tras_primero = _fichas(pasos[1])
    assert tras_primero["P001"].estado is EstadoProceso.TERMINADO
    assert tras_primero["P001"].tiempo_restante == 0
    assert tras_primero["P001"].tiempo_ejecutado == 2
    assert tras_primero["P002"].estado is EstadoProceso.NUEVO

    tras_idle = _fichas(pasos[2])
    assert tras_idle["P002"].estado is EstadoProceso.LISTO
    assert tras_idle["P002"].tiempo_restante == 2

    tras_segundo = _fichas(pasos[3])
    assert tras_segundo["P002"].estado is EstadoProceso.TERMINADO
    assert tras_segundo["P002"].tiempo_restante == 0


def test_el_estado_final_coincide_con_el_resultado_de_la_simulacion() -> None:
    resultado = resultado_con_idle()
    pasos = construir_pasos(resultado)

    finales = _fichas(pasos[-1])
    assert pasos[-1].tiempo == resultado.tiempo_total
    for item in resultado.resultados:
        ficha = finales[item.id_proceso]
        assert ficha.estado is EstadoProceso.TERMINADO
        assert ficha.tiempo_restante == 0
        assert ficha.tiempo_ejecutado == item.rafaga
    finalizaciones = {
        segmento.id_proceso: segmento.fin
        for segmento in resultado.segmentos
        if segmento.id_proceso is not None
    }
    assert finalizaciones == {
        item.id_proceso: item.tiempo_finalizacion for item in resultado.resultados
    }


def test_la_reproduccion_conserva_los_segmentos_idle() -> None:
    pasos = construir_pasos(resultado_con_idle())
    idle = [paso for paso in pasos if paso.segmento is not None and paso.segmento.es_inactivo]

    assert len(idle) == 1
    assert idle[0].segmento.inicio == 2
    assert idle[0].segmento.fin == 5
    assert "CPU inactivo" in idle[0].descripcion


def test_round_robin_reduce_el_tiempo_restante_en_cada_segmento() -> None:
    procesos = (crear_proceso("P001", 0, 4),)
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=2),
        SegmentoEjecucion("P001", inicio=2, fin=4),
    )
    resultado = calcular_metricas(segmentos, procesos, algoritmo=Algoritmo.ROUND_ROBIN)

    pasos = construir_pasos(resultado)
    primer_corte = pasos[1].procesos[0]
    segundo_corte = pasos[2].procesos[0]

    assert primer_corte.tiempo_restante == 2
    assert primer_corte.estado is EstadoProceso.LISTO
    assert segundo_corte.tiempo_restante == 0
    assert segundo_corte.estado is EstadoProceso.TERMINADO


def test_rechaza_un_segmento_que_referencia_un_proceso_desconocido() -> None:
    resultado = ResultadoSimulacion(
        algoritmo=Algoritmo.FIFO,
        segmentos=(SegmentoEjecucion("P999", inicio=0, fin=2),),
        resultados=(
            ResultadoProceso(
                id_proceso="P001",
                tiempo_llegada=0,
                rafaga=2,
                tiempo_finalizacion=2,
                tiempo_espera=0,
                tiempo_retorno=2,
                id_cola="normal",
            ),
        ),
        promedio_espera=0.0,
        promedio_retorno=2.0,
        tiempo_cpu_ocupado=2,
        tiempo_cpu_inactivo=0,
        tiempo_total=2,
        utilizacion_cpu=100.0,
    )

    with pytest.raises(ErrorValidacion, match="proceso desconocido"):
        construir_pasos(resultado)


def test_rechaza_una_traza_que_no_termina_todos_los_procesos() -> None:
    resultado = ResultadoSimulacion(
        algoritmo=Algoritmo.FIFO,
        segmentos=(
            SegmentoEjecucion("P001", inicio=0, fin=1),
            SegmentoEjecucion(None, inicio=1, fin=2),
        ),
        resultados=(
            ResultadoProceso(
                id_proceso="P001",
                tiempo_llegada=0,
                rafaga=1,
                tiempo_finalizacion=1,
                tiempo_espera=0,
                tiempo_retorno=1,
            ),
            ResultadoProceso(
                id_proceso="P002",
                tiempo_llegada=0,
                rafaga=1,
                tiempo_finalizacion=2,
                tiempo_espera=1,
                tiempo_retorno=2,
            ),
        ),
        promedio_espera=0.5,
        promedio_retorno=1.5,
        tiempo_cpu_ocupado=2,
        tiempo_cpu_inactivo=0,
        tiempo_total=2,
        utilizacion_cpu=100.0,
    )

    with pytest.raises(ErrorValidacion, match="no completó su ráfaga"):
        construir_pasos(resultado)
