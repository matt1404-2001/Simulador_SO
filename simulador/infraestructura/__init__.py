"""Adaptadores para archivos y otras fuentes externas."""

from simulador.infraestructura.clientes_csv import COLUMNAS_CLIENTES, cargar_clientes
from simulador.infraestructura.procesos_csv import COLUMNAS_PROCESOS, cargar_procesos

__all__ = [
    "COLUMNAS_CLIENTES",
    "COLUMNAS_PROCESOS",
    "cargar_clientes",
    "cargar_procesos",
]
