"""Reglas que derivan la prioridad y la cola de un cliente."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from simulador.dominio.enumeraciones import TipoCliente
from simulador.dominio.excepciones import ErrorValidacion


@dataclass(frozen=True, slots=True)
class ReglaTipoCliente:
    """Prioridad, máximo de gestiones y cola asociados a un tipo de cliente."""

    prioridad: int
    maximo_gestiones: int
    id_cola: str


# Los valores son una decisión de diseño documentada en guias/CONTEXT.md y deben
# coincidir con las columnas del catálogo de clientes. Los identificadores de cola
# se escriben en minúsculas para usarlos como claves estables en el dominio.
REGLAS_TIPO_CLIENTE: Mapping[TipoCliente, ReglaTipoCliente] = MappingProxyType(
    {
        TipoCliente.VIP: ReglaTipoCliente(prioridad=1, maximo_gestiones=3, id_cola="alta"),
        TipoCliente.EMBARAZADA: ReglaTipoCliente(prioridad=1, maximo_gestiones=2, id_cola="alta"),
        TipoCliente.ADULTO_MAYOR: ReglaTipoCliente(prioridad=1, maximo_gestiones=2, id_cola="alta"),
        TipoCliente.EMPRESARIAL: ReglaTipoCliente(prioridad=2, maximo_gestiones=4, id_cola="media"),
        TipoCliente.REGULAR: ReglaTipoCliente(prioridad=3, maximo_gestiones=2, id_cola="normal"),
        TipoCliente.OCASIONAL: ReglaTipoCliente(prioridad=4, maximo_gestiones=1, id_cola="baja"),
    }
)

# Un valor numérico menor representa una prioridad más alta.
ID_COLA_POR_PRIORIDAD: Mapping[int, str] = MappingProxyType(
    {1: "alta", 2: "media", 3: "normal", 4: "baja"}
)


def obtener_regla(tipo_cliente: TipoCliente) -> ReglaTipoCliente:
    """Devuelve la regla vigente para un tipo de cliente."""

    try:
        return REGLAS_TIPO_CLIENTE[tipo_cliente]
    except KeyError:
        raise ErrorValidacion(f"tipo de cliente desconocido: {tipo_cliente}") from None


def derivar_prioridad(tipo_cliente: TipoCliente) -> int:
    """Obtiene la prioridad asignada al tipo de cliente."""

    return obtener_regla(tipo_cliente).prioridad


def derivar_cola(prioridad: int) -> str:
    """Traduce la prioridad numérica al identificador de su cola fija."""

    if isinstance(prioridad, bool) or not isinstance(prioridad, int):
        raise ErrorValidacion("prioridad debe ser un número entero")
    try:
        return ID_COLA_POR_PRIORIDAD[prioridad]
    except KeyError:
        raise ErrorValidacion(f"no existe una cola para la prioridad {prioridad}") from None
