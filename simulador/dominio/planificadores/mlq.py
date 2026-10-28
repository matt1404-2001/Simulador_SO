"""Planificador MLQ de colas fijas con prioridad entre colas."""

from collections import deque
from collections.abc import Iterable

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


def _clave_sjf(proceso: Proceso) -> tuple[int, int, int, str]:
    """Ordena por menor ráfaga y desempata por llegada, ingreso e identificador."""

    return (
        proceso.rafaga,
        proceso.tiempo_llegada,
        proceso.orden_ingreso,
        proceso.id_proceso,
    )


class _ColaMLQ:
    """Estado de despacho de una cola fija durante una ejecución MLQ.

    Conserva los procesos que ya llegaron y su tiempo restante para que Round
    Robin pueda repartir la ráfaga en varios turnos sin alterar la carga
    original. La prioridad y el índice se usan para elegir entre colas.
    """

    def __init__(self, configuracion: ConfiguracionCola, orden: int) -> None:
        self.configuracion = configuracion
        self.orden = orden
        self._es_round_robin = configuracion.algoritmo is Algoritmo.ROUND_ROBIN
        self._listos: list[Proceso] = []
        self._circular: deque[str] = deque()
        self._procesos: dict[str, Proceso] = {}
        self._restante: dict[str, int] = {}

    @property
    def id_cola(self) -> str:
        """Identificador de la cola configurada."""

        return self.configuracion.id_cola

    @property
    def clave_prioridad(self) -> tuple[int, int]:
        """Ordena por prioridad y desempata por el índice en la configuración."""

        return (self.configuracion.prioridad_cola, self.orden)

    @property
    def esta_vacia(self) -> bool:
        """Indica si la cola no tiene procesos esperando despacho."""

        if self._es_round_robin:
            return not self._circular
        return not self._listos

    @property
    def _quantum(self) -> int:
        """Quantum de la cola; toda cola Round Robin lo exige."""

        if self.configuracion.quantum is None:
            raise ErrorConfiguracion(f"la cola {self.id_cola} requiere quantum para Round Robin")
        return self.configuracion.quantum

    def incorporar(self, proceso: Proceso) -> None:
        """Agrega un proceso recién llegado al final de la cola."""

        self._procesos[proceso.id_proceso] = proceso
        self._restante[proceso.id_proceso] = proceso.rafaga
        if self._es_round_robin:
            self._circular.append(proceso.id_proceso)
        else:
            self._listos.append(proceso)

    def tomar(self) -> tuple[Proceso, int]:
        """Extrae el proceso a despachar y la duración de su próximo segmento."""

        if self._es_round_robin:
            id_proceso = self._circular.popleft()
        else:
            seleccionado = min(self._listos, key=self._clave_seleccion)
            self._listos.remove(seleccionado)
            id_proceso = seleccionado.id_proceso

        proceso = self._procesos[id_proceso]
        restante = self._restante[id_proceso]
        if self._es_round_robin:
            return proceso, min(self._quantum, restante)
        return proceso, restante

    def completar(self, proceso: Proceso, ejecucion: int) -> bool:
        """Descuenta el segmento ejecutado e indica si el proceso debe reingresar."""

        self._restante[proceso.id_proceso] -= ejecucion
        return self._restante[proceso.id_proceso] > 0

    def reingresar(self, proceso: Proceso) -> None:
        """Devuelve al final de la cola circular un proceso interrumpido."""

        self._circular.append(proceso.id_proceso)

    def _clave_seleccion(self, proceso: Proceso) -> tuple[int, ...]:
        """Aplica el criterio del algoritmo configurado para la cola."""

        if self.configuracion.algoritmo is Algoritmo.SJF:
            return _clave_sjf(proceso)
        return _clave_llegada(proceso)


class PlanificadorMLQ(Planificador):
    """Integra FIFO, SJF y Round Robin en colas fijas con prioridad entre colas.

    Cada proceso pertenece a una única cola y no cambia de ella. En cada punto de
    despacho se elige la cola no vacía con menor `prioridad_cola`; si empatan, la
    de menor índice en la configuración. Dentro de la cola se aplica su
    algoritmo. Las ejecuciones FIFO y SJF no se interrumpen por llegadas a colas
    superiores: las colas solo se reevalúan al terminar un proceso o un quantum
    de Round Robin.
    """

    def planificar(
        self,
        procesos: tuple[Proceso, ...],
        configuracion: tuple[ConfiguracionCola, ...],
    ) -> ResultadoSimulacion:
        """Planifica la carga por colas fijas y devuelve traza y métricas."""

        procesos_copiados, configuracion_copiada = copiar_carga(procesos, configuracion)
        if not procesos_copiados:
            raise ErrorValidacion("no se puede planificar una carga sin procesos")

        colas = self._construir_colas(configuracion_copiada)
        pendientes = sorted(procesos_copiados, key=_clave_llegada)
        self._validar_procesos(pendientes, colas)

        segmentos: list[SegmentoEjecucion] = []
        reloj = 0
        siguiente = 0

        while True:
            siguiente = self._incorporar_llegadas(pendientes, siguiente, reloj, colas)
            if siguiente >= len(pendientes) and not any(
                not cola.esta_vacia for cola in colas.values()
            ):
                break

            cola = self._seleccionar_cola(colas.values())
            if cola is None:
                llegada = pendientes[siguiente].tiempo_llegada
                segmentos.append(SegmentoEjecucion(None, inicio=reloj, fin=llegada))
                reloj = llegada
                continue

            proceso, ejecucion = cola.tomar()
            fin = reloj + ejecucion
            segmentos.append(
                SegmentoEjecucion(
                    proceso.id_proceso,
                    inicio=reloj,
                    fin=fin,
                    id_cola=proceso.id_cola,
                )
            )
            reloj = fin

            if cola.completar(proceso, ejecucion):
                # Las llegadas del turno entran antes de devolver al proceso al
                # final de la cola circular, igual que en Round Robin aislado.
                siguiente = self._incorporar_llegadas(pendientes, siguiente, reloj, colas)
                cola.reingresar(proceso)

        return calcular_metricas(
            segmentos,
            procesos_copiados,
            algoritmo=Algoritmo.MLQ,
            configuraciones_colas=configuracion_copiada,
        )

    @staticmethod
    def _construir_colas(
        configuracion: tuple[ConfiguracionCola, ...],
    ) -> dict[str, _ColaMLQ]:
        """Crea el estado de cada cola respetando su índice de configuración."""

        colas: dict[str, _ColaMLQ] = {}
        for orden, cola in enumerate(configuracion):
            if cola.id_cola in colas:
                raise ErrorConfiguracion(
                    f"la configuración contiene la cola duplicada {cola.id_cola}"
                )
            colas[cola.id_cola] = _ColaMLQ(cola, orden)
        return colas

    @staticmethod
    def _validar_procesos(
        procesos: Iterable[Proceso],
        colas: dict[str, _ColaMLQ],
    ) -> None:
        """Rechaza identificadores repetidos y procesos sin cola configurada."""

        identificadores = [proceso.id_proceso for proceso in procesos]
        if len(set(identificadores)) != len(identificadores):
            raise ErrorValidacion("la carga contiene identificadores de proceso duplicados")

        for proceso in procesos:
            if proceso.id_cola not in colas:
                raise ErrorValidacion(
                    f"el proceso {proceso.id_proceso} no tiene una cola configurada: "
                    f"{proceso.id_cola}"
                )

    @staticmethod
    def _incorporar_llegadas(
        pendientes: list[Proceso],
        siguiente: int,
        reloj: int,
        colas: dict[str, _ColaMLQ],
    ) -> int:
        """Agrega a su cola los procesos cuya llegada ya ocurrió."""

        while siguiente < len(pendientes) and pendientes[siguiente].tiempo_llegada <= reloj:
            proceso = pendientes[siguiente]
            colas[proceso.id_cola].incorporar(proceso)
            siguiente += 1
        return siguiente

    @staticmethod
    def _seleccionar_cola(colas: Iterable[_ColaMLQ]) -> _ColaMLQ | None:
        """Devuelve la cola no vacía de mayor prioridad o None si no hay trabajo."""

        disponibles = [cola for cola in colas if not cola.esta_vacia]
        if not disponibles:
            return None
        return min(disponibles, key=lambda cola: cola.clave_prioridad)
