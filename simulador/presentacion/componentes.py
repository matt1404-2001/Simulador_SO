"""Componentes de Streamlit para preparar la carga del simulador."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import pandas as pd
import streamlit as st

from simulador.dominio.enumeraciones import Servicio
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.modelos import Cliente
from simulador.infraestructura import cargar_clientes, cargar_procesos
from simulador.presentacion.estado_sesion import EstadoSesion

RUTA_DATOS = Path(__file__).resolve().parents[2] / "data"


class ArchivoCargado(Protocol):
    """Contrato mínimo que necesita un archivo subido desde la interfaz."""

    name: str

    def getvalue(self) -> bytes:
        """Devuelve el contenido completo del archivo."""


def renderizar_catalogo(estado: EstadoSesion) -> None:
    """Muestra la carga del catálogo de clientes registrados."""

    st.header("1. Catálogo de clientes")
    st.caption("Solo un cliente activo del catálogo puede generar tiquetes de proceso.")

    columnas = st.columns(2)
    with columnas[0]:
        if st.button("Cargar catálogo de ejemplo", key="catalogo_ejemplo"):
            _cargar_catalogo(estado, RUTA_DATOS / "clientes.csv")
    with columnas[1]:
        archivo = st.file_uploader("Archivo de clientes en CSV", type=["csv"], key="clientes_csv")
        if archivo is not None and st.button("Importar catálogo", key="importar_clientes"):
            with _archivo_temporal(archivo) as ruta:
                _cargar_catalogo(estado, ruta)

    if not estado.clientes:
        st.info("Cargue el catálogo de ejemplo o importe un archivo de clientes para continuar.")
        return

    st.caption(f"Clientes en el catálogo: {len(estado.clientes)}")
    st.dataframe(_tabla_clientes(estado), hide_index=True)


def renderizar_procesos(estado: EstadoSesion) -> None:
    """Muestra la cantidad N, la importación y la edición manual de procesos."""

    st.header("2. Carga de procesos")
    if st.button("Reiniciar carga", key="reiniciar_carga"):
        estado.reiniciar()
        st.success("Se limpiaron los procesos y N. El catálogo de clientes se conserva.")
    _renderizar_cantidad(estado)
    _renderizar_importacion(estado)
    _renderizar_alta(estado)
    if estado.procesos:
        _renderizar_edicion(estado)


def renderizar_resumen(estado: EstadoSesion) -> None:
    """Muestra la carga vigente y comprueba que coincida con N."""

    st.header("3. Carga preparada")

    try:
        cantidad = estado.validar_cantidad()
    except ErrorValidacion as error:
        st.warning(f"La carga todavía no está lista: {error}.")
    else:
        st.success(f"La carga está lista con {cantidad} procesos. Se usará en la ejecución.")

    if not estado.procesos:
        st.info("La carga no contiene procesos.")
        return

    st.dataframe(_tabla_procesos(estado), hide_index=True)
    st.caption(
        "La prioridad y la cola se derivan del tipo de cliente. La configuración de colas y la "
        "ejecución se incorporan en la siguiente etapa."
    )


def _renderizar_cantidad(estado: EstadoSesion) -> None:
    """Solicita N y lo contrasta con la cantidad de procesos válidos."""

    with st.form("formulario_cantidad"):
        columnas = st.columns([1, 2])
        with columnas[0]:
            cantidad = st.number_input(
                "Cantidad N de procesos",
                min_value=1,
                step=1,
                value=estado.cantidad_solicitada or 1,
            )
        with columnas[1]:
            st.caption(
                "N es la cantidad de procesos válidos que debe contener la carga para ejecutar "
                "la simulación."
            )
            aplicar = st.form_submit_button("Aplicar N")
        if aplicar:
            try:
                estado.establecer_cantidad_solicitada(int(cantidad))
            except ErrorValidacion as error:
                st.error(f"No se pudo registrar N: {error}.")
            else:
                st.success(f"N quedó establecida en {estado.cantidad_solicitada}.")


def _renderizar_importacion(estado: EstadoSesion) -> None:
    """Importa procesos desde el archivo de ejemplo o uno subido por el usuario."""

    st.subheader("Importar procesos")
    if not estado.clientes:
        st.info("Importe primero el catálogo de clientes.")
        return

    columnas = st.columns(2)
    with columnas[0]:
        if st.button("Cargar procesos de ejemplo", key="procesos_ejemplo"):
            _importar_procesos(estado, RUTA_DATOS / "procesos_ejemplo.csv")
    with columnas[1]:
        archivo = st.file_uploader("Archivo de procesos en CSV", type=["csv"], key="procesos_csv")
        if archivo is not None and st.button("Importar procesos", key="importar_procesos"):
            with _archivo_temporal(archivo) as ruta:
                _importar_procesos(estado, ruta)


def _renderizar_alta(estado: EstadoSesion) -> None:
    """Formulario para agregar un tiquete manualmente."""

    st.subheader("Agregar un proceso")
    opciones = _opciones_clientes(estado.clientes, solo_activos=True)
    if not opciones:
        st.info("El catálogo no tiene clientes activos; revise el archivo de clientes.")
        return

    with st.form("formulario_alta"):
        columnas = st.columns(2)
        with columnas[0]:
            id_proceso = st.text_input(
                "Identificador del proceso", value=estado.siguiente_id_proceso()
            )
            etiqueta_cliente = st.selectbox("Cliente", list(opciones))
        with columnas[1]:
            servicio = st.selectbox("Servicio", list(Servicio))
            cantidad_gestiones = st.number_input(
                "Cantidad de gestiones", min_value=1, step=1, value=1
            )
        columnas_tiempo = st.columns(2)
        with columnas_tiempo[0]:
            tiempo_llegada = st.number_input("Tiempo de llegada", min_value=0, step=1, value=0)
        with columnas_tiempo[1]:
            rafaga = st.number_input("Ráfaga", min_value=1, step=1, value=1)
        agregar = st.form_submit_button("Agregar proceso")

    if not agregar:
        return

    try:
        proceso = estado.agregar_proceso(
            id_proceso=id_proceso,
            id_cliente=opciones[etiqueta_cliente].id_cliente,
            servicio=servicio,
            cantidad_gestiones=int(cantidad_gestiones),
            tiempo_llegada=int(tiempo_llegada),
            rafaga=int(rafaga),
        )
    except ErrorValidacion as error:
        st.error(f"No se pudo agregar el proceso: {error}.")
    else:
        st.success(
            f"Proceso {proceso.id_proceso} agregado a la cola {proceso.id_cola} "
            f"con prioridad {proceso.prioridad}."
        )


def _renderizar_edicion(estado: EstadoSesion) -> None:
    """Permite editar los datos de un proceso o eliminarlo de la carga."""

    st.subheader("Editar o eliminar un proceso")
    identificadores = [proceso.id_proceso for proceso in estado.procesos_ordenados]
    seleccionado = st.selectbox("Proceso", identificadores, key="proceso_seleccionado")
    proceso = estado.buscar_proceso(seleccionado)
    if proceso is None:
        st.info("El proceso seleccionado ya no está en la carga.")
        return

    opciones = _opciones_clientes(estado.clientes, solo_activos=False)
    etiquetas = list(opciones)
    indice_cliente = next(
        (
            posicion
            for posicion, etiqueta in enumerate(etiquetas)
            if opciones[etiqueta].id_cliente == proceso.id_cliente
        ),
        0,
    )

    with st.form(f"formulario_edicion_{seleccionado}"):
        columnas = st.columns(2)
        with columnas[0]:
            etiqueta_cliente = st.selectbox("Cliente", etiquetas, index=indice_cliente)
            servicio = st.selectbox(
                "Servicio", list(Servicio), index=list(Servicio).index(proceso.servicio)
            )
        with columnas[1]:
            cantidad_gestiones = st.number_input(
                "Cantidad de gestiones",
                min_value=1,
                step=1,
                value=proceso.cantidad_gestiones,
            )
        columnas_tiempo = st.columns(2)
        with columnas_tiempo[0]:
            tiempo_llegada = st.number_input(
                "Tiempo de llegada",
                min_value=0,
                step=1,
                value=proceso.tiempo_llegada,
            )
        with columnas_tiempo[1]:
            rafaga = st.number_input("Ráfaga", min_value=1, step=1, value=proceso.rafaga)
        guardar = st.form_submit_button("Guardar cambios")

    if guardar:
        try:
            actualizado = estado.editar_proceso(
                seleccionado,
                id_cliente=opciones[etiqueta_cliente].id_cliente,
                servicio=servicio,
                cantidad_gestiones=int(cantidad_gestiones),
                tiempo_llegada=int(tiempo_llegada),
                rafaga=int(rafaga),
            )
        except ErrorValidacion as error:
            st.error(f"No se pudo editar el proceso: {error}.")
        else:
            st.success(f"Proceso {actualizado.id_proceso} actualizado.")

    with st.form(f"formulario_eliminacion_{seleccionado}"):
        confirmar = st.checkbox("Confirmo la eliminación del proceso seleccionado")
        eliminar = st.form_submit_button("Eliminar proceso")
    if eliminar:
        if not confirmar:
            st.warning("Marque la confirmación antes de eliminar el proceso.")
        else:
            try:
                estado.eliminar_proceso(seleccionado)
            except ErrorValidacion as error:
                st.error(f"No se pudo eliminar el proceso: {error}.")
            else:
                st.success(f"Proceso {seleccionado} eliminado.")


def _cargar_catalogo(estado: EstadoSesion, ruta: Path) -> None:
    """Lee el catálogo y lo aplica al estado, informando cualquier rechazo."""

    try:
        clientes = cargar_clientes(ruta)
        estado.cargar_catalogo(clientes)
    except ErrorValidacion as error:
        st.error(f"No se pudo cargar el catálogo: {error}.")
    else:
        st.success(f"Catálogo cargado con {len(clientes)} clientes.")


def _importar_procesos(estado: EstadoSesion, ruta: Path) -> None:
    """Lee los procesos, los valida contra el catálogo y reemplaza la carga."""

    try:
        procesos = cargar_procesos(ruta, estado.clientes)
        estado.importar_procesos(procesos)
    except ErrorValidacion as error:
        st.error(f"No se pudieron importar los procesos: {error}.")
    else:
        st.success(f"Se importaron {len(procesos)} procesos.")


def _opciones_clientes(
    clientes: tuple[Cliente, ...],
    *,
    solo_activos: bool,
) -> dict[str, Cliente]:
    """Construye etiquetas legibles para los clientes que admite cada formulario."""

    return {
        f"{cliente.id_cliente} - {cliente.nombre} ({cliente.tipo_cliente.value})": cliente
        for cliente in clientes
        if cliente.activo or not solo_activos
    }


def _tabla_clientes(estado: EstadoSesion) -> pd.DataFrame:
    """Convierte el catálogo en una tabla de presentación."""

    return pd.DataFrame(
        [
            {
                "Identificador": cliente.id_cliente,
                "Nombre": cliente.nombre,
                "Tipo": cliente.tipo_cliente.value,
                "Prioridad": cliente.prioridad,
                "Máximo de gestiones": cliente.maximo_gestiones,
                "Activo": "Sí" if cliente.activo else "No",
            }
            for cliente in estado.clientes
        ]
    )


def _tabla_procesos(estado: EstadoSesion) -> pd.DataFrame:
    """Convierte la carga en una tabla de presentación con los datos derivados."""

    nombres = {cliente.id_cliente: cliente.nombre for cliente in estado.clientes}
    return pd.DataFrame(
        [
            {
                "Proceso": proceso.id_proceso,
                "Cliente": f"{proceso.id_cliente} - {nombres.get(proceso.id_cliente, '')}",
                "Servicio": proceso.servicio.value,
                "Gestiones": proceso.cantidad_gestiones,
                "Llegada": proceso.tiempo_llegada,
                "Ráfaga": proceso.rafaga,
                "Prioridad": proceso.prioridad,
                "Cola": proceso.id_cola,
                "Ingreso": proceso.orden_ingreso,
            }
            for proceso in estado.procesos_ordenados
        ]
    )


@contextmanager
def _archivo_temporal(archivo: ArchivoCargado) -> Iterator[Path]:
    """Escribe el archivo subido en una carpeta temporal durante la importación."""

    with TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / (Path(archivo.name).name or "carga.csv")
        ruta.write_bytes(archivo.getvalue())
        yield ruta
