"""Prueba de humo de la página Streamlit sin navegador."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

RUTA_APP = Path(__file__).resolve().parents[2] / "app.py"


def _boton(at: AppTest, etiqueta: str):
    """Localiza un botón por su etiqueta visible."""

    coincidencias = [elemento for elemento in at.button if elemento.label == etiqueta]
    assert coincidencias, f"no existe el botón {etiqueta!r}"
    return coincidencias[0]


def _mensajes(elementos) -> list[str]:
    return [elemento.value for elemento in elementos]


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
