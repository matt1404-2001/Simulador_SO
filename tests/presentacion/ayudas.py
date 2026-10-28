"""Datos de ejemplo compartidos por las pruebas de presentación."""

from simulador.dominio import (
    Algoritmo,
    Proceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
    Servicio,
    calcular_metricas,
)


def crear_proceso(
    id_proceso: str,
    tiempo_llegada: int,
    rafaga: int,
    *,
    orden_ingreso: int = 0,
) -> Proceso:
    """Crea un proceso mínimo para las pruebas de presentación."""

    return Proceso(
        id_proceso=id_proceso,
        id_cliente="C001",
        servicio=Servicio.INTERNET,
        cantidad_gestiones=1,
        tiempo_llegada=tiempo_llegada,
        rafaga=rafaga,
        prioridad=1,
        id_cola="normal",
        orden_ingreso=orden_ingreso,
    )


def resultado_con_idle() -> ResultadoSimulacion:
    """Devuelve una traza calculada a mano con un tramo de CPU inactivo."""

    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P002", 5, 2, orden_ingreso=1),
    )
    segmentos = (
        SegmentoEjecucion("P001", inicio=0, fin=2),
        SegmentoEjecucion(None, inicio=2, fin=5),
        SegmentoEjecucion("P002", inicio=5, fin=7),
    )
    return calcular_metricas(segmentos, procesos, algoritmo=Algoritmo.FIFO)
