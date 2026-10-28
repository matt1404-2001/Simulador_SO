"""Prueba de humo de la página Streamlit sin navegador."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from simulador.dominio import Algoritmo

RUTA_APP = Path(__file__).resolve().parents[2] / "app.py"


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

    _boton(at, "Cargar catálogo de ejemplo").click().run()
    _boton(at, "Cargar procesos de ejemplo").click().run()
    at.number_input[0].set_value(8)
    _boton(at, "Aplicar N").click().run()
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
    _boton(at, "Aplicar N").click().run()

    assert not at.exception
    assert any("La carga está lista con 8 procesos" in texto for texto in _mensajes(at.success))
    assert len(at.dataframe[1].value) == 8


def test_reiniciar_limpia_la_carga_pero_conserva_el_catalogo() -> None:
    at = AppTest.from_file(str(RUTA_APP), default_timeout=30).run()
    _boton(at, "Cargar catálogo de ejemplo").click().run()
    _boton(at, "Cargar procesos de ejemplo").click().run()

    _boton(at, "Reiniciar carga").click().run()

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
    _boton(at, "Aplicar configuración").click().run()

    assert not at.exception
    assert any("Round Robin y requiere quantum" in texto for texto in _mensajes(at.error))
