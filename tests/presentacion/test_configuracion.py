"""Pruebas de la configuración MLQ y de la invalidación de resultados."""

from pathlib import Path

import pytest

from simulador.aplicacion import comparar_algoritmos, ejecutar_algoritmo
from simulador.dominio import (
    Algoritmo,
    Cliente,
    ConfiguracionCola,
    ErrorConfiguracion,
    ErrorValidacion,
    Servicio,
    TipoCliente,
)
from simulador.dominio.reglas import REGLAS_TIPO_CLIENTE
from simulador.infraestructura import cargar_clientes, cargar_procesos
from simulador.presentacion.estado_sesion import (
    ColaEditable,
    EstadoSesion,
    configuracion_por_defecto,
    construir_colas,
    tipos_cliente_de_cola,
)

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def clientes() -> tuple[Cliente, ...]:
    return cargar_clientes(RUTA_DATOS / "clientes.csv")


@pytest.fixture
def estado_vacio(clientes: tuple[Cliente, ...]) -> EstadoSesion:
    estado = EstadoSesion()
    estado.cargar_catalogo(clientes)
    return estado


@pytest.fixture
def estado_con_ejemplo(clientes: tuple[Cliente, ...]) -> EstadoSesion:
    estado = EstadoSesion()
    estado.cargar_catalogo(clientes)
    estado.importar_procesos(cargar_procesos(RUTA_DATOS / "procesos_ejemplo.csv", clientes))
    estado.establecer_cantidad_solicitada(len(estado.procesos))
    return estado


def _agregar(estado: EstadoSesion, id_proceso: str = "P001", *, rafaga: int = 4) -> None:
    estado.agregar_proceso(
        id_proceso=id_proceso,
        id_cliente="C001",
        servicio=Servicio.INTERNET,
        cantidad_gestiones=1,
        tiempo_llegada=0,
        rafaga=rafaga,
    )


def _ejecutar_mlq(estado: EstadoSesion) -> None:
    resultado = ejecutar_algoritmo(
        estado.procesos_ordenados,
        Algoritmo.MLQ,
        configuracion=estado.configuracion_colas,
    )
    estado.registrar_resultado_mlq(resultado)


def _ejecutar_comparacion(estado: EstadoSesion, quantum: int = 2) -> None:
    comparacion = comparar_algoritmos(estado.procesos_ordenados, quantum=quantum)
    estado.registrar_comparacion(comparacion, quantum=quantum)


def test_la_configuracion_por_defecto_reproduce_la_demostracion() -> None:
    configuracion = configuracion_por_defecto()

    assert [cola.id_cola for cola in configuracion] == ["alta", "media", "normal", "baja"]
    assert [cola.prioridad_cola for cola in configuracion] == [1, 2, 3, 4]
    assert [cola.algoritmo for cola in configuracion] == [
        Algoritmo.ROUND_ROBIN,
        Algoritmo.SJF,
        Algoritmo.FIFO,
        Algoritmo.FIFO,
    ]
    assert configuracion[0].quantum == 2


def test_construir_colas_deriva_nombre_y_tipos() -> None:
    (cola,) = construir_colas((ColaEditable("alta", 1, Algoritmo.ROUND_ROBIN, 3),))

    assert cola.nombre == "Alta"
    assert cola.quantum == 3
    assert cola.tipos_cliente == tipos_cliente_de_cola("alta")
    assert TipoCliente.VIP in cola.tipos_cliente
    assert TipoCliente.EMPRESARIAL not in cola.tipos_cliente


def test_todos_los_tipos_de_cliente_tienen_una_sola_cola() -> None:
    asignaciones: dict[str, int] = {}
    for regla in REGLAS_TIPO_CLIENTE.values():
        asignaciones[regla.id_cola] = asignaciones.get(regla.id_cola, 0) + 1

    assert sum(asignaciones.values()) == len(TipoCliente)
    assert len(tipos_cliente_de_cola("alta")) == 3


def test_round_robin_exige_quantum() -> None:
    with pytest.raises(ErrorConfiguracion, match="Round Robin y requiere quantum"):
        construir_colas((ColaEditable("alta", 1, Algoritmo.ROUND_ROBIN),))


@pytest.mark.parametrize("quantum", [0, -1, True])
def test_round_robin_rechaza_quantum_invalido(quantum: object) -> None:
    with pytest.raises(ErrorConfiguracion, match="entero mayor o igual que 1"):
        construir_colas(
            (ColaEditable("alta", 1, Algoritmo.ROUND_ROBIN, quantum),)  # type: ignore[arg-type]
        )


def test_una_cola_sin_round_robin_no_admite_quantum() -> None:
    with pytest.raises(ErrorConfiguracion, match="no admite quantum"):
        construir_colas((ColaEditable("media", 2, Algoritmo.FIFO, 2),))


def test_construir_colas_rechaza_identificadores_duplicados() -> None:
    with pytest.raises(ErrorConfiguracion, match="colas duplicadas"):
        construir_colas(
            (
                ColaEditable("media", 2, Algoritmo.FIFO),
                ColaEditable("media", 3, Algoritmo.SJF),
            )
        )


def test_construir_colas_rechaza_una_cola_desconocida() -> None:
    with pytest.raises(ErrorConfiguracion, match="no está definida en el sistema"):
        construir_colas((ColaEditable("inventada", 1, Algoritmo.FIFO),))


def test_establecer_configuracion_rechaza_tipos_repetidos(estado_vacio: EstadoSesion) -> None:
    configuracion = (
        ConfiguracionCola(
            "alta",
            "Alta",
            1,
            Algoritmo.FIFO,
            tipos_cliente=(TipoCliente.VIP,),
        ),
        ConfiguracionCola(
            "media",
            "Media",
            2,
            Algoritmo.FIFO,
            tipos_cliente=(TipoCliente.VIP,),
        ),
    )

    with pytest.raises(ErrorConfiguracion, match="el tipo de cliente VIP aparece"):
        estado_vacio.establecer_configuracion(configuracion)


def test_establecer_configuracion_exige_cubrir_las_colas_de_la_carga(
    estado_con_ejemplo: EstadoSesion,
) -> None:
    solo_media = construir_colas((ColaEditable("media", 2, Algoritmo.SJF),))

    with pytest.raises(ErrorConfiguracion, match="no incluye las colas de la carga: alta"):
        estado_con_ejemplo.establecer_configuracion(solo_media)


def test_establecer_configuracion_valida_la_conserva(estado_con_ejemplo: EstadoSesion) -> None:
    configuracion = construir_colas(
        (
            ColaEditable("alta", 1, Algoritmo.ROUND_ROBIN, 4),
            ColaEditable("media", 2, Algoritmo.FIFO),
            ColaEditable("normal", 3, Algoritmo.SJF),
            ColaEditable("baja", 4, Algoritmo.FIFO),
        )
    )

    estado_con_ejemplo.establecer_configuracion(configuracion)

    assert estado_con_ejemplo.configuracion_colas == configuracion
    assert estado_con_ejemplo.configuracion_colas[0].quantum == 4


def test_ejecutar_los_cuatro_modos_conserva_los_resultados(
    estado_con_ejemplo: EstadoSesion,
) -> None:
    for algoritmo in (Algoritmo.FIFO, Algoritmo.SJF):
        resultado = ejecutar_algoritmo(estado_con_ejemplo.procesos_ordenados, algoritmo)
        estado_con_ejemplo.registrar_resultado_individual(resultado)
    resultado_round_robin = ejecutar_algoritmo(
        estado_con_ejemplo.procesos_ordenados,
        Algoritmo.ROUND_ROBIN,
        quantum=2,
    )
    estado_con_ejemplo.registrar_resultado_individual(resultado_round_robin)
    _ejecutar_mlq(estado_con_ejemplo)
    _ejecutar_comparacion(estado_con_ejemplo)

    assert estado_con_ejemplo.resultado_individual is not None
    assert estado_con_ejemplo.resultado_individual.algoritmo is Algoritmo.ROUND_ROBIN
    assert estado_con_ejemplo.resultado_mlq is not None
    assert estado_con_ejemplo.resultado_mlq.algoritmo is Algoritmo.MLQ
    assert estado_con_ejemplo.comparacion is not None
    assert [resultado.algoritmo for resultado in estado_con_ejemplo.comparacion.resultados] == [
        Algoritmo.FIFO,
        Algoritmo.SJF,
        Algoritmo.ROUND_ROBIN,
    ]
    assert estado_con_ejemplo.quantum_comparacion == 2


def test_cambiar_la_carga_invalida_los_resultados(estado_vacio: EstadoSesion) -> None:
    _agregar(estado_vacio)
    _ejecutar_mlq(estado_vacio)
    _ejecutar_comparacion(estado_vacio)

    _agregar(estado_vacio, "P002", rafaga=2)

    assert estado_vacio.resultado_mlq is None
    assert estado_vacio.comparacion is None
    assert estado_vacio.resultado_individual is None


def test_editar_o_eliminar_un_proceso_invalida_los_resultados(
    estado_vacio: EstadoSesion,
) -> None:
    _agregar(estado_vacio, "P001")
    _agregar(estado_vacio, "P002")
    _ejecutar_mlq(estado_vacio)

    estado_vacio.editar_proceso(
        "P001",
        id_cliente="C002",
        servicio=Servicio.CABLE,
        cantidad_gestiones=1,
        tiempo_llegada=0,
        rafaga=3,
    )
    assert estado_vacio.resultado_mlq is None

    _ejecutar_mlq(estado_vacio)
    estado_vacio.eliminar_proceso("P002")
    assert estado_vacio.resultado_mlq is None


def test_importar_procesos_y_recargar_catalogo_invalidan_los_resultados(
    estado_vacio: EstadoSesion,
    clientes: tuple[Cliente, ...],
) -> None:
    _agregar(estado_vacio)
    _ejecutar_mlq(estado_vacio)
    estado_vacio.importar_procesos(cargar_procesos(RUTA_DATOS / "procesos_ejemplo.csv", clientes))
    assert estado_vacio.resultado_mlq is None

    _ejecutar_mlq(estado_vacio)
    estado_vacio.cargar_catalogo(clientes)
    assert estado_vacio.resultado_mlq is None


def test_cambiar_la_configuracion_invalida_los_resultados(
    estado_con_ejemplo: EstadoSesion,
) -> None:
    _ejecutar_mlq(estado_con_ejemplo)
    _ejecutar_comparacion(estado_con_ejemplo)

    configuracion = construir_colas(
        (
            ColaEditable("alta", 1, Algoritmo.FIFO),
            ColaEditable("media", 2, Algoritmo.SJF),
            ColaEditable("normal", 3, Algoritmo.FIFO),
            ColaEditable("baja", 4, Algoritmo.FIFO),
        )
    )
    estado_con_ejemplo.establecer_configuracion(configuracion)

    assert estado_con_ejemplo.resultado_mlq is None
    assert estado_con_ejemplo.comparacion is None


def test_una_configuracion_invalida_no_descarta_los_resultados(
    estado_con_ejemplo: EstadoSesion,
) -> None:
    _ejecutar_mlq(estado_con_ejemplo)
    resultado = estado_con_ejemplo.resultado_mlq
    solo_media = construir_colas((ColaEditable("media", 2, Algoritmo.SJF),))

    with pytest.raises(ErrorConfiguracion):
        estado_con_ejemplo.establecer_configuracion(solo_media)

    assert estado_con_ejemplo.resultado_mlq is resultado


def test_cambiar_el_quantum_de_comparacion_solo_descarta_la_comparacion(
    estado_vacio: EstadoSesion,
) -> None:
    _agregar(estado_vacio)
    _ejecutar_mlq(estado_vacio)
    _ejecutar_comparacion(estado_vacio, quantum=2)

    estado_vacio.establecer_quantum_comparacion(3)

    assert estado_vacio.comparacion is None
    assert estado_vacio.quantum_comparacion == 3
    assert estado_vacio.resultado_mlq is not None


@pytest.mark.parametrize("quantum", [0, -1, "dos"])
def test_quantum_de_comparacion_invalido(estado_vacio: EstadoSesion, quantum: object) -> None:
    with pytest.raises(ErrorValidacion, match="quantum de la comparación"):
        estado_vacio.establecer_quantum_comparacion(quantum)  # type: ignore[arg-type]


def test_cambiar_n_no_descarta_los_resultados(estado_vacio: EstadoSesion) -> None:
    _agregar(estado_vacio)
    estado_vacio.establecer_cantidad_solicitada(1)
    _ejecutar_mlq(estado_vacio)

    estado_vacio.establecer_cantidad_solicitada(2)

    assert estado_vacio.resultado_mlq is not None


def test_reiniciar_descarta_resultados_y_conserva_la_configuracion(
    estado_vacio: EstadoSesion,
) -> None:
    configuracion = estado_vacio.configuracion_colas
    _agregar(estado_vacio)
    _ejecutar_mlq(estado_vacio)

    estado_vacio.reiniciar()

    assert estado_vacio.resultado_mlq is None
    assert estado_vacio.configuracion_colas == configuracion
    assert estado_vacio.clientes
