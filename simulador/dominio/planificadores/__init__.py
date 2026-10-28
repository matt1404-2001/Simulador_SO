"""Planificadores de CPU del dominio."""

from simulador.dominio.planificadores.base import (
    Planificador,
    copiar_carga,
    copiar_configuracion,
    copiar_procesos,
)

__all__ = [
    "Planificador",
    "copiar_carga",
    "copiar_configuracion",
    "copiar_procesos",
]
