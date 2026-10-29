"""Pruebas de la carga de tiquetes de proceso desde CSV."""

from pathlib import Path

import pytest

from simulador.dominio import Cliente, ErrorValidacion, Servicio
from simulador.infraestructura import cargar_clientes, cargar_procesos

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"
CABECERA = "id_proceso,id_cliente,servicio,cantidad_gestiones,tiempo_llegada,rafaga"


@pytest.fixture
def clientes_de_ejemplo() -> tuple[Cliente, ...]:
    return cargar_clientes(RUTA_DATOS / "clientes.csv")


def _escribir(tmp_path: Path, contenido: str, nombre: str = "procesos.csv") -> Path:
    ruta = tmp_path / nombre
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def _escribir_clientes(tmp_path: Path) -> Path:
    ruta = tmp_path / "clientes.csv"
    ruta.write_text(
        "id_cliente,nombre,tipo_cliente,prioridad,maximo_gestiones,activo\n"
        "C001,Ana Rojas,VIP,1,3,false\n",
        encoding="utf-8",
    )
    return ruta


def test_carga_procesos_de_ejemplo_deriva_prioridad_y_cola(
    clientes_de_ejemplo: tuple[Cliente, ...],
) -> None:
    procesos = cargar_procesos(RUTA_DATOS / "procesos_ejemplo.csv", clientes_de_ejemplo)

    assert len(procesos) == 8
    por_id = {proceso.id_proceso: proceso for proceso in procesos}
    assert (por_id["P001"].prioridad, por_id["P001"].id_cola) == (1, "alta")
    assert (por_id["P003"].prioridad, por_id["P003"].id_cola) == (2, "media")
    assert (por_id["P005"].prioridad, por_id["P005"].id_cola) == (3, "normal")
    assert (por_id["P006"].prioridad, por_id["P006"].id_cola) == (4, "baja")
    assert por_id["P001"].servicio is Servicio.INTERNET
    assert [proceso.orden_ingreso for proceso in procesos] == list(range(8))


def test_rechaza_entero_invalido(tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nP001,C001,Internet,2,0,cinco\n")

    with pytest.raises(ErrorValidacion, match="fila 2, campo rafaga: debe ser un número entero"):
        cargar_procesos(ruta, clientes_de_ejemplo)


def test_rechaza_cliente_inexistente(
    tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]
) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nP001,C999,Internet,1,0,5\n")

    with pytest.raises(ErrorValidacion, match="fila 2, campo id_cliente: cliente inexistente"):
        cargar_procesos(ruta, clientes_de_ejemplo)


def test_rechaza_cliente_inactivo(tmp_path: Path) -> None:
    clientes = cargar_clientes(_escribir_clientes(tmp_path))
    ruta = _escribir(tmp_path, f"{CABECERA}\nP001,C001,Internet,1,0,5\n")

    with pytest.raises(ErrorValidacion, match="campo id_cliente: .*inactivo"):
        cargar_procesos(ruta, clientes)


def test_rechaza_gestiones_fuera_del_maximo(
    tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]
) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nP001,C006,Cable,2,0,2\n")

    with pytest.raises(ErrorValidacion, match="campo cantidad_gestiones: supera el máximo"):
        cargar_procesos(ruta, clientes_de_ejemplo)


def test_rechaza_columna_de_prioridad_en_procesos(
    tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]
) -> None:
    ruta = _escribir(
        tmp_path,
        "id_proceso,id_cliente,servicio,cantidad_gestiones,tiempo_llegada,rafaga,prioridad\n"
        "P001,C001,Internet,2,0,5,4\n",
    )

    with pytest.raises(ErrorValidacion, match="encabezado inválido.*sobran prioridad"):
        cargar_procesos(ruta, clientes_de_ejemplo)


def test_rechaza_identificador_de_proceso_duplicado(
    tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]
) -> None:
    contenido = f"{CABECERA}\nP001,C001,Internet,2,0,5\nP001,C002,Hosting,3,2,7\n"
    ruta = _escribir(tmp_path, contenido)

    with pytest.raises(ErrorValidacion, match="fila 3, campo id_proceso: .*duplicado"):
        cargar_procesos(ruta, clientes_de_ejemplo)


def test_rechaza_servicio_desconocido(
    tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]
) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nP001,C001,Fibra,1,0,5\n")

    with pytest.raises(ErrorValidacion, match="fila 2, campo servicio"):
        cargar_procesos(ruta, clientes_de_ejemplo)


def test_limite_carga_solo_las_primeras_filas(
    clientes_de_ejemplo: tuple[Cliente, ...],
) -> None:
    procesos = cargar_procesos(RUTA_DATOS / "procesos_ejemplo.csv", clientes_de_ejemplo, limite=3)

    assert [proceso.id_proceso for proceso in procesos] == ["P001", "P002", "P003"]
    assert [proceso.orden_ingreso for proceso in procesos] == [0, 1, 2]


def test_limite_ignora_las_filas_posteriores(
    tmp_path: Path, clientes_de_ejemplo: tuple[Cliente, ...]
) -> None:
    contenido = (
        f"{CABECERA}\n"
        "P001,C001,Internet,2,0,5\n"
        "P002,C002,Hosting,1,2,3\n"
        "P003,C003,Cable,1,4,no-es-un-entero\n"
    )
    ruta = _escribir(tmp_path, contenido)

    procesos = cargar_procesos(ruta, clientes_de_ejemplo, limite=2)

    assert [proceso.id_proceso for proceso in procesos] == ["P001", "P002"]


def test_limite_mayor_que_las_filas_carga_todo(
    clientes_de_ejemplo: tuple[Cliente, ...],
) -> None:
    procesos = cargar_procesos(
        RUTA_DATOS / "procesos_ejemplo.csv",
        clientes_de_ejemplo,
        limite=50,
    )

    assert len(procesos) == 8


@pytest.mark.parametrize("limite", [0, -2, 1.5, True, "2"])
def test_rechaza_un_limite_invalido(
    limite: object,
    clientes_de_ejemplo: tuple[Cliente, ...],
) -> None:
    with pytest.raises(ErrorValidacion, match="limite"):
        cargar_procesos(RUTA_DATOS / "procesos_ejemplo.csv", clientes_de_ejemplo, limite=limite)
