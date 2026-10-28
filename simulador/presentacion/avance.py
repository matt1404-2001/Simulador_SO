"""Reconstrucción y presentación paso a paso de una traza terminada."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from simulador.dominio.enumeraciones import EstadoProceso
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.modelos import (
    ResultadoProceso,
    ResultadoSimulacion,
    SegmentoEjecucion,
)


@dataclass(frozen=True, slots=True)
class EstadoProcesoPaso:
    """Fotografía de un proceso al finalizar un paso de la traza."""

    id_proceso: str
    tiempo_llegada: int
    rafaga: int
    tiempo_restante: int
    estado: EstadoProceso
    id_cola: str | None = None

    @property
    def tiempo_ejecutado(self) -> int:
        """Tiempo de CPU consumido por el proceso hasta este paso."""

        return self.rafaga - self.tiempo_restante


@dataclass(frozen=True, slots=True)
class PasoAvance:
    """Estado de todos los procesos en un instante de la simulación.

    El paso cero representa el estado inicial, antes de ejecutar cualquier
    segmento. Cada paso siguiente aplica exactamente un segmento de la traza.
    """

    indice: int
    tiempo: int
    segmento: SegmentoEjecucion | None
    procesos: tuple[EstadoProcesoPaso, ...]

    @property
    def descripcion(self) -> str:
        """Resume el segmento aplicado o indica que se trata del inicio."""

        if self.segmento is None:
            return "Inicio de la simulación: ningún proceso ha ejecutado todavía."
        if self.segmento.es_inactivo:
            return (
                f"CPU inactivo desde {self.segmento.inicio} hasta {self.segmento.fin}: "
                "no hay procesos listos."
            )
        return (
            f"{self.segmento.id_proceso} ejecuta desde {self.segmento.inicio} hasta "
            f"{self.segmento.fin} en la cola {self.segmento.id_cola or 'sin cola'}."
        )


def construir_pasos(resultado: ResultadoSimulacion) -> tuple[PasoAvance, ...]:
    """Reconstruye el estado y el tiempo restante después de cada segmento.

    La traza producida por el motor es la única fuente de verdad: no se vuelve a
    planificar. Se comprueba que cada proceso consuma exactamente su ráfaga y
    que su última ejecución coincida con el tiempo de finalización informado.
    """

    resultados = {item.id_proceso: item for item in resultado.resultados}
    restante = {id_proceso: item.rafaga for id_proceso, item in resultados.items()}
    finalizacion = {id_proceso: 0 for id_proceso in resultados}

    pasos = [
        PasoAvance(
            indice=0,
            tiempo=0,
            segmento=None,
            procesos=_crear_fichas(resultados, restante, instante=0),
        )
    ]

    for indice, segmento in enumerate(resultado.segmentos, start=1):
        if segmento.id_proceso is not None:
            if segmento.id_proceso not in restante:
                raise ErrorValidacion(
                    f"el segmento referencia un proceso desconocido: {segmento.id_proceso}"
                )
            if segmento.duracion > restante[segmento.id_proceso]:
                raise ErrorValidacion(f"el proceso {segmento.id_proceso} ejecuta más que su ráfaga")
            restante[segmento.id_proceso] -= segmento.duracion
            finalizacion[segmento.id_proceso] = segmento.fin

        pasos.append(
            PasoAvance(
                indice=indice,
                tiempo=segmento.fin,
                segmento=segmento,
                procesos=_crear_fichas(resultados, restante, instante=segmento.fin),
            )
        )

    _validar_cierre(resultados, restante, finalizacion)
    return tuple(pasos)


def _crear_fichas(
    resultados: dict[str, ResultadoProceso],
    restante: dict[str, int],
    *,
    instante: int,
) -> tuple[EstadoProcesoPaso, ...]:
    """Construye la fotografía de todos los procesos en un instante."""

    fichas: list[EstadoProcesoPaso] = []
    for item in resultados.values():
        tiempo_restante = restante[item.id_proceso]
        if tiempo_restante == 0:
            estado = EstadoProceso.TERMINADO
        elif item.tiempo_llegada <= instante:
            estado = EstadoProceso.LISTO
        else:
            estado = EstadoProceso.NUEVO
        fichas.append(
            EstadoProcesoPaso(
                id_proceso=item.id_proceso,
                tiempo_llegada=item.tiempo_llegada,
                rafaga=item.rafaga,
                tiempo_restante=tiempo_restante,
                estado=estado,
                id_cola=item.id_cola,
            )
        )
    return tuple(fichas)


def _validar_cierre(
    resultados: dict[str, ResultadoProceso],
    restante: dict[str, int],
    finalizacion: dict[str, int],
) -> None:
    """Exige que la traza termine todos los procesos cuando el resultado lo afirma."""

    for id_proceso, item in resultados.items():
        if restante[id_proceso] != 0:
            raise ErrorValidacion(f"el proceso {id_proceso} no completó su ráfaga en la traza")
        if finalizacion[id_proceso] != item.tiempo_finalizacion:
            raise ErrorValidacion(f"la finalización de {id_proceso} no coincide con el resultado")


def renderizar_avance(resultado: ResultadoSimulacion, *, clave: str) -> None:
    """Muestra la traza existente paso a paso sin volver a planificar."""

    pasos = construir_pasos(resultado)
    st.markdown("**Avance paso a paso**")
    indice = st.slider(
        "Paso de la traza",
        min_value=0,
        max_value=len(pasos) - 1,
        value=len(pasos) - 1,
        key=f"avance_{clave}",
        help="El paso 0 muestra el estado inicial; cada paso aplica un segmento de la traza.",
    )
    paso = pasos[indice]
    st.caption(paso.descripcion)
    st.dataframe(_tabla_paso(paso), hide_index=True)


def _tabla_paso(paso: PasoAvance) -> pd.DataFrame:
    """Convierte la fotografía del paso en una tabla de presentación."""

    return pd.DataFrame(
        [
            {
                "Proceso": ficha.id_proceso,
                "Cola": ficha.id_cola or "no aplica",
                "Llegada": ficha.tiempo_llegada,
                "Ráfaga": ficha.rafaga,
                "Ejecutado": ficha.tiempo_ejecutado,
                "Restante": ficha.tiempo_restante,
                "Estado": ficha.estado.value,
            }
            for ficha in paso.procesos
        ]
    )
