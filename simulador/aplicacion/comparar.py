"""Comparación de FIFO, SJF y Round Robin sobre una misma carga."""

from collections.abc import Iterable
from dataclasses import dataclass

from simulador.aplicacion.simular import preparar_carga
from simulador.dominio.modelos import Proceso, ResultadoSimulacion
from simulador.dominio.planificadores import (
    PlanificadorFIFO,
    PlanificadorRoundRobin,
    PlanificadorSJF,
)


@dataclass(frozen=True, slots=True)
class Comparacion:
    """Resultados independientes de los tres algoritmos comparables."""

    fifo: ResultadoSimulacion
    sjf: ResultadoSimulacion
    round_robin: ResultadoSimulacion

    @property
    def resultados(self) -> tuple[ResultadoSimulacion, ...]:
        """Devuelve los resultados en el orden FIFO, SJF y Round Robin."""

        return (self.fifo, self.sjf, self.round_robin)


def comparar_algoritmos(
    procesos: Iterable[Proceso],
    *,
    quantum: int,
) -> Comparacion:
    """Ejecuta FIFO, SJF y Round Robin sobre copias equivalentes de la carga.

    El quantum solo interviene en Round Robin y debe ser un entero positivo. Cada
    planificador copia la carga antes de planificar, de modo que los resultados no
    comparten estado mutable entre sí ni con la carga original.
    """

    procesos_copiados, _ = preparar_carga(procesos)
    planificador_round_robin = PlanificadorRoundRobin(quantum)

    return Comparacion(
        fifo=PlanificadorFIFO().planificar(procesos_copiados, ()),
        sjf=PlanificadorSJF().planificar(procesos_copiados, ()),
        round_robin=planificador_round_robin.planificar(procesos_copiados, ()),
    )
