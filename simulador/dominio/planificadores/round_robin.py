"""Planificador Round Robin apropiativo por quantum."""

from collections import deque

from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.excepciones import ErrorConfiguracion, ErrorValidacion
from simulador.dominio.metricas import calcular_metricas
from simulador.dominio.modelos import (
    ConfiguracionCola,
    Proceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
)
from simulador.dominio.planificadores.base import Planificador, copiar_carga


def _clave_llegada(proceso: Proceso) -> tuple[int, int, str]:
    """Ordena por llegada y desempata por ingreso e identificador."""

    return (proceso.tiempo_llegada, proceso.orden_ingreso, proceso.id_proceso)


def _validar_quantum(quantum: object) -> int:
    """Rechaza quanta que no sean enteros positivos."""

    if isinstance(quantum, bool) or not isinstance(quantum, int):
        raise ErrorConfiguracion("quantum debe ser un número entero")
    if quantum <= 0:
        raise ErrorConfiguracion("quantum debe ser mayor que cero")
    return quantum


class PlanificadorRoundRobin(Planificador):
    """Alterna el CPU entre los procesos listos en turnos de tamaño fijo.

    La cola de listos respeta el orden FIFO de llegada. Cada turno ejecuta
    `min(quantum, tiempo_restante)`. Las llegadas ocurridas durante un turno se
    incorporan antes de devolver al final de la cola al proceso interrumpido, de
    modo que un recién llegado no queda detrás del proceso que ya venía esperando.
    """

    def __init__(self, quantum: int) -> None:
        self.quantum = _validar_quantum(quantum)

    def planificar(
        self,
        procesos: tuple[Proceso, ...],
        configuracion: tuple[ConfiguracionCola, ...],
    ) -> ResultadoSimulacion:
        """Planifica la carga por turnos y devuelve traza y métricas."""

        procesos_copiados, configuracion_copiada = copiar_carga(procesos, configuracion)
        if not procesos_copiados:
            raise ErrorValidacion("no se puede planificar una carga sin procesos")

        pendientes = sorted(procesos_copiados, key=_clave_llegada)
        indice = {proceso.id_proceso: proceso for proceso in pendientes}
        if len(indice) != len(pendientes):
            raise ErrorValidacion("la carga contiene identificadores de proceso duplicados")

        restante = {proceso.id_proceso: proceso.rafaga for proceso in pendientes}
        cola: deque[str] = deque()
        segmentos: list[SegmentoEjecucion] = []
        reloj = 0
        siguiente_llegada = 0

        while siguiente_llegada < len(pendientes) or cola:
            while (
                siguiente_llegada < len(pendientes)
                and pendientes[siguiente_llegada].tiempo_llegada <= reloj
            ):
                cola.append(pendientes[siguiente_llegada].id_proceso)
                siguiente_llegada += 1

            if not cola:
                llegada = pendientes[siguiente_llegada].tiempo_llegada
                segmentos.append(SegmentoEjecucion(None, inicio=reloj, fin=llegada))
                reloj = llegada
                continue

            id_proceso = cola.popleft()
            ejecucion = min(self.quantum, restante[id_proceso])
            fin = reloj + ejecucion
            segmentos.append(
                SegmentoEjecucion(
                    id_proceso,
                    inicio=reloj,
                    fin=fin,
                    id_cola=indice[id_proceso].id_cola,
                )
            )
            reloj = fin
            restante[id_proceso] -= ejecucion

            while (
                siguiente_llegada < len(pendientes)
                and pendientes[siguiente_llegada].tiempo_llegada <= reloj
            ):
                cola.append(pendientes[siguiente_llegada].id_proceso)
                siguiente_llegada += 1

            if restante[id_proceso] > 0:
                cola.append(id_proceso)

        return calcular_metricas(
            segmentos,
            procesos_copiados,
            algoritmo=Algoritmo.ROUND_ROBIN,
            configuraciones_colas=configuracion_copiada,
        )
