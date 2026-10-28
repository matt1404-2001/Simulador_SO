"""Valores controlados utilizados por los modelos del dominio."""

from enum import StrEnum


class EstadoProceso(StrEnum):
    """Estados que puede mostrar un proceso durante la simulación."""

    NUEVO = "Nuevo"
    LISTO = "Listo"
    EJECUTANDO = "Ejecutando"
    TERMINADO = "Terminado"


class Algoritmo(StrEnum):
    """Algoritmos de planificación admitidos por el sistema."""

    FIFO = "FIFO"
    SJF = "SJF"
    ROUND_ROBIN = "Round Robin"
    MLQ = "MLQ"


class TipoCliente(StrEnum):
    """Categorías iniciales de clientes del proveedor de servicios."""

    VIP = "VIP"
    EMBARAZADA = "Embarazada"
    ADULTO_MAYOR = "Adulto mayor"
    EMPRESARIAL = "Empresarial"
    REGULAR = "Regular"
    OCASIONAL = "Ocasional"


class Servicio(StrEnum):
    """Servicios iniciales que puede solicitar un cliente."""

    INTERNET = "Internet"
    CABLE = "Cable"
    TELEFONIA = "Telefonía"
    HOSTING = "Hosting"
