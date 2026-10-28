"""Excepciones controladas del dominio del simulador."""


class ErrorDominio(ValueError):
    """Base para errores provocados por datos o reglas del dominio."""


class ErrorValidacion(ErrorDominio):
    """Indica que un dato no satisface una restricción del dominio."""


class ErrorConfiguracion(ErrorDominio):
    """Indica que una configuración de planificación es inconsistente."""
