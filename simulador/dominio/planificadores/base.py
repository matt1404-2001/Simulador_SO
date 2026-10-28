"""Contrato común, utilidades de aislamiento y motor no apropiativo."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import replace

from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.metricas import calcular_metricas
from simulador.dominio.modelos import (
    ConfiguracionCola,
    Proceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
)

SelectorProceso = Callable[[list[Proceso]], Proceso]


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


def planificar_no_apropiativo(
    procesos: Iterable[Proceso],
    configuracion: Iterable[ConfiguracionCola],
    *,
    algoritmo: Algoritmo,
    seleccionar: SelectorProceso,
) -> ResultadoSimulacion:
    """Ejecuta una política no apropiativa sobre copias de la carga.

    En cada punto de despacho se entrega a `seleccionar` solo los procesos que ya
    llegaron y todavía no se ejecutaron. El proceso elegido ocupa el CPU hasta
    consumir toda su ráfaga, por lo que una llegada posterior no lo interrumpe.
    Los intervalos sin procesos listos se representan con un segmento IDLE.
    """

    procesos_copiados, configuracion_copiada = copiar_carga(procesos, configuracion)
    if not procesos_copiados:
        raise ErrorValidacion("no se puede planificar una carga sin procesos")

    pendientes = list(procesos_copiados)
    segmentos: list[SegmentoEjecucion] = []
    reloj = 0

    while pendientes:
        listos = [proceso for proceso in pendientes if proceso.tiempo_llegada <= reloj]
        if not listos:
            siguiente_llegada = min(proceso.tiempo_llegada for proceso in pendientes)
            segmentos.append(SegmentoEjecucion(None, inicio=reloj, fin=siguiente_llegada))
            reloj = siguiente_llegada
            continue

        proceso = seleccionar(listos)
        fin = reloj + proceso.rafaga
        segmentos.append(
            SegmentoEjecucion(
                proceso.id_proceso,
                inicio=reloj,
                fin=fin,
                id_cola=proceso.id_cola,
            )
        )
        reloj = fin
        pendientes.remove(proceso)

    return calcular_metricas(
        segmentos,
        procesos_copiados,
        algoritmo=algoritmo,
        configuraciones_colas=configuracion_copiada,
    )


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
