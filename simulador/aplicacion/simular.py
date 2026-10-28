"""Casos de uso para preparar una carga y ejecutar los algoritmos."""

from collections.abc import Iterable

from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.excepciones import ErrorConfiguracion, ErrorValidacion
from simulador.dominio.modelos import ConfiguracionCola, Proceso, ResultadoSimulacion
from simulador.dominio.planificadores import (
    Planificador,
    PlanificadorFIFO,
    PlanificadorMLQ,
    PlanificadorRoundRobin,
    PlanificadorSJF,
)
from simulador.dominio.planificadores.base import copiar_configuracion, copiar_procesos


def preparar_carga(
    procesos: Iterable[Proceso],
    configuracion: Iterable[ConfiguracionCola] = (),
) -> tuple[tuple[Proceso, ...], tuple[ConfiguracionCola, ...]]:
    """Valida la carga y devuelve copias independientes de procesos y colas.

    Rechaza cargas vacías, elementos ajenos al dominio e identificadores de
    proceso o de cola repetidos. No exige que las colas cubran todos los
    procesos: esa comprobación corresponde a MLQ.
    """

    procesos_recibidos = tuple(procesos)
    if not procesos_recibidos:
        raise ErrorValidacion("no se puede ejecutar una carga sin procesos")
    if any(not isinstance(proceso, Proceso) for proceso in procesos_recibidos):
        raise ErrorValidacion("la carga contiene un proceso inválido")

    identificadores = [proceso.id_proceso for proceso in procesos_recibidos]
    if len(set(identificadores)) != len(identificadores):
        raise ErrorValidacion("la carga contiene identificadores de proceso duplicados")

    configuracion_recibida = tuple(configuracion)
    if any(not isinstance(cola, ConfiguracionCola) for cola in configuracion_recibida):
        raise ErrorConfiguracion("la configuración contiene una cola inválida")

    identificadores_cola = [cola.id_cola for cola in configuracion_recibida]
    if len(set(identificadores_cola)) != len(identificadores_cola):
        raise ErrorConfiguracion("la configuración contiene colas duplicadas")

    return copiar_procesos(procesos_recibidos), copiar_configuracion(configuracion_recibida)


def _crear_planificador(algoritmo: Algoritmo, quantum: int | None) -> Planificador:
    """Construye el planificador individual y valida su quantum."""

    if algoritmo is Algoritmo.ROUND_ROBIN:
        if quantum is None:
            raise ErrorConfiguracion("Round Robin requiere quantum")
        return PlanificadorRoundRobin(quantum)

    if quantum is not None:
        raise ErrorConfiguracion("quantum solo se configura para Round Robin")

    if algoritmo is Algoritmo.FIFO:
        return PlanificadorFIFO()
    if algoritmo is Algoritmo.SJF:
        return PlanificadorSJF()
    raise ErrorConfiguracion(f"algoritmo no soportado para ejecución individual: {algoritmo}")


def ejecutar_algoritmo(
    procesos: Iterable[Proceso],
    algoritmo: Algoritmo,
    *,
    quantum: int | None = None,
    configuracion: Iterable[ConfiguracionCola] = (),
) -> ResultadoSimulacion:
    """Ejecuta un algoritmo individual o una configuración MLQ sobre una copia.

    `quantum` solo aplica a Round Robin individual. MLQ toma el quantum de cada
    cola configurada, por lo que rechaza un quantum global.
    """

    if not isinstance(algoritmo, Algoritmo):
        raise ErrorConfiguracion("algoritmo debe ser un Algoritmo válido")

    procesos_copiados, configuracion_copiada = preparar_carga(procesos, configuracion)

    if algoritmo is Algoritmo.MLQ:
        if quantum is not None:
            raise ErrorConfiguracion("MLQ usa el quantum de cada cola configurada")
        return PlanificadorMLQ().planificar(procesos_copiados, configuracion_copiada)

    planificador = _crear_planificador(algoritmo, quantum)
    return planificador.planificar(procesos_copiados, configuracion_copiada)
