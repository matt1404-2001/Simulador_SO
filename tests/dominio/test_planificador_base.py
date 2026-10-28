"""Pruebas del contrato de planificación y las copias de carga."""

import pytest

from simulador.dominio import (
    Algoritmo,
    ConfiguracionCola,
    Planificador,
    Proceso,
    Servicio,
    copiar_carga,
    copiar_configuracion,
    copiar_procesos,
)


def crear_proceso() -> Proceso:
    return Proceso(
        id_proceso="P001",
        id_cliente="C001",
        servicio=Servicio.INTERNET,
        cantidad_gestiones=1,
        tiempo_llegada=0,
        rafaga=3,
        prioridad=1,
        id_cola="alta",
        orden_ingreso=0,
    )


def crear_configuracion() -> ConfiguracionCola:
    return ConfiguracionCola(
        id_cola="alta",
        nombre="Alta",
        prioridad_cola=1,
        algoritmo=Algoritmo.FIFO,
    )


def test_planificador_no_se_puede_instanciar() -> None:
    with pytest.raises(TypeError):
        Planificador()  # type: ignore[abstract]


def test_copiar_procesos_devuelve_instancias_equivalentes_no_compartidas() -> None:
    procesos = (crear_proceso(),)

    copia = copiar_procesos(procesos)

    assert copia == procesos
    assert copia[0] is not procesos[0]


def test_copiar_configuracion_devuelve_instancias_equivalentes_no_compartidas() -> None:
    configuracion = (crear_configuracion(),)

    copia = copiar_configuracion(configuracion)

    assert copia == configuracion
    assert copia[0] is not configuracion[0]


def test_copiar_carga_aisla_procesos_y_configuracion() -> None:
    procesos = (crear_proceso(),)
    configuracion = (crear_configuracion(),)

    procesos_copiados, configuracion_copiada = copiar_carga(procesos, configuracion)

    assert procesos_copiados == procesos
    assert configuracion_copiada == configuracion
    assert procesos_copiados[0] is not procesos[0]
    assert configuracion_copiada[0] is not configuracion[0]
