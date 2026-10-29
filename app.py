"""Aplicación Streamlit para preparar, configurar y ejecutar la simulación."""

import streamlit as st

from simulador.dominio.excepciones import ErrorValidacion
from simulador.presentacion.componentes import (
    renderizar_catalogo,
    renderizar_configuracion,
    renderizar_ejecucion,
    renderizar_procesos,
    renderizar_resultados,
    renderizar_resumen,
)
from simulador.presentacion.estado_sesion import EstadoSesion, obtener_estado


def _carga_lista(estado: EstadoSesion) -> bool:
    """Indica si la carga puede pasar a configuración y ejecución."""

    try:
        estado.validar_cantidad()
    except ErrorValidacion:
        return False
    return True


def _hay_resultados(estado: EstadoSesion) -> bool:
    """Indica si existe algún resultado vigente para mostrar."""

    return any(
        resultado is not None
        for resultado in (
            estado.resultado_individual,
            estado.resultado_mlq,
            estado.comparacion,
        )
    )


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

    if not estado.clientes:
        return

    renderizar_procesos(estado)
    renderizar_resumen(estado)

    if not _carga_lista(estado):
        return

    renderizar_configuracion(estado)
    renderizar_ejecucion(estado)
    if _hay_resultados(estado):
        renderizar_resultados(estado)


main()
