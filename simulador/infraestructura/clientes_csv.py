"""Carga del catálogo de clientes desde CSV."""

from pathlib import Path

from simulador.dominio.enumeraciones import TipoCliente
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.modelos import Cliente
from simulador.dominio.reglas import obtener_regla
from simulador.infraestructura._csv import (
    convertir_entero,
    error_fila,
    exigir_texto,
    leer_filas,
)

COLUMNAS_CLIENTES = (
    "id_cliente",
    "nombre",
    "tipo_cliente",
    "prioridad",
    "maximo_gestiones",
    "activo",
)

_TIPOS_POR_NOMBRE = {tipo.value: tipo for tipo in TipoCliente}


def cargar_clientes(ruta: str | Path) -> tuple[Cliente, ...]:
    """Carga y valida el catálogo de clientes registrados.

    La prioridad y el máximo de gestiones declarados en el archivo deben
    coincidir con la regla vigente para el tipo de cliente, de modo que el CSV no
    pueda contradecir la configuración del dominio.
    """

    filas = leer_filas(ruta, COLUMNAS_CLIENTES, "clientes")
    clientes: list[Cliente] = []
    identificadores: set[str] = set()

    for numero, fila in filas:
        id_cliente = exigir_texto(fila["id_cliente"], numero, "id_cliente")
        if id_cliente in identificadores:
            raise error_fila(numero, "id_cliente", f"identificador duplicado {id_cliente}")
        identificadores.add(id_cliente)

        nombre = exigir_texto(fila["nombre"], numero, "nombre")
        tipo_cliente = _leer_tipo_cliente(fila["tipo_cliente"], numero)
        prioridad = convertir_entero(fila["prioridad"], numero, "prioridad")
        maximo_gestiones = convertir_entero(fila["maximo_gestiones"], numero, "maximo_gestiones")
        activo = _leer_activo(fila["activo"], numero)

        regla = obtener_regla(tipo_cliente)
        if prioridad != regla.prioridad:
            raise error_fila(
                numero,
                "prioridad",
                f"no coincide con la regla de {tipo_cliente.value} (esperado {regla.prioridad})",
            )
        if maximo_gestiones != regla.maximo_gestiones:
            raise error_fila(
                numero,
                "maximo_gestiones",
                f"no coincide con la regla de {tipo_cliente.value} "
                f"(esperado {regla.maximo_gestiones})",
            )

        try:
            cliente = Cliente(
                id_cliente=id_cliente,
                nombre=nombre,
                tipo_cliente=tipo_cliente,
                prioridad=prioridad,
                maximo_gestiones=maximo_gestiones,
                activo=activo,
            )
        except ErrorValidacion as error:
            raise ErrorValidacion(f"fila {numero}: {error}") from error
        clientes.append(cliente)

    return tuple(clientes)


def _leer_tipo_cliente(valor: str, numero: int) -> TipoCliente:
    """Convierte el nombre del tipo de cliente en una categoría del dominio."""

    tipo_cliente = _TIPOS_POR_NOMBRE.get(valor)
    if tipo_cliente is None:
        validos = ", ".join(_TIPOS_POR_NOMBRE)
        raise error_fila(numero, "tipo_cliente", f"valor desconocido {valor!r}; válidos: {validos}")
    return tipo_cliente


def _leer_activo(valor: str, numero: int) -> bool:
    """Interpreta únicamente los booleanos documentados del formato CSV."""

    normalizado = valor.lower()
    if normalizado == "true":
        return True
    if normalizado == "false":
        return False
    raise error_fila(numero, "activo", f"valor booleano inválido {valor!r}; use true o false")
