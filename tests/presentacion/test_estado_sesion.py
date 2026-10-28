"""Pruebas del estado de sesión sin depender de un navegador."""

from pathlib import Path

import pytest

from simulador.dominio import Cliente, ErrorValidacion, Proceso, Servicio, TipoCliente
from simulador.infraestructura import cargar_clientes
from simulador.presentacion.estado_sesion import (
    CLAVE_ESTADO_SESION,
    EstadoSesion,
    obtener_estado,
    reiniciar_estado,
)

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"


@pytest.fixture
def clientes() -> tuple[Cliente, ...]:
    return cargar_clientes(RUTA_DATOS / "clientes.csv")


@pytest.fixture
def estado(clientes: tuple[Cliente, ...]) -> EstadoSesion:
    estado = EstadoSesion()
    estado.cargar_catalogo(clientes)
    return estado


def _agregar(
    estado: EstadoSesion,
    id_proceso: str = "P001",
    *,
    id_cliente: str = "C001",
    servicio: Servicio = Servicio.INTERNET,
    cantidad_gestiones: int = 1,
    tiempo_llegada: int = 0,
    rafaga: int = 5,
) -> Proceso:
    return estado.agregar_proceso(
        id_proceso=id_proceso,
        id_cliente=id_cliente,
        servicio=servicio,
        cantidad_gestiones=cantidad_gestiones,
        tiempo_llegada=tiempo_llegada,
        rafaga=rafaga,
    )


def _crear_cliente(id_cliente: str, nombre: str, *, activo: bool = True) -> Cliente:
    return Cliente(
        id_cliente=id_cliente,
        nombre=nombre,
        tipo_cliente=TipoCliente.VIP,
        prioridad=1,
        maximo_gestiones=3,
        activo=activo,
    )


def test_agregar_deriva_prioridad_cola_y_orden_de_ingreso(estado: EstadoSesion) -> None:
    primero = _agregar(estado, "P001", id_cliente="C002", cantidad_gestiones=3)
    segundo = _agregar(estado, "P002", id_cliente="C005", tiempo_llegada=4, rafaga=2)

    assert (primero.prioridad, primero.id_cola, primero.orden_ingreso) == (2, "media", 0)
    assert (segundo.prioridad, segundo.id_cola, segundo.orden_ingreso) == (3, "normal", 1)
    assert [proceso.id_proceso for proceso in estado.procesos] == ["P001", "P002"]


def test_agregar_rechaza_identificador_duplicado(estado: EstadoSesion) -> None:
    _agregar(estado, "P001")

    with pytest.raises(ErrorValidacion, match="ya existe"):
        _agregar(estado, "P001")


def test_agregar_rechaza_cliente_inexistente(estado: EstadoSesion) -> None:
    with pytest.raises(ErrorValidacion, match="no está en el catálogo"):
        _agregar(estado, id_cliente="C999")


def test_agregar_rechaza_cliente_inactivo(estado: EstadoSesion) -> None:
    estado.cargar_catalogo((_crear_cliente("C900", "Cliente inactivo", activo=False),))

    with pytest.raises(ErrorValidacion, match="está inactivo"):
        _agregar(estado, id_cliente="C900")


def test_agregar_rechaza_gestiones_sobre_el_maximo(estado: EstadoSesion) -> None:
    # C006 es Ocasional y admite una sola gestión.
    with pytest.raises(ErrorValidacion, match="no puede superar 1"):
        _agregar(estado, id_cliente="C006", cantidad_gestiones=2)


def test_agregar_sin_catalogo_rechaza_la_operacion() -> None:
    with pytest.raises(ErrorValidacion, match="cargue el catálogo"):
        _agregar(EstadoSesion())


def test_editar_conserva_identificador_y_orden_de_ingreso(estado: EstadoSesion) -> None:
    _agregar(estado, "P001", id_cliente="C001", cantidad_gestiones=2)
    _agregar(estado, "P002", id_cliente="C005")

    actualizado = estado.editar_proceso(
        "P001",
        id_cliente="C002",
        servicio=Servicio.HOSTING,
        cantidad_gestiones=3,
        tiempo_llegada=3,
        rafaga=4,
    )

    assert actualizado.id_proceso == "P001"
    assert actualizado.orden_ingreso == 0
    assert (actualizado.prioridad, actualizado.id_cola) == (2, "media")
    assert (actualizado.servicio, actualizado.cantidad_gestiones) == (Servicio.HOSTING, 3)
    assert (actualizado.tiempo_llegada, actualizado.rafaga) == (3, 4)


def test_editar_rechaza_un_proceso_ausente(estado: EstadoSesion) -> None:
    with pytest.raises(ErrorValidacion, match="no existe el proceso P404"):
        estado.editar_proceso(
            "P404",
            id_cliente="C001",
            servicio=Servicio.CABLE,
            cantidad_gestiones=1,
            tiempo_llegada=0,
            rafaga=1,
        )


def test_eliminar_quita_solo_el_proceso_indicado(estado: EstadoSesion) -> None:
    _agregar(estado, "P001")
    _agregar(estado, "P002")

    estado.eliminar_proceso("P001")

    assert [proceso.id_proceso for proceso in estado.procesos] == ["P002"]
    with pytest.raises(ErrorValidacion, match="no existe el proceso P001"):
        estado.eliminar_proceso("P001")


def test_validar_cantidad_exige_n_y_una_carga_coincidente(estado: EstadoSesion) -> None:
    _agregar(estado, "P001")
    _agregar(estado, "P002")

    with pytest.raises(ErrorValidacion, match="indique la cantidad N"):
        estado.validar_cantidad()

    estado.establecer_cantidad_solicitada(3)
    with pytest.raises(ErrorValidacion, match="N es 3 y la carga tiene 2"):
        estado.validar_cantidad()

    estado.establecer_cantidad_solicitada(2)
    assert estado.validar_cantidad() == 2


@pytest.mark.parametrize("cantidad", [0, -1])
def test_cantidad_solicitada_fuera_de_rango(estado: EstadoSesion, cantidad: int) -> None:
    with pytest.raises(ErrorValidacion, match="mayor o igual que 1"):
        estado.establecer_cantidad_solicitada(cantidad)


def test_cantidad_solicitada_rechaza_valores_no_enteros(estado: EstadoSesion) -> None:
    with pytest.raises(ErrorValidacion, match="número entero"):
        estado.establecer_cantidad_solicitada("dos")  # type: ignore[arg-type]


def test_reiniciar_limpia_procesos_y_n_pero_conserva_el_catalogo(
    estado: EstadoSesion, clientes: tuple[Cliente, ...]
) -> None:
    _agregar(estado, "P001")
    estado.establecer_cantidad_solicitada(1)

    estado.reiniciar()

    assert estado.procesos == []
    assert estado.cantidad_solicitada is None
    assert estado.clientes == clientes


def test_cargar_catalogo_rechaza_identificadores_duplicados(estado: EstadoSesion) -> None:
    with pytest.raises(ErrorValidacion, match="identificadores de cliente duplicados"):
        estado.cargar_catalogo((_crear_cliente("C001", "Ana"), _crear_cliente("C001", "Otra Ana")))


def test_cargar_catalogo_rechaza_un_catalogo_vacio(estado: EstadoSesion) -> None:
    with pytest.raises(ErrorValidacion, match="catálogo de clientes está vacío"):
        estado.cargar_catalogo(())


def test_cargar_catalogo_rechaza_dejar_procesos_huerfanos(
    estado: EstadoSesion, clientes: tuple[Cliente, ...]
) -> None:
    _agregar(estado, "P001", id_cliente="C001")

    with pytest.raises(ErrorValidacion, match="no incluye los clientes de los procesos P001"):
        estado.cargar_catalogo(clientes[1:])


def test_importar_procesos_reemplaza_la_carga(estado: EstadoSesion) -> None:
    _agregar(estado, "P001")
    importados = (
        Proceso(
            id_proceso="P010",
            id_cliente="C003",
            servicio=Servicio.CABLE,
            cantidad_gestiones=1,
            tiempo_llegada=2,
            rafaga=3,
            prioridad=1,
            id_cola="alta",
            orden_ingreso=0,
        ),
    )

    estado.importar_procesos(importados)

    assert estado.procesos == list(importados)


def test_importar_procesos_rechaza_cliente_inexistente(estado: EstadoSesion) -> None:
    proceso = Proceso(
        id_proceso="P010",
        id_cliente="C999",
        servicio=Servicio.CABLE,
        cantidad_gestiones=1,
        tiempo_llegada=0,
        rafaga=2,
        prioridad=1,
        id_cola="alta",
        orden_ingreso=0,
    )

    with pytest.raises(ErrorValidacion, match="referencia un cliente inexistente"):
        estado.importar_procesos((proceso,))


def test_importar_procesos_rechaza_identificadores_duplicados(estado: EstadoSesion) -> None:
    base = {
        "id_cliente": "C001",
        "servicio": Servicio.INTERNET,
        "cantidad_gestiones": 1,
        "tiempo_llegada": 0,
        "rafaga": 2,
        "prioridad": 1,
        "id_cola": "alta",
    }
    procesos = (
        Proceso(id_proceso="P001", orden_ingreso=0, **base),
        Proceso(id_proceso="P001", orden_ingreso=1, **base),
    )

    with pytest.raises(ErrorValidacion, match="identificadores de proceso duplicados"):
        estado.importar_procesos(procesos)


def test_importar_procesos_rechaza_una_carga_vacia(estado: EstadoSesion) -> None:
    with pytest.raises(ErrorValidacion, match="no contiene procesos"):
        estado.importar_procesos(())


def test_procesos_ordenados_usan_el_orden_de_ingreso(estado: EstadoSesion) -> None:
    _agregar(estado, "P002", tiempo_llegada=0)
    _agregar(estado, "P001", tiempo_llegada=5)

    assert [proceso.id_proceso for proceso in estado.procesos_ordenados] == ["P002", "P001"]
    assert [proceso.id_proceso for proceso in estado.procesos] == ["P002", "P001"]


def test_siguiente_id_proceso_evita_identificadores_usados(estado: EstadoSesion) -> None:
    assert estado.siguiente_id_proceso() == "P001"
    _agregar(estado, "P001")
    _agregar(estado, "P002")

    assert estado.siguiente_id_proceso() == "P003"


def test_obtener_estado_reutiliza_la_instancia_de_la_sesion() -> None:
    sesion: dict[str, object] = {}

    primero = obtener_estado(sesion)
    segundo = obtener_estado(sesion)

    assert primero is segundo
    assert sesion[CLAVE_ESTADO_SESION] is primero


def test_reiniciar_estado_conserva_la_instancia_de_la_sesion() -> None:
    sesion: dict[str, object] = {}
    estado = obtener_estado(sesion)
    estado.cargar_catalogo((_crear_cliente("C001", "Ana"),))
    _agregar(estado, "P001")
    estado.establecer_cantidad_solicitada(1)

    reiniciado = reiniciar_estado(sesion)

    assert reiniciado is estado
    assert estado.procesos == []
    assert estado.cantidad_solicitada is None
    assert len(estado.clientes) == 1
