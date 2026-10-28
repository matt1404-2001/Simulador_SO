"""Modo consola para ejecutar la carga de ejemplo e imprimir secuencia y métricas."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from simulador.aplicacion import ejecutar_algoritmo
from simulador.dominio.enumeraciones import Algoritmo
from simulador.dominio.excepciones import ErrorDominio
from simulador.dominio.modelos import ResultadoSimulacion
from simulador.infraestructura import cargar_clientes, cargar_procesos
from simulador.presentacion.estado_sesion import configuracion_por_defecto

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"
NOMBRE_CLIENTES = "clientes.csv"


def resolver_ruta_clientes(
    ruta_procesos: Path,
    ruta_clientes: Path | None = None,
) -> Path:
    """Ubica el catálogo que permite derivar prioridad y cola de cada proceso.

    El archivo de procesos no contiene datos del cliente. Si no se indica un
    catálogo, se busca `clientes.csv` junto al archivo de procesos y, como
    respaldo, en la carpeta `data/` del proyecto.
    """

    if ruta_clientes is not None:
        return ruta_clientes

    junto_al_archivo = ruta_procesos.parent / NOMBRE_CLIENTES
    if junto_al_archivo.is_file():
        return junto_al_archivo
    return RUTA_DATOS / NOMBRE_CLIENTES


def ejecutar_desde_archivo(
    ruta_procesos: str | Path,
    ruta_clientes: str | Path | None = None,
) -> ResultadoSimulacion:
    """Carga los CSV y ejecuta la configuración MLQ de demostración."""

    ruta_procesos_normalizada = Path(ruta_procesos)
    ruta_clientes_normalizada = Path(ruta_clientes) if ruta_clientes is not None else None
    clientes = cargar_clientes(
        resolver_ruta_clientes(ruta_procesos_normalizada, ruta_clientes_normalizada)
    )
    procesos = cargar_procesos(ruta_procesos_normalizada, clientes)
    return ejecutar_algoritmo(
        procesos,
        Algoritmo.MLQ,
        configuracion=configuracion_por_defecto(),
    )


def formatear_secuencia(resultado: ResultadoSimulacion) -> tuple[str, ...]:
    """Presenta cada segmento de la traza en orden cronológico."""

    lineas = ["Secuencia de ejecución"]
    for segmento in resultado.segmentos:
        detalle = (
            "CPU inactivo" if segmento.es_inactivo else f"cola {segmento.id_cola or 'sin cola'}"
        )
        lineas.append(
            f"{segmento.inicio:>4} - {segmento.fin:>4}  "
            f"{segmento.etiqueta:<6}  {detalle:<16}  {segmento.duracion:>3} u.t."
        )
    return tuple(lineas)


def formatear_resultados(resultado: ResultadoSimulacion) -> tuple[str, ...]:
    """Presenta los tiempos finales de cada proceso terminado."""

    lineas = [
        "Resultados por proceso",
        f"{'Proceso':<8}{'Cola':<8}{'Llegada':>8}{'Ráfaga':>8}"
        f"{'Final':>7}{'Espera':>8}{'Retorno':>9}",
    ]
    for item in resultado.resultados:
        lineas.append(
            f"{item.id_proceso:<8}{item.id_cola or 'no aplica':<8}"
            f"{item.tiempo_llegada:>8}{item.rafaga:>8}{item.tiempo_finalizacion:>7}"
            f"{item.tiempo_espera:>8}{item.tiempo_retorno:>9}"
        )
    return tuple(lineas)


def formatear_metricas(resultado: ResultadoSimulacion) -> tuple[str, ...]:
    """Presenta los promedios y el uso del CPU ya calculados por el motor."""

    return (
        "Métricas de la ejecución",
        f"Espera promedio: {resultado.promedio_espera:.2f}",
        f"Retorno promedio: {resultado.promedio_retorno:.2f}",
        f"CPU ocupado: {resultado.tiempo_cpu_ocupado} u.t.",
        f"CPU inactivo: {resultado.tiempo_cpu_inactivo} u.t.",
        f"Tiempo total: {resultado.tiempo_total} u.t.",
        f"Utilización del CPU: {resultado.utilizacion_cpu:.2f} %",
    )


def formatear_salida(resultado: ResultadoSimulacion) -> str:
    """Combina encabezado, secuencia, resultados y métricas en un solo texto."""

    secciones = (
        (f"Simulación {resultado.algoritmo.value} con {len(resultado.resultados)} procesos",),
        formatear_secuencia(resultado),
        formatear_resultados(resultado),
        formatear_metricas(resultado),
    )
    return "\n\n".join("\n".join(seccion) for seccion in secciones)


def main(argv: Sequence[str] | None = None) -> int:
    """Ejecuta la simulación desde la línea de comandos.

    Devuelve cero cuando imprime la secuencia y las métricas, y uno cuando el
    archivo no existe o no satisface las reglas de importación.
    """

    analizador = argparse.ArgumentParser(
        prog="python -m simulador.presentacion.consola",
        description=(
            "Ejecuta una carga de procesos con la configuración MLQ de demostración "
            "e imprime la secuencia y las métricas."
        ),
    )
    analizador.add_argument(
        "--archivo",
        required=True,
        type=Path,
        help="CSV de procesos con el formato documentado en README.md.",
    )
    analizador.add_argument(
        "--clientes",
        type=Path,
        default=None,
        help="CSV de clientes; por defecto se busca clientes.csv junto al archivo de procesos.",
    )
    argumentos = analizador.parse_args(argv)

    try:
        resultado = ejecutar_desde_archivo(argumentos.archivo, argumentos.clientes)
    except (ErrorDominio, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(formatear_salida(resultado))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
