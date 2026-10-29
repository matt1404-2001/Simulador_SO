"""Prueba de humo de la página Streamlit sin navegador."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from simulador.dominio import Algoritmo

RUTA_APP = Path(__file__).resolve().parents[2] / "app.py"

PROCESOS_DOCE = """id_proceso,id_cliente,servicio,cantidad_gestiones,tiempo_llegada,rafaga
P001,C001,Internet,1,0,5
P002,C002,Hosting,1,1,4
P003,C003,Cable,1,2,3
P004,C004,Telefonía,1,3,2
P005,C005,Internet,1,4,6
P006,C006,Cable,1,5,2
P007,C001,Hosting,1,6,3
P008,C002,Telefonía,1,7,4
P009,C003,Internet,1,8,2
P010,C004,Cable,1,9,3
P011,C005,Telefonía,1,10,4
P012,C006,Hosting,1,11,1
"""


def _boton(at: AppTest, etiqueta: str):
    """Localiza un botón por su etiqueta visible."""

    coincidencias = [elemento for elemento in at.button if elemento.label == etiqueta]
    assert coincidencias, f"no existe el botón {etiqueta!r}"
    return coincidencias[0]


def _selectbox(at: AppTest, etiqueta: str):
    """Localiza un selectbox por su etiqueta visible."""

    coincidencias = [elemento for elemento in at.selectbox if elemento.label == etiqueta]
    assert coincidencias, f"no existe el selectbox {etiqueta!r}"
    return coincidencias[0]


def _mensajes(elementos) -> list[str]:
    return [elemento.value for elemento in elementos]


def _preparar_carga(at: AppTest) -> None:
    """Carga el catálogo y los procesos de ejemplo, y fija N en 8."""

    _boton(at, "Preparar demostración").click().run()
    assert not at.exception


def test_la_pagina_prepara_una_carga_de_ejemplo_y_valida_n() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()

    assert not at.exception
    assert at.title[0].value == "Simulador de planificación de procesos"

    _boton(at, "Cargar catálogo de ejemplo").click().run()
    assert not at.exception
    assert "Catálogo cargado con 6 clientes." in _mensajes(at.success)

    _boton(at, "Cargar procesos de ejemplo").click().run()
    assert not at.exception
    assert "Se importaron 8 procesos." in _mensajes(at.success)

    at.number_input[0].set_value(8)
    _boton(at, "Confirmar cantidad").click().run()

    assert not at.exception
    assert any("La carga está lista con 8 procesos" in texto for texto in _mensajes(at.success))
    assert len(at.dataframe[1].value) == 8


def test_reiniciar_limpia_la_carga_pero_conserva_el_catalogo() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _boton(at, "Cargar catálogo de ejemplo").click().run()
    _boton(at, "Cargar procesos de ejemplo").click().run()

    _boton(at, "Reiniciar carga").click().run()
    _boton(at, "Confirmar reinicio").click().run()

    assert not at.exception
    assert any("Se limpiaron los procesos" in texto for texto in _mensajes(at.success))
    assert any("indique la cantidad N" in texto for texto in _mensajes(at.warning))
    assert len(at.dataframe[0].value) == 6
    assert any("La carga no contiene procesos" in texto for texto in _mensajes(at.info))


def test_la_pagina_ejecuta_mlq_y_conserva_el_resultado() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _preparar_carga(at)

    _selectbox(at, "Modalidad de ejecución").select("MLQ").run()
    _boton(at, "Ejecutar simulación").click().run()

    assert not at.exception
    assert "Simulación ejecutada con 8 procesos." in _mensajes(at.success)
    assert any("Última ejecución MLQ: MLQ con 8 procesos" in texto for texto in _mensajes(at.info))

    at.run()
    assert any("Última ejecución MLQ: MLQ con 8 procesos" in texto for texto in _mensajes(at.info))

    _boton(at, "Reiniciar carga").click().run()
    _boton(at, "Confirmar reinicio").click().run()

    assert not at.exception
    assert not any("Última ejecución MLQ" in texto for texto in _mensajes(at.info))


@pytest.mark.parametrize("modalidad", ["FIFO", "SJF", "Round Robin"])
def test_la_pagina_ejecuta_los_algoritmos_individuales(modalidad: str) -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _preparar_carga(at)

    _selectbox(at, "Modalidad de ejecución").select(modalidad).run()
    _boton(at, "Ejecutar simulación").click().run()

    assert not at.exception
    assert "Simulación ejecutada con 8 procesos." in _mensajes(at.success)
    assert any(
        f"Última ejecución individual: {modalidad} con 8 procesos" in texto
        for texto in _mensajes(at.info)
    )


def test_la_pagina_compara_los_tres_algoritmos() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _preparar_carga(at)

    _selectbox(at, "Modalidad de ejecución").select("Comparación").run()
    _boton(at, "Ejecutar simulación").click().run()

    assert not at.exception
    assert "Simulación ejecutada con 8 procesos." in _mensajes(at.success)
    resumen = " ".join(_mensajes(at.info))
    assert "Comparación vigente con quantum 2" in resumen
    assert "FIFO con 8 procesos" in resumen
    assert "SJF con 8 procesos" in resumen
    assert "Round Robin con 8 procesos" in resumen


def test_la_pagina_bloquea_round_robin_sin_quantum() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _preparar_carga(at)

    _selectbox(at, "Algoritmo de la cola Media").set_value(Algoritmo.ROUND_ROBIN)
    _boton(at, "Guardar configuración").click().run()

    assert not at.exception
    assert any("Round Robin y requiere quantum" in texto for texto in _mensajes(at.error))


def _cargador(at: AppTest, etiqueta: str):
    """Localiza un cargador de archivos por su etiqueta visible."""

    coincidencias = [elemento for elemento in at.file_uploader if elemento.label == etiqueta]
    assert coincidencias, f"no existe el cargador {etiqueta!r}"
    return coincidencias[0]


def test_la_pagina_ajusta_la_carga_a_n() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _preparar_carga(at)

    _boton(at, "Agregar proceso").click().run()

    assert not at.exception
    assert len(at.dataframe[1].value) == 9
    assert any("La carga tiene 9 procesos y N es 8" in texto for texto in _mensajes(at.caption))

    _boton(at, "Ajustar la carga a N = 8").click().run()

    assert not at.exception
    assert "Se quitaron: P009." in _mensajes(at.success)
    assert len(at.dataframe[1].value) == 8
    assert any("La carga está lista con 8 procesos" in texto for texto in _mensajes(at.success))


def test_la_pagina_importa_solo_los_primeros_n_procesos() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _boton(at, "Cargar catálogo de ejemplo").click().run()

    at.number_input[0].set_value(8)
    _boton(at, "Confirmar cantidad").click().run()

    cargador = _cargador(at, "Archivo de procesos en CSV")
    cargador.upload("procesos.csv", PROCESOS_DOCE.encode("utf-8"), "text/csv").run()
    _boton(at, "Importar procesos").click().run()

    assert not at.exception
    assert "Se importaron 8 procesos." in _mensajes(at.success)
    assert list(at.dataframe[1].value["Proceso"]) == [f"P{numero:03d}" for numero in range(1, 9)]
    assert not any(boton.label.startswith("Ajustar la carga") for boton in at.button)
