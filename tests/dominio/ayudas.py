"""Utilidades compartidas por las pruebas de los planificadores."""

from itertools import pairwise

from simulador.dominio import Proceso, ResultadoSimulacion, Servicio


def crear_proceso(
    id_proceso: str,
    tiempo_llegada: int,
    rafaga: int,
    *,
    orden_ingreso: int = 0,
    id_cola: str = "normal",
) -> Proceso:
    """Crea un proceso mínimo con los datos necesarios para planificar."""

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


def describir_segmentos(resultado: ResultadoSimulacion) -> list[tuple[str, int, int]]:
    """Devuelve cada segmento como una tupla (etiqueta, inicio, fin)."""

    return [(segmento.etiqueta, segmento.inicio, segmento.fin) for segmento in resultado.segmentos]


def verificar_invariantes(resultado: ResultadoSimulacion) -> None:
    """Comprueba continuidad del reloj, ráfagas exactas y respeto de llegadas."""

    segmentos = resultado.segmentos
    assert segmentos[0].inicio == 0

    for anterior, siguiente in pairwise(segmentos):
        assert anterior.fin == siguiente.inicio

    llegadas = {
        resultado_proceso.id_proceso: resultado_proceso.tiempo_llegada
        for resultado_proceso in resultado.resultados
    }
    ejecutado: dict[str, int] = {}
    for segmento in segmentos:
        if segmento.id_proceso is None:
            continue
        assert segmento.inicio >= llegadas[segmento.id_proceso]
        ejecutado[segmento.id_proceso] = ejecutado.get(segmento.id_proceso, 0) + segmento.duracion

    assert ejecutado == {
        resultado_proceso.id_proceso: resultado_proceso.rafaga
        for resultado_proceso in resultado.resultados
    }
