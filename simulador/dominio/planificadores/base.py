"""Contrato común y utilidades de aislamiento para los planificadores."""

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import replace

from simulador.dominio.modelos import ConfiguracionCola, Proceso, ResultadoSimulacion


def copiar_procesos(procesos: Iterable[Proceso]) -> tuple[Proceso, ...]:
    """Devuelve copias independientes de los procesos recibidos."""

    return tuple(replace(proceso) for proceso in procesos)


def copiar_configuracion(
    configuracion: Iterable[ConfiguracionCola],
) -> tuple[ConfiguracionCola, ...]:
    """Devuelve copias independientes de las colas recibidas."""

    return tuple(replace(cola) for cola in configuracion)


def copiar_carga(
    procesos: Iterable[Proceso],
    configuracion: Iterable[ConfiguracionCola],
) -> tuple[tuple[Proceso, ...], tuple[ConfiguracionCola, ...]]:
    """Copia la carga completa para que una ejecución no altere el original."""

    return copiar_procesos(procesos), copiar_configuracion(configuracion)


class Planificador(ABC):
    """Contrato común de los algoritmos de planificación de CPU."""

    @abstractmethod
    def planificar(
        self,
        procesos: tuple[Proceso, ...],
        configuracion: tuple[ConfiguracionCola, ...],
    ) -> ResultadoSimulacion:
        """Planifica una copia de la carga y devuelve la traza con sus métricas."""
        raise NotImplementedError
