"""Pruebas del Gantt construido desde la traza."""

from simulador.presentacion.gantt import (
    COLOR_INACTIVO,
    ETIQUETA_INACTIVO,
    construir_figura_gantt,
)
from tests.presentacion.ayudas import resultado_con_idle


def test_el_gantt_reproduce_los_segmentos_del_motor_incluido_idle() -> None:
    resultado = resultado_con_idle()

    figura = construir_figura_gantt(resultado)
    (barras,) = figura.data

    assert list(barras.base) == [segmento.inicio for segmento in resultado.segmentos]
    assert list(barras.x) == [segmento.duracion for segmento in resultado.segmentos]
    assert list(barras.y) == ["P001", ETIQUETA_INACTIVO, "P002"]
    assert barras.marker.color[1] == COLOR_INACTIVO
    assert figura.layout.xaxis.range == (0, resultado.tiempo_total)
    assert ETIQUETA_INACTIVO in figura.layout.yaxis.categoryarray
