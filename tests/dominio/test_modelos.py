"""Pruebas unitarias de los modelos iniciales del dominio."""

from dataclasses import FrozenInstanceError

import pytest

from simulador.dominio import (
    Algoritmo,
    Cliente,
    ConfiguracionCola,
    ErrorConfiguracion,
    ErrorValidacion,
    EstadoProceso,
    Proceso,
    ResultadoProceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
    Servicio,
    TipoCliente,
)


def crear_proceso(**cambios: object) -> Proceso:
    datos: dict[str, object] = {
        "id_proceso": "P001",
        "id_cliente": "C001",
        "servicio": Servicio.INTERNET,
        "cantidad_gestiones": 2,
        "tiempo_llegada": 0,
        "rafaga": 5,
        "prioridad": 1,
        "id_cola": "alta",
        "orden_ingreso": 0,
    }
    datos.update(cambios)
    return Proceso(**datos)  # type: ignore[arg-type]


def test_cliente_valido_normaliza_textos() -> None:
    cliente = Cliente(
        id_cliente=" C001 ",
        nombre=" Ana Gómez ",
        tipo_cliente=TipoCliente.VIP,
        prioridad=1,
        maximo_gestiones=3,
    )

    assert cliente.id_cliente == "C001"
    assert cliente.nombre == "Ana Gómez"
    assert cliente.activo is True


@pytest.mark.parametrize(
    ("campo", "valor"),
    [("id_cliente", ""), ("nombre", "  "), ("prioridad", 0), ("maximo_gestiones", 0)],
)
def test_cliente_rechaza_datos_invalidos(campo: str, valor: object) -> None:
    datos: dict[str, object] = {
        "id_cliente": "C001",
        "nombre": "Ana Gómez",
        "tipo_cliente": TipoCliente.VIP,
        "prioridad": 1,
        "maximo_gestiones": 3,
    }
    datos[campo] = valor

    with pytest.raises(ErrorValidacion):
        Cliente(**datos)  # type: ignore[arg-type]


def test_proceso_inicia_con_rafaga_completa_y_es_inmutable() -> None:
    proceso = crear_proceso()

    assert proceso.tiempo_restante == proceso.rafaga
    assert proceso.estado is EstadoProceso.NUEVO
    with pytest.raises(FrozenInstanceError):
        proceso.tiempo_restante = 0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("cantidad_gestiones", 0),
        ("tiempo_llegada", -1),
        ("rafaga", 0),
        ("prioridad", 0),
        ("orden_ingreso", -1),
        ("tiempo_restante", 6),
    ],
)
def test_proceso_rechaza_valores_fuera_de_rango(campo: str, valor: object) -> None:
    with pytest.raises(ErrorValidacion):
        crear_proceso(**{campo: valor})


def test_proceso_terminado_requiere_tiempo_restante_cero() -> None:
    proceso = crear_proceso(tiempo_restante=0, estado=EstadoProceso.TERMINADO)

    assert proceso.tiempo_restante == 0

    with pytest.raises(ErrorValidacion, match="terminado"):
        crear_proceso(estado=EstadoProceso.TERMINADO)


def test_configuracion_round_robin_requiere_quantum_positivo() -> None:
    configuracion = ConfiguracionCola(
        id_cola="alta",
        nombre="Alta",
        prioridad_cola=1,
        algoritmo=Algoritmo.ROUND_ROBIN,
        quantum=2,
        tipos_cliente=(TipoCliente.VIP, TipoCliente.ADULTO_MAYOR),
    )

    assert configuracion.quantum == 2

    with pytest.raises(ErrorConfiguracion, match="requiere quantum"):
        ConfiguracionCola("alta", "Alta", 1, Algoritmo.ROUND_ROBIN)

    with pytest.raises(ErrorValidacion, match="mayor o igual"):
        ConfiguracionCola("alta", "Alta", 1, Algoritmo.ROUND_ROBIN, quantum=0)


def test_configuracion_rechaza_quantum_en_fifo_y_mlq_interno() -> None:
    with pytest.raises(ErrorConfiguracion, match="solo se configura"):
        ConfiguracionCola("normal", "Normal", 3, Algoritmo.FIFO, quantum=2)

    with pytest.raises(ErrorConfiguracion, match="no puede utilizar MLQ"):
        ConfiguracionCola("normal", "Normal", 3, Algoritmo.MLQ)


def test_segmento_calcula_duracion_y_representa_idle() -> None:
    ejecucion = SegmentoEjecucion("P001", inicio=2, fin=5, id_cola="alta")
    inactivo = SegmentoEjecucion(None, inicio=0, fin=2)

    assert ejecucion.duracion == 3
    assert ejecucion.etiqueta == "P001"
    assert inactivo.es_inactivo is True
    assert inactivo.etiqueta == "IDLE"


def test_segmento_rechaza_intervalo_vacio_y_cola_en_idle() -> None:
    with pytest.raises(ErrorValidacion, match="fin debe ser mayor"):
        SegmentoEjecucion("P001", inicio=2, fin=2)

    with pytest.raises(ErrorValidacion, match="IDLE"):
        SegmentoEjecucion(None, inicio=0, fin=2, id_cola="alta")


def test_resultado_proceso_valida_formulas() -> None:
    resultado = ResultadoProceso(
        id_proceso="P001",
        tiempo_llegada=0,
        rafaga=5,
        tiempo_finalizacion=7,
        tiempo_espera=2,
        tiempo_retorno=7,
        id_cola="alta",
    )

    assert resultado.tiempo_espera == 2

    with pytest.raises(ErrorValidacion, match="tiempo_espera"):
        ResultadoProceso("P001", 0, 5, 7, 1, 7)


def test_resultado_simulacion_valido() -> None:
    segmentos = (
        SegmentoEjecucion(None, 0, 2),
        SegmentoEjecucion("P001", 2, 5, "normal"),
    )
    resultado_proceso = ResultadoProceso("P001", 2, 3, 5, 0, 3, "normal")

    resultado = ResultadoSimulacion(
        algoritmo=Algoritmo.FIFO,
        segmentos=segmentos,
        resultados=(resultado_proceso,),
        promedio_espera=0,
        promedio_retorno=3,
        tiempo_cpu_ocupado=3,
        tiempo_cpu_inactivo=2,
        tiempo_total=5,
        utilizacion_cpu=60,
    )

    assert resultado.utilizacion_cpu == 60.0


def test_resultado_simulacion_rechaza_metricas_inconsistentes() -> None:
    segmentos = (SegmentoEjecucion("P001", 0, 3, "normal"),)
    resultado_proceso = ResultadoProceso("P001", 0, 3, 3, 0, 3, "normal")

    with pytest.raises(ErrorValidacion, match="tiempo_total"):
        ResultadoSimulacion(
            algoritmo=Algoritmo.FIFO,
            segmentos=segmentos,
            resultados=(resultado_proceso,),
            promedio_espera=0,
            promedio_retorno=3,
            tiempo_cpu_ocupado=3,
            tiempo_cpu_inactivo=1,
            tiempo_total=3,
            utilizacion_cpu=100,
        )
