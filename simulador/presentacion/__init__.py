"""Componentes de presentación de la aplicación web."""

from simulador.presentacion.estado_sesion import (
    CLAVE_ESTADO_SESION,
    EstadoSesion,
    obtener_estado,
    reiniciar_estado,
)

__all__ = [
    "CLAVE_ESTADO_SESION",
    "EstadoSesion",
    "obtener_estado",
    "reiniciar_estado",
]
