"""Aplicación Streamlit para preparar la carga de la simulación."""

import streamlit as st

from simulador.presentacion.componentes import (
    renderizar_catalogo,
    renderizar_procesos,
    renderizar_resumen,
)
from simulador.presentacion.estado_sesion import obtener_estado


def main() -> None:
    """Construye la página y conserva la carga en la sesión de Streamlit."""

    st.set_page_config(page_title="Simulador de planificación", layout="wide")
    st.title("Simulador de planificación de procesos")
    st.caption(
        "Cada tiquete de servicio es un proceso que compite por un único CPU simulado. "
        "En esta etapa se prepara la carga que luego se planificará."
    )

    estado = obtener_estado()
    renderizar_catalogo(estado)
    renderizar_procesos(estado)
    renderizar_resumen(estado)


main()
