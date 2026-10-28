"""Modelos y reglas independientes de la interfaz y la persistencia."""

from simulador.dominio.enumeraciones import Algoritmo, EstadoProceso, Servicio, TipoCliente
from simulador.dominio.excepciones import ErrorConfiguracion, ErrorDominio, ErrorValidacion
from simulador.dominio.modelos import (
    Cliente,
    ConfiguracionCola,
    Proceso,
    ResultadoProceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
)

__all__ = [
    "Algoritmo",
    "Cliente",
    "ConfiguracionCola",
    "ErrorConfiguracion",
    "ErrorDominio",
    "ErrorValidacion",
    "EstadoProceso",
    "Proceso",
    "ResultadoProceso",
    "ResultadoSimulacion",
    "SegmentoEjecucion",
    "Servicio",
    "TipoCliente",
]
