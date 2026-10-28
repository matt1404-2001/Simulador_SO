"""Pruebas de la carga del catálogo de clientes desde CSV."""

from pathlib import Path

import pytest

from simulador.dominio import Cliente, ErrorValidacion, TipoCliente
from simulador.infraestructura.clientes_csv import COLUMNAS_CLIENTES, cargar_clientes

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"
CABECERA = ",".join(COLUMNAS_CLIENTES)


def _escribir(tmp_path: Path, contenido: str) -> Path:
    ruta = tmp_path / "clientes.csv"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_carga_catalogo_de_ejemplo() -> None:
    clientes = cargar_clientes(RUTA_DATOS / "clientes.csv")

    assert len(clientes) == 6
    assert clientes[0] == Cliente(
        id_cliente="C001",
        nombre="Ana Rojas",
        tipo_cliente=TipoCliente.VIP,
        prioridad=1,
        maximo_gestiones=3,
        activo=True,
    )
    assert {cliente.tipo_cliente for cliente in clientes} == set(TipoCliente)
    assert all(cliente.activo for cliente in clientes)


def test_rechaza_archivo_sin_encabezado(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "")

    with pytest.raises(ErrorValidacion, match="no tiene encabezado"):
        cargar_clientes(ruta)


def test_rechaza_encabezado_incompleto(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, "id_cliente,nombre,tipo_cliente,prioridad,maximo_gestiones\n")

    with pytest.raises(ErrorValidacion, match="encabezado inválido.*faltan activo"):
        cargar_clientes(ruta)


def test_rechaza_tipo_de_cliente_desconocido(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nC001,Ana Rojas,Platino,1,3,true\n")

    with pytest.raises(ErrorValidacion, match="fila 2, campo tipo_cliente"):
        cargar_clientes(ruta)


@pytest.mark.parametrize("activo", ["si", "1", ""])
def test_rechaza_booleano_invalido(tmp_path: Path, activo: str) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nC001,Ana Rojas,VIP,1,3,{activo}\n")

    with pytest.raises(ErrorValidacion, match="campo activo"):
        cargar_clientes(ruta)


def test_rechaza_identificador_duplicado(tmp_path: Path) -> None:
    contenido = f"{CABECERA}\nC001,Ana Rojas,VIP,1,3,true\nC001,Luis Mora,Empresarial,2,4,true\n"
    ruta = _escribir(tmp_path, contenido)

    with pytest.raises(ErrorValidacion, match="fila 3, campo id_cliente: .*duplicado"):
        cargar_clientes(ruta)


def test_rechaza_prioridad_incoherente_con_el_tipo(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nC001,Ana Rojas,VIP,2,3,true\n")

    with pytest.raises(ErrorValidacion, match="campo prioridad: .*esperado 1"):
        cargar_clientes(ruta)


def test_rechaza_maximo_de_gestiones_incoherente_con_el_tipo(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nC001,Ana Rojas,VIP,1,4,true\n")

    with pytest.raises(ErrorValidacion, match="campo maximo_gestiones: .*esperado 3"):
        cargar_clientes(ruta)


def test_rechaza_prioridad_no_entera(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, f"{CABECERA}\nC001,Ana Rojas,VIP,alta,3,true\n")

    with pytest.raises(ErrorValidacion, match="campo prioridad: debe ser un número entero"):
        cargar_clientes(ruta)
