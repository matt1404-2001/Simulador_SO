"""Pruebas del planificador Round Robin."""

import pytest

from simulador.dominio import (
    Algoritmo,
    ConfiguracionCola,
    ErrorConfiguracion,
    ErrorValidacion,
    EstadoProceso,
)
from simulador.dominio.planificadores import PlanificadorRoundRobin
from tests.dominio.ayudas import crear_proceso, describir_segmentos, verificar_invariantes


def test_rr_con_quantum_menor_que_la_rafaga_reparte_en_varios_segmentos() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 1, 3, orden_ingreso=1),
        crear_proceso("P003", 2, 1, orden_ingreso=2),
    )

    resultado = PlanificadorRoundRobin(quantum=2).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P002", 2, 4),
        ("P003", 4, 5),
        ("P001", 5, 7),
        ("P002", 7, 8),
        ("P001", 8, 9),
    ]
    assert resultado.algoritmo is Algoritmo.ROUND_ROBIN
    finalizaciones = [
        resultado_proceso.tiempo_finalizacion for resultado_proceso in resultado.resultados
    ]
    assert finalizaciones == [9, 8, 5]
    assert [resultado_proceso.tiempo_espera for resultado_proceso in resultado.resultados] == [
        4,
        4,
        2,
    ]
    assert resultado.promedio_espera == pytest.approx(10 / 3)
    assert resultado.promedio_retorno == pytest.approx(19 / 3)
    assert resultado.utilizacion_cpu == pytest.approx(100)
    verificar_invariantes(resultado)


def test_rr_con_quantum_igual_a_la_rafaga_no_fragmenta_los_procesos() -> None:
    procesos = (
        crear_proceso("P001", 0, 3, orden_ingreso=0),
        crear_proceso("P002", 0, 3, orden_ingreso=1),
    )

    resultado = PlanificadorRoundRobin(quantum=3).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 3),
        ("P002", 3, 6),
    ]
    assert [segmento.duracion for segmento in resultado.segmentos] == [3, 3]
    verificar_invariantes(resultado)


def test_rr_con_quantum_mayor_que_la_rafaga_termina_en_un_solo_segmento() -> None:
    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P002", 1, 2, orden_ingreso=1),
    )

    resultado = PlanificadorRoundRobin(quantum=5).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 2),
        ("P002", 2, 4),
    ]
    assert len(resultado.segmentos) == 2
    assert resultado.resultados[1].tiempo_espera == 1
    verificar_invariantes(resultado)


def test_rr_incorpora_las_llegadas_del_quantum_antes_de_reingresar() -> None:
    procesos = (
        crear_proceso("P001", 0, 6, orden_ingreso=0),
        crear_proceso("P002", 2, 2, orden_ingreso=1),
    )

    resultado = PlanificadorRoundRobin(quantum=4).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 4),
        ("P002", 4, 6),
        ("P001", 6, 8),
    ]
    assert resultado.resultados[1].tiempo_espera == 2
    verificar_invariantes(resultado)


def test_rr_reingresa_al_final_de_la_cola_despues_de_las_llegadas() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 1, 1, orden_ingreso=1),
        crear_proceso("P003", 2, 1, orden_ingreso=2),
    )

    resultado = PlanificadorRoundRobin(quantum=3).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 3),
        ("P002", 3, 4),
        ("P003", 4, 5),
        ("P001", 5, 7),
    ]
    verificar_invariantes(resultado)


def test_rr_ordena_las_llegadas_simultaneas_por_ingreso_e_identificador() -> None:
    procesos = (
        crear_proceso("P002", 0, 1, orden_ingreso=1),
        crear_proceso("P003", 0, 1, orden_ingreso=0),
        crear_proceso("P001", 0, 1, orden_ingreso=0),
    )

    resultado = PlanificadorRoundRobin(quantum=1).planificar(procesos, ())

    assert [segmento.etiqueta for segmento in resultado.segmentos] == [
        "P001",
        "P003",
        "P002",
    ]


def test_rr_inserta_idle_inicial_hasta_la_primera_llegada() -> None:
    procesos = (crear_proceso("P001", 3, 2),)

    resultado = PlanificadorRoundRobin(quantum=2).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("IDLE", 0, 3),
        ("P001", 3, 5),
    ]
    assert resultado.tiempo_cpu_inactivo == 3
    assert resultado.utilizacion_cpu == pytest.approx(40)
    verificar_invariantes(resultado)


def test_rr_inserta_idle_entre_llegadas_distantes() -> None:
    procesos = (
        crear_proceso("P001", 0, 1, orden_ingreso=0),
        crear_proceso("P002", 5, 1, orden_ingreso=1),
    )

    resultado = PlanificadorRoundRobin(quantum=2).planificar(procesos, ())

    assert describir_segmentos(resultado) == [
        ("P001", 0, 1),
        ("IDLE", 1, 5),
        ("P002", 5, 6),
    ]
    assert resultado.tiempo_cpu_inactivo == 4
    verificar_invariantes(resultado)


@pytest.mark.parametrize("quantum", [0, -1, -5])
def test_rr_rechaza_quantum_cero_o_negativo(quantum: int) -> None:
    with pytest.raises(ErrorConfiguracion, match="mayor que cero"):
        PlanificadorRoundRobin(quantum=quantum)


def test_rr_rechaza_quantum_no_entero() -> None:
    with pytest.raises(ErrorConfiguracion, match="entero"):
        PlanificadorRoundRobin(quantum=2.5)  # type: ignore[arg-type]


def test_rr_conserva_la_configuracion_recibida() -> None:
    configuracion = (
        ConfiguracionCola(
            id_cola="normal",
            nombre="Normal",
            prioridad_cola=3,
            algoritmo=Algoritmo.ROUND_ROBIN,
            quantum=2,
        ),
    )

    resultado = PlanificadorRoundRobin(quantum=2).planificar(
        (crear_proceso("P001", 0, 2),),
        configuracion,
    )

    assert resultado.configuraciones_colas == configuracion


def test_rr_no_modifica_la_carga_original() -> None:
    procesos = (
        crear_proceso("P001", 0, 5, orden_ingreso=0),
        crear_proceso("P002", 1, 3, orden_ingreso=1),
    )
    copia = tuple(procesos)

    PlanificadorRoundRobin(quantum=2).planificar(procesos, ())

    assert procesos == copia
    assert [proceso.tiempo_restante for proceso in procesos] == [5, 3]
    assert all(proceso.estado is EstadoProceso.NUEVO for proceso in procesos)


def test_rr_rechaza_carga_vacia() -> None:
    with pytest.raises(ErrorValidacion, match="sin procesos"):
        PlanificadorRoundRobin(quantum=2).planificar((), ())


def test_rr_rechaza_identificadores_duplicados() -> None:
    procesos = (
        crear_proceso("P001", 0, 2, orden_ingreso=0),
        crear_proceso("P001", 1, 2, orden_ingreso=1),
    )

    with pytest.raises(ErrorValidacion, match="duplicados"):
        PlanificadorRoundRobin(quantum=1).planificar(procesos, ())
