"""Aplicación Streamlit para preparar, configurar y ejecutar la simulación."""

import streamlit as st

from simulador.presentacion.componentes import (
    renderizar_catalogo,
    renderizar_configuracion,
    renderizar_ejecucion,
    renderizar_procesos,
    renderizar_resultados,
    renderizar_resumen,
)
from simulador.presentacion.estado_sesion import obtener_estado


def main() -> None:
    """Construye la página y conserva carga, configuración y resultados en la sesión."""

    st.set_page_config(page_title="Simulador de planificación", layout="wide")
    st.title("Simulador de planificación de procesos")
    st.caption(
        "Cada tiquete de servicio es un proceso que compite por un único CPU simulado. "
        "Prepare la carga, configure las colas MLQ y ejecute los algoritmos."
    )

    estado = obtener_estado()
    renderizar_catalogo(estado)
    renderizar_procesos(estado)
    renderizar_resumen(estado)
    renderizar_configuracion(estado)
    renderizar_ejecucion(estado)
    renderizar_resultados(estado)


main()
