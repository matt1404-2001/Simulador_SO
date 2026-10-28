"""Planificadores de CPU del dominio."""

from simulador.dominio.planificadores.base import (
    Planificador,
    copiar_carga,
    copiar_configuracion,
    copiar_procesos,
    planificar_no_apropiativo,
)
from simulador.dominio.planificadores.fifo import PlanificadorFIFO
from simulador.dominio.planificadores.sjf import PlanificadorSJF

__all__ = [
    "Planificador",
    "PlanificadorFIFO",
    "PlanificadorSJF",
    "copiar_carga",
    "copiar_configuracion",
    "copiar_procesos",
    "planificar_no_apropiativo",
]
