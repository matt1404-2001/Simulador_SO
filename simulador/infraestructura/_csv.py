"""Utilidades internas para leer los CSV del proveedor de servicios."""

import csv
from collections.abc import Sequence
from pathlib import Path

from simulador.dominio.excepciones import ErrorValidacion


def leer_filas(
    ruta: str | Path,
    columnas: Sequence[str],
    descripcion: str,
) -> list[tuple[int, dict[str, str]]]:
    """Lee un CSV UTF-8 y devuelve cada fila con su número de línea.

    El encabezado debe contener exactamente las columnas esperadas, en cualquier
    orden, y cada fila debe tener la misma cantidad de campos.
    """

    ruta_archivo = Path(ruta)
    if not ruta_archivo.is_file():
        raise ErrorValidacion(f"no existe el archivo de {descripcion}: {ruta_archivo}")

    try:
        with ruta_archivo.open("r", encoding="utf-8-sig", newline="") as archivo:
            lector = csv.DictReader(archivo)
            _validar_encabezado(lector.fieldnames, columnas, descripcion)

            filas: list[tuple[int, dict[str, str]]] = []
            for fila in lector:
                numero = lector.line_num
                if None in fila or any(fila.get(columna) is None for columna in columnas):
                    raise ErrorValidacion(
                        f"fila {numero}: la cantidad de campos no coincide con el encabezado"
                    )
                filas.append(
                    (
                        numero,
                        {columna: (fila[columna] or "").strip() for columna in columnas},
                    )
                )
            return filas
    except UnicodeDecodeError as error:
        raise ErrorValidacion(f"el archivo de {descripcion} no está codificado en UTF-8") from error


def _validar_encabezado(
    cabecera: Sequence[str] | None,
    columnas: Sequence[str],
    descripcion: str,
) -> None:
    """Exige las columnas documentadas y rechaza duplicados o sobrantes."""

    if not cabecera:
        raise ErrorValidacion(f"el archivo de {descripcion} no tiene encabezado")
    if len(set(cabecera)) != len(cabecera):
        raise ErrorValidacion(f"el encabezado de {descripcion} contiene columnas repetidas")

    faltantes = [columna for columna in columnas if columna not in cabecera]
    sobrantes = [columna for columna in cabecera if columna not in columnas]
    if faltantes or sobrantes:
        detalles: list[str] = []
        if faltantes:
            detalles.append("faltan " + ", ".join(faltantes))
        if sobrantes:
            detalles.append("sobran " + ", ".join(sobrantes))
        raise ErrorValidacion(f"encabezado inválido en {descripcion}: " + "; ".join(detalles))


def error_fila(numero: int, campo: str, mensaje: str) -> ErrorValidacion:
    """Construye un error con la fila y el campo que originaron el rechazo."""

    return ErrorValidacion(f"fila {numero}, campo {campo}: {mensaje}")


def exigir_texto(valor: str, numero: int, campo: str) -> str:
    """Devuelve el texto o falla si la celda está vacía."""

    if not valor:
        raise error_fila(numero, campo, "no puede estar vacío")
    return valor


def convertir_entero(valor: str, numero: int, campo: str) -> int:
    """Convierte una celda a entero y contextualiza el error de formato."""

    try:
        return int(valor)
    except ValueError:
        raise error_fila(numero, campo, "debe ser un número entero") from None
