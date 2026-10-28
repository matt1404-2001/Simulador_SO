"""Gantt Plotly construido directamente desde la traza del motor."""

import plotly.graph_objects as go
import streamlit as st

from simulador.dominio.modelos import ResultadoSimulacion

COLORES_PROCESO = (
    "#2f6db3",
    "#d97706",
    "#2e8b57",
    "#b03a8c",
    "#7c5cbf",
    "#0f8b8d",
    "#c2413b",
    "#8a6d3b",
)
COLOR_INACTIVO = "#9aa0a6"
ETIQUETA_INACTIVO = "CPU inactivo"


def construir_figura_gantt(resultado: ResultadoSimulacion) -> go.Figure:
    """Construye un Gantt con una fila por proceso y otra para la inactividad.

    Cada barra reproduce un segmento de la traza sin modificarlo: el inicio se
    toma como base y la duración como ancho. Los segmentos ``IDLE`` se agrupan en
    una fila propia para que la inactividad del CPU sea visible.
    """

    identificadores = [item.id_proceso for item in resultado.resultados]
    colores = {
        id_proceso: COLORES_PROCESO[posicion % len(COLORES_PROCESO)]
        for posicion, id_proceso in enumerate(identificadores)
    }

    bases: list[int] = []
    duraciones: list[int] = []
    filas: list[str] = []
    colores_barras: list[str] = []
    etiquetas: list[str] = []
    detalles: list[tuple[int, int, int, str]] = []

    for segmento in resultado.segmentos:
        fila = ETIQUETA_INACTIVO if segmento.es_inactivo else segmento.etiqueta
        bases.append(segmento.inicio)
        duraciones.append(segmento.duracion)
        filas.append(fila)
        colores_barras.append(COLOR_INACTIVO if segmento.es_inactivo else colores[fila])
        etiquetas.append(segmento.etiqueta)
        detalles.append(
            (
                segmento.inicio,
                segmento.fin,
                segmento.duracion,
                segmento.id_cola or "no aplica",
            )
        )

    categorias = list(identificadores)
    if any(segmento.es_inactivo for segmento in resultado.segmentos):
        categorias.append(ETIQUETA_INACTIVO)

    figura = go.Figure(
        go.Bar(
            orientation="h",
            x=duraciones,
            base=bases,
            y=filas,
            marker={"color": colores_barras, "line": {"color": "#ffffff", "width": 1}},
            text=etiquetas,
            textposition="inside",
            insidetextanchor="middle",
            customdata=detalles,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Inicio: %{customdata[0]}<br>"
                "Fin: %{customdata[1]}<br>"
                "Duración: %{customdata[2]}<br>"
                "Cola: %{customdata[3]}<extra></extra>"
            ),
            width=0.7,
        )
    )
    figura.update_layout(
        title={"text": f"Gantt de la traza ({resultado.algoritmo.value})", "x": 0.01},
        showlegend=False,
        bargap=0.2,
        height=max(280, 120 + 45 * len(categorias)),
        margin={"l": 20, "r": 20, "t": 60, "b": 40},
        xaxis={
            "title": "Tiempo",
            "rangemode": "tozero",
            "range": [0, resultado.tiempo_total],
            "dtick": _paso_eje(resultado.tiempo_total),
        },
        yaxis={
            "title": "",
            "categoryorder": "array",
            "categoryarray": categorias,
            "autorange": "reversed",
        },
    )
    return figura


def renderizar_gantt(resultado: ResultadoSimulacion) -> None:
    """Muestra el Gantt Plotly de una ejecución vigente."""

    st.plotly_chart(construir_figura_gantt(resultado))


def _paso_eje(tiempo_total: int) -> int:
    """Elige una separación legible para el eje temporal."""

    if tiempo_total <= 20:
        return 1
    if tiempo_total <= 60:
        return 5
    return 10
