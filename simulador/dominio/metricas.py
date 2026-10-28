"""Construcción de trazas y cálculo de métricas de una simulación."""

from collections.abc import Iterable

from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.modelos import (
    ConfiguracionCola,
    Proceso,
    ResultadoProceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
)


def _convertir_segmentos(
    segmentos: Iterable[SegmentoEjecucion],
) -> tuple[SegmentoEjecucion, ...]:
    traza = tuple(segmentos)
    if not traza:
        raise ErrorValidacion("la traza debe contener al menos un segmento")
    if any(not isinstance(segmento, SegmentoEjecucion) for segmento in traza):
        raise ErrorValidacion("la traza contiene un segmento inválido")
    return traza


def _indexar_procesos(procesos: Iterable[Proceso]) -> dict[str, Proceso]:
    indice: dict[str, Proceso] = {}
    for proceso in procesos:
        if not isinstance(proceso, Proceso):
            raise ErrorValidacion("la carga contiene un proceso inválido")
        if proceso.id_proceso in indice:
            raise ErrorValidacion(f"el proceso {proceso.id_proceso} está duplicado")
        indice[proceso.id_proceso] = proceso
    return indice


def validar_traza(
    segmentos: Iterable[SegmentoEjecucion],
    procesos: Iterable[Proceso],
) -> tuple[SegmentoEjecucion, ...]:
    """Valida una traza cronológica y la devuelve en el orden recibido.

    Rechaza retrocesos del reloj, superposiciones, huecos sin segmento IDLE,
    procesos desconocidos y ejecuciones anteriores a la llegada o superiores a
    la ráfaga. No exige que todos los procesos hayan terminado.
    """

    traza = _convertir_segmentos(segmentos)
    indice = _indexar_procesos(procesos)
    ejecutado: dict[str, int] = {}

    for segmento in traza:
        if segmento.id_proceso is None:
            continue

        proceso = indice.get(segmento.id_proceso)
        if proceso is None:
            raise ErrorValidacion(
                f"el segmento referencia un proceso desconocido: {segmento.id_proceso}"
            )
        if segmento.inicio < proceso.tiempo_llegada:
            raise ErrorValidacion(
                f"el proceso {proceso.id_proceso} se ejecuta antes de su tiempo de llegada"
            )
        if segmento.id_cola is not None and segmento.id_cola != proceso.id_cola:
            raise ErrorValidacion(
                f"el segmento de {proceso.id_proceso} no coincide con su cola {proceso.id_cola}"
            )

        acumulado = ejecutado.get(proceso.id_proceso, 0) + segmento.duracion
        if acumulado > proceso.rafaga:
            raise ErrorValidacion(f"el proceso {proceso.id_proceso} excede su ráfaga")
        ejecutado[proceso.id_proceso] = acumulado

    anterior: SegmentoEjecucion | None = None
    for segmento in traza:
        if anterior is not None:
            if segmento.inicio < anterior.inicio:
                raise ErrorValidacion(
                    f"el reloj retrocede de {anterior.inicio} a {segmento.inicio}"
                )
            if segmento.inicio < anterior.fin:
                raise ErrorValidacion(
                    f"los segmentos {anterior.inicio}-{anterior.fin} y "
                    f"{segmento.inicio}-{segmento.fin} se superponen"
                )
            if segmento.inicio > anterior.fin:
                raise ErrorValidacion(
                    f"falta un segmento IDLE entre {anterior.fin} y {segmento.inicio}"
                )
        anterior = segmento

    if traza[0].inicio != 0:
        raise ErrorValidacion("la traza debe comenzar en 0")

    return traza


def construir_traza(
    segmentos: Iterable[SegmentoEjecucion],
    procesos: Iterable[Proceso],
) -> tuple[SegmentoEjecucion, ...]:
    """Ordena los segmentos y valida que formen una traza continua desde cero."""

    traza = tuple(sorted(_convertir_segmentos(segmentos), key=lambda segmento: segmento.inicio))
    return validar_traza(traza, procesos)


def _calcular_resultados(
    traza: tuple[SegmentoEjecucion, ...],
    procesos: tuple[Proceso, ...],
) -> tuple[ResultadoProceso, ...]:
    indice = _indexar_procesos(procesos)
    ejecutado = {id_proceso: 0 for id_proceso in indice}
    finalizacion = {id_proceso: 0 for id_proceso in indice}

    for segmento in traza:
        if segmento.id_proceso is None:
            continue
        ejecutado[segmento.id_proceso] += segmento.duracion
        finalizacion[segmento.id_proceso] = max(
            finalizacion[segmento.id_proceso],
            segmento.fin,
        )

    resultados: list[ResultadoProceso] = []
    for proceso in procesos:
        if ejecutado[proceso.id_proceso] != proceso.rafaga:
            raise ErrorValidacion(
                f"el proceso {proceso.id_proceso} no completó su ráfaga en la traza"
            )

        tiempo_retorno = finalizacion[proceso.id_proceso] - proceso.tiempo_llegada
        resultados.append(
            ResultadoProceso(
                id_proceso=proceso.id_proceso,
                tiempo_llegada=proceso.tiempo_llegada,
                rafaga=proceso.rafaga,
                tiempo_finalizacion=finalizacion[proceso.id_proceso],
                tiempo_espera=tiempo_retorno - proceso.rafaga,
                tiempo_retorno=tiempo_retorno,
                id_cola=proceso.id_cola,
            )
        )

    return tuple(
        sorted(
            resultados,
            key=lambda resultado: (
                indice[resultado.id_proceso].orden_ingreso,
                resultado.id_proceso,
            ),
        )
    )


def calcular_resultados(
    segmentos: Iterable[SegmentoEjecucion],
    procesos: Iterable[Proceso],
) -> tuple[ResultadoProceso, ...]:
    """Calcula el resultado de cada proceso a partir de una traza terminada.

    Todos los procesos recibidos deben haber consumido exactamente su ráfaga.
    El orden de los resultados se determina por `orden_ingreso` y `id_proceso`.
    """

    procesos_tuple = tuple(procesos)
    traza = construir_traza(segmentos, procesos_tuple)
    return _calcular_resultados(traza, procesos_tuple)


def calcular_metricas(
    segmentos: Iterable[SegmentoEjecucion],
    procesos: Iterable[Proceso],
    *,
    algoritmo: Algoritmo,
    configuraciones_colas: Iterable[ConfiguracionCola] = (),
) -> ResultadoSimulacion:
    """Consolida traza, resultados individuales y métricas globales.

    La traza debe estar terminada: cada proceso tiene que haber consumido su
    ráfaga completa. Los intervalos inactivos se cuentan como tiempo de CPU
    inactivo y forman parte del tiempo total.
    """

    procesos_tuple = tuple(procesos)
    if not procesos_tuple:
        raise ErrorValidacion("no se pueden calcular métricas sin procesos")

    traza = construir_traza(segmentos, procesos_tuple)
    resultados = _calcular_resultados(traza, procesos_tuple)

    cantidad_procesos = len(resultados)
    tiempo_cpu_ocupado = sum(segmento.duracion for segmento in traza if not segmento.es_inactivo)
    tiempo_cpu_inactivo = sum(segmento.duracion for segmento in traza if segmento.es_inactivo)
    tiempo_total = traza[-1].fin

    return ResultadoSimulacion(
        algoritmo=algoritmo,
        segmentos=traza,
        resultados=resultados,
        promedio_espera=(
            sum(resultado.tiempo_espera for resultado in resultados) / cantidad_procesos
        ),
        promedio_retorno=(
            sum(resultado.tiempo_retorno for resultado in resultados) / cantidad_procesos
        ),
        tiempo_cpu_ocupado=tiempo_cpu_ocupado,
        tiempo_cpu_inactivo=tiempo_cpu_inactivo,
        tiempo_total=tiempo_total,
        utilizacion_cpu=tiempo_cpu_ocupado / tiempo_total * 100,
        configuraciones_colas=tuple(configuraciones_colas),
    )
