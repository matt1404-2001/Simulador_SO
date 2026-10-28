"""Flujo completo con los archivos de ejemplo y casos límite de integración."""

import csv
import shutil
from io import StringIO
from pathlib import Path

import pytest

from simulador.aplicacion import comparar_algoritmos, ejecutar_algoritmo
from simulador.dominio import (
    Algoritmo,
    ConfiguracionCola,
    ErrorValidacion,
    Proceso,
    ResultadoSimulacion,
)
from simulador.infraestructura import (
    COLUMNAS_METRICAS,
    COLUMNAS_RESULTADOS,
    COLUMNAS_TRAZA,
    cargar_clientes,
    cargar_procesos,
    exportar_metricas,
    exportar_resultados,
    exportar_traza,
)
from simulador.presentacion.consola import (
    ejecutar_desde_archivo,
    formatear_salida,
    main,
)
from simulador.presentacion.estado_sesion import configuracion_por_defecto
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"
RUTA_CLIENTES = RUTA_DATOS / "clientes.csv"
RUTA_PROCESOS = RUTA_DATOS / "procesos_ejemplo.csv"


@pytest.fixture(scope="module")
def procesos_de_ejemplo() -> tuple[Proceso, ...]:
    """Carga la demostración completa desde los CSV entregados."""

    clientes = cargar_clientes(RUTA_CLIENTES)
    return cargar_procesos(RUTA_PROCESOS, clientes)


def _leer_csv(contenido: str) -> tuple[list[str], list[dict[str, str]]]:
    """Devuelve el encabezado y las filas de un CSV en memoria."""

    lector = csv.DictReader(StringIO(contenido))
    filas = list(lector)
    return list(lector.fieldnames or ()), filas


def _ejecutar_modo(
    procesos_de_ejemplo: tuple[Proceso, ...],
    algoritmo: Algoritmo,
    quantum: int | None = None,
) -> ResultadoSimulacion:
    """Ejecuta uno de los cuatro modos con la configuración vigente."""

    configuracion = configuracion_por_defecto() if algoritmo is Algoritmo.MLQ else ()
    return ejecutar_algoritmo(
        procesos_de_ejemplo,
        algoritmo,
        quantum=quantum,
        configuracion=configuracion,
    )


def test_la_carga_de_ejemplo_contiene_ocho_procesos_validos(
    procesos_de_ejemplo: tuple[Proceso, ...],
) -> None:
    assert len(procesos_de_ejemplo) == 8
    assert [proceso.id_proceso for proceso in procesos_de_ejemplo] == [
        "P001",
        "P002",
        "P003",
        "P004",
        "P005",
        "P006",
        "P007",
        "P008",
    ]
    assert [proceso.id_cola for proceso in procesos_de_ejemplo] == [
        "alta",
        "alta",
        "media",
        "alta",
        "normal",
        "baja",
        "alta",
        "media",
    ]
    assert sum(proceso.rafaga for proceso in procesos_de_ejemplo) == 34


@pytest.mark.parametrize(
    ("algoritmo", "quantum"),
    [
        (Algoritmo.FIFO, None),
        (Algoritmo.SJF, None),
        (Algoritmo.ROUND_ROBIN, 2),
        (Algoritmo.MLQ, None),
    ],
    ids=["fifo", "sjf", "round-robin", "mlq"],
)
def test_los_cuatro_modos_ejecutan_la_carga_completa(
    procesos_de_ejemplo: tuple[Proceso, ...],
    algoritmo: Algoritmo,
    quantum: int | None,
) -> None:
    resultado = _ejecutar_modo(procesos_de_ejemplo, algoritmo, quantum)

    assert resultado.algoritmo is algoritmo
    assert len(resultado.resultados) == 8
    assert resultado.tiempo_cpu_ocupado == 34
    assert resultado.tiempo_cpu_inactivo == 10
    assert resultado.tiempo_total == 44
    assert resultado.utilizacion_cpu == pytest.approx(34 / 44 * 100)
    assert any(segmento.es_inactivo for segmento in resultado.segmentos)
    verificar_invariantes(resultado)


def test_mlq_de_demostracion_respeta_colas_y_prioridades(
    procesos_de_ejemplo: tuple[Proceso, ...],
) -> None:
    resultado = _ejecutar_modo(procesos_de_ejemplo, Algoritmo.MLQ)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P002", 2, 4),
        ("P001", 4, 6),
        ("P002", 6, 7),
        ("P004", 7, 9),
        ("P001", 9, 10),
        ("P004", 10, 12),
        ("P007", 12, 14),
        ("P007", 14, 15),
        ("P003", 15, 22),
        ("P005", 22, 28),
        ("P006", 28, 30),
        ("IDLE", 30, 40),
        ("P008", 40, 44),
    ]
    assert resultado.promedio_espera == pytest.approx(7.25)
    assert resultado.promedio_retorno == pytest.approx(11.5)
    assert resultado.utilizacion_cpu == pytest.approx(34 / 44 * 100)
    assert resultado.configuraciones_colas == configuracion_por_defecto()


def test_la_comparacion_reutiliza_la_misma_carga(
    procesos_de_ejemplo: tuple[Proceso, ...],
) -> None:
    comparacion = comparar_algoritmos(procesos_de_ejemplo, quantum=2)

    assert [resultado.algoritmo for resultado in comparacion.resultados] == [
        Algoritmo.FIFO,
        Algoritmo.SJF,
        Algoritmo.ROUND_ROBIN,
    ]
    for resultado in comparacion.resultados:
        assert len(resultado.resultados) == 8
        assert resultado.tiempo_cpu_ocupado == 34
        assert resultado.tiempo_cpu_inactivo == 10
        assert resultado.tiempo_total == 44
        verificar_invariantes(resultado)

    assert comparacion.sjf.promedio_espera == pytest.approx(5.375)
    assert comparacion.round_robin.promedio_espera == pytest.approx(10.375)


def test_la_exportacion_del_flujo_completo_coincide_con_la_traza(
    procesos_de_ejemplo: tuple[Proceso, ...],
    tmp_path: Path,
) -> None:
    resultado = _ejecutar_modo(procesos_de_ejemplo, Algoritmo.MLQ)

    ruta_traza = exportar_traza(resultado, tmp_path / "traza.csv")
    ruta_resultados = exportar_resultados(resultado, tmp_path / "resultados.csv")
    ruta_metricas = exportar_metricas(resultado, tmp_path / "metricas.csv")

    encabezado_traza, filas_traza = _leer_csv(ruta_traza.read_text(encoding="utf-8"))
    assert encabezado_traza == list(COLUMNAS_TRAZA)
    assert len(filas_traza) == len(resultado.segmentos)
    assert [fila["proceso"] for fila in filas_traza if fila["proceso"] == "IDLE"] == ["IDLE"]
    assert sum(int(fila["duracion"]) for fila in filas_traza) == resultado.tiempo_total

    encabezado_resultados, filas_resultados = _leer_csv(ruta_resultados.read_text(encoding="utf-8"))
    assert encabezado_resultados == list(COLUMNAS_RESULTADOS)
    assert [fila["id_proceso"] for fila in filas_resultados] == [
        item.id_proceso for item in resultado.resultados
    ]
    assert int(filas_resultados[-1]["tiempo_finalizacion"]) == 44

    encabezado_metricas, filas_metricas = _leer_csv(ruta_metricas.read_text(encoding="utf-8"))
    assert encabezado_metricas == list(COLUMNAS_METRICAS)
    assert len(filas_metricas) == 1
    assert filas_metricas[0]["algoritmo"] == "MLQ"
    assert float(filas_metricas[0]["utilizacion_cpu"]) == pytest.approx(34 / 44 * 100)


def test_la_consola_imprime_secuencia_y_metricas(capsys) -> None:
    codigo = main(["--archivo", str(RUTA_PROCESOS)])

    salida = capsys.readouterr()
    assert codigo == 0
    assert salida.err == ""
    assert salida.out == formatear_salida(ejecutar_desde_archivo(RUTA_PROCESOS)) + "\n"
    assert "Simulación MLQ con 8 procesos" in salida.out
    assert "Secuencia de ejecución" in salida.out
    assert "IDLE" in salida.out
    assert "CPU inactivo" in salida.out
    assert "Espera promedio: 7.25" in salida.out
    assert "Retorno promedio: 11.50" in salida.out
    assert "Utilización del CPU: 77.27 %" in salida.out


def test_la_consola_busca_el_catalogo_junto_al_archivo(tmp_path: Path, capsys) -> None:
    shutil.copy(RUTA_CLIENTES, tmp_path / "clientes.csv")
    shutil.copy(RUTA_PROCESOS, tmp_path / "procesos.csv")

    codigo = main(["--archivo", str(tmp_path / "procesos.csv")])

    assert codigo == 0
    assert "Simulación MLQ con 8 procesos" in capsys.readouterr().out


def test_la_consola_informa_un_archivo_inexistente(tmp_path: Path, capsys) -> None:
    codigo = main(
        [
            "--archivo",
            str(tmp_path / "no_existe.csv"),
            "--clientes",
            str(RUTA_CLIENTES),
        ]
    )

    salida = capsys.readouterr()
    assert codigo == 1
    assert salida.out == ""
    assert "no existe el archivo de procesos" in salida.err


def test_la_consola_rechaza_un_archivo_sin_procesos(tmp_path: Path, capsys) -> None:
    ruta = tmp_path / "vacio.csv"
    ruta.write_text(
        "id_proceso,id_cliente,servicio,cantidad_gestiones,tiempo_llegada,rafaga\n",
        encoding="utf-8",
    )

    codigo = main(["--archivo", str(ruta), "--clientes", str(RUTA_CLIENTES)])

    salida = capsys.readouterr()
    assert codigo == 1
    assert salida.out == ""
    assert "sin procesos" in salida.err


def test_una_llegada_tardia_produce_idle_inicial_en_los_cuatro_modos() -> None:
    proceso = crear_proceso("P001", 5, 2)
    configuracion = (
        ConfiguracionCola(
            id_cola="normal",
            nombre="Normal",
            prioridad_cola=1,
            algoritmo=Algoritmo.FIFO,
        ),
    )

    resultados = (
        ejecutar_algoritmo((proceso,), Algoritmo.FIFO),
        ejecutar_algoritmo((proceso,), Algoritmo.SJF),
        ejecutar_algoritmo((proceso,), Algoritmo.ROUND_ROBIN, quantum=3),
        ejecutar_algoritmo((proceso,), Algoritmo.MLQ, configuracion=configuracion),
    )

    for resultado in resultados:
        assert describir_segmentos(resultado) == [
            ("IDLE", 0, 5),
            ("P001", 5, 7),
        ]
        assert resultado.tiempo_cpu_ocupado == 2
        assert resultado.tiempo_cpu_inactivo == 5
        assert resultado.tiempo_total == 7
        assert resultado.utilizacion_cpu == pytest.approx(2 / 7 * 100)
        verificar_invariantes(resultado)


def test_round_robin_con_quantum_mayor_que_las_rafagas_no_deja_idle() -> None:
    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P002", 0, 3, orden_ingreso=1),
    )

    resultado = ejecutar_algoritmo(procesos, Algoritmo.ROUND_ROBIN, quantum=10)

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P002", 2, 5),
    ]
    assert resultado.tiempo_cpu_inactivo == 0
    assert resultado.utilizacion_cpu == pytest.approx(100)
    verificar_invariantes(resultado)


def test_la_consola_rechaza_un_catalogo_que_no_permite_derivar_la_cola(
    tmp_path: Path,
    capsys,
) -> None:
    shutil.copy(RUTA_PROCESOS, tmp_path / "procesos.csv")
    clientes_incompletos = tmp_path / "clientes.csv"
    clientes_incompletos.write_text(
        "id_cliente,nombre,tipo_cliente,prioridad,maximo_gestiones,activo\n"
        "C001,Ana Rojas,VIP,1,3,true\n",
        encoding="utf-8",
    )

    codigo = main(["--archivo", str(tmp_path / "procesos.csv")])

    salida = capsys.readouterr()
    assert codigo == 1
    assert salida.out == ""
    assert "cliente inexistente C003" in salida.err
    with pytest.raises(ErrorValidacion, match="cliente inexistente"):
        ejecutar_desde_archivo(tmp_path / "procesos.csv", clientes_incompletos)
