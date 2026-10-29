"""Carga de tiquetes de proceso desde CSV."""

from collections.abc import Iterable
from pathlib import Path

from simulador.dominio.enumeraciones import Servicio
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.modelos import Cliente, Proceso
from simulador.dominio.reglas import derivar_cola, derivar_prioridad
from simulador.infraestructura._csv import (
    convertir_entero,
    error_fila,
    exigir_texto,
    leer_filas,
)

COLUMNAS_PROCESOS = (
    "id_proceso",
    "id_cliente",
    "servicio",
    "cantidad_gestiones",
    "tiempo_llegada",
    "rafaga",
)

_SERVICIOS_POR_NOMBRE = {servicio.value: servicio for servicio in Servicio}


def cargar_procesos(
    ruta: str | Path,
    clientes: Iterable[Cliente],
    *,
    limite: int | None = None,
) -> tuple[Proceso, ...]:
    """Carga los tiquetes y deriva de cada cliente su prioridad y cola.

    El archivo no puede declarar prioridad ni cola: ambas se obtienen de las
    reglas del tipo de cliente. El orden de las filas define `orden_ingreso`.
    Con `limite` se cargan solo las primeras filas, que es como se planifican los
    primeros N procesos de un archivo más largo.
    """

    limite_validado = _validar_limite(limite)
    indice_clientes = {cliente.id_cliente: cliente for cliente in clientes}
    filas = leer_filas(ruta, COLUMNAS_PROCESOS, "procesos", limite_validado)
    procesos: list[Proceso] = []
    identificadores: set[str] = set()

    for orden_ingreso, (numero, fila) in enumerate(filas):
        id_proceso = exigir_texto(fila["id_proceso"], numero, "id_proceso")
        if id_proceso in identificadores:
            raise error_fila(numero, "id_proceso", f"identificador duplicado {id_proceso}")
        identificadores.add(id_proceso)

        id_cliente = exigir_texto(fila["id_cliente"], numero, "id_cliente")
        cliente = indice_clientes.get(id_cliente)
        if cliente is None:
            raise error_fila(numero, "id_cliente", f"cliente inexistente {id_cliente}")
        if not cliente.activo:
            raise error_fila(numero, "id_cliente", f"el cliente {id_cliente} está inactivo")

        servicio = _leer_servicio(fila["servicio"], numero)
        cantidad_gestiones = convertir_entero(
            fila["cantidad_gestiones"], numero, "cantidad_gestiones"
        )
        if cantidad_gestiones < 1:
            raise error_fila(numero, "cantidad_gestiones", "debe ser mayor o igual que 1")
        if cantidad_gestiones > cliente.maximo_gestiones:
            raise error_fila(
                numero,
                "cantidad_gestiones",
                f"supera el máximo de {cliente.maximo_gestiones} del cliente {id_cliente}",
            )

        tiempo_llegada = convertir_entero(fila["tiempo_llegada"], numero, "tiempo_llegada")
        if tiempo_llegada < 0:
            raise error_fila(numero, "tiempo_llegada", "debe ser mayor o igual que 0")
        rafaga = convertir_entero(fila["rafaga"], numero, "rafaga")
        if rafaga < 1:
            raise error_fila(numero, "rafaga", "debe ser mayor que 0")

        prioridad = derivar_prioridad(cliente.tipo_cliente)
        try:
            proceso = Proceso(
                id_proceso=id_proceso,
                id_cliente=id_cliente,
                servicio=servicio,
                cantidad_gestiones=cantidad_gestiones,
                tiempo_llegada=tiempo_llegada,
                rafaga=rafaga,
                prioridad=prioridad,
                id_cola=derivar_cola(prioridad),
                orden_ingreso=orden_ingreso,
            )
        except ErrorValidacion as error:
            raise ErrorValidacion(f"fila {numero}: {error}") from error
        procesos.append(proceso)

    return tuple(procesos)


def _validar_limite(limite: int | None) -> int | None:
    """Exige un límite entero positivo o `None` cuando no hay recorte."""

    if limite is None:
        return None
    if isinstance(limite, bool) or not isinstance(limite, int):
        raise ErrorValidacion("limite debe ser un número entero")
    if limite < 1:
        raise ErrorValidacion("limite debe ser mayor o igual que 1")
    return limite


def _leer_servicio(valor: str, numero: int) -> Servicio:
    """Convierte el nombre del servicio en una categoría del dominio."""

    servicio = _SERVICIOS_POR_NOMBRE.get(valor)
    if servicio is None:
        validos = ", ".join(_SERVICIOS_POR_NOMBRE)
        raise error_fila(numero, "servicio", f"valor desconocido {valor!r}; válidos: {validos}")
    return servicio
