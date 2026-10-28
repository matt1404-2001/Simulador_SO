"""Planificador FIFO no apropiativo."""

from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.modelos import ConfiguracionCola, Proceso, ResultadoSimulacion
from simulador.dominio.planificadores.base import Planificador, planificar_no_apropiativo


def _clave_fifo(proceso: Proceso) -> tuple[int, int, str]:
    """Ordena por llegada y desempata por ingreso e identificador."""

    return (proceso.tiempo_llegada, proceso.orden_ingreso, proceso.id_proceso)


class PlanificadorFIFO(Planificador):
    """Atiende primero al proceso listo que llegó antes.

    Es no apropiativo: el proceso elegido conserva el CPU hasta terminar, aunque
    durante su ejecución lleguen procesos más antiguos o más cortos.
    """

    def planificar(
        self,
        procesos: tuple[Proceso, ...],
        configuracion: tuple[ConfiguracionCola, ...],
    ) -> ResultadoSimulacion:
        """Planifica la carga en orden de llegada y devuelve traza y métricas."""

        return planificar_no_apropiativo(
            procesos,
            configuracion,
            algoritmo=Algoritmo.FIFO,
            seleccionar=lambda listos: min(listos, key=_clave_fifo),
        )
