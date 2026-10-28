"""Planificador SJF no apropiativo."""

from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.modelos import ConfiguracionCola, Proceso, ResultadoSimulacion
from simulador.dominio.planificadores.base import Planificador, planificar_no_apropiativo


def _clave_sjf(proceso: Proceso) -> tuple[int, int, int, str]:
    """Ordena por menor ráfaga y desempata por llegada, ingreso e identificador."""

    return (
        proceso.rafaga,
        proceso.tiempo_llegada,
        proceso.orden_ingreso,
        proceso.id_proceso,
    )


class PlanificadorSJF(Planificador):
    """Atiende primero al proceso listo con la ráfaga más corta.

    Solo considera procesos que ya llegaron. Es no apropiativo: la ráfaga se
    elige en cada punto de despacho y el proceso elegido no se interrumpe.
    """

    def planificar(
        self,
        procesos: tuple[Proceso, ...],
        configuracion: tuple[ConfiguracionCola, ...],
    ) -> ResultadoSimulacion:
        """Planifica la carga por menor ráfaga y devuelve traza y métricas."""

        return planificar_no_apropiativo(
            procesos,
            configuracion,
            algoritmo=Algoritmo.SJF,
            seleccionar=lambda listos: min(listos, key=_clave_sjf),
        )
