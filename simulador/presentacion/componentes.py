"""Componentes de Streamlit para preparar la carga del simulador."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

import pandas as pd
import streamlit as st

from simulador.aplicacion import Comparacion, comparar_algoritmos, ejecutar_algoritmo
from simulador.dominio.enumeraciones import Algoritmo, Servicio
from simulador.dominio.excepciones import ErrorDominio, ErrorValidacion
from simulador.dominio.modelos import Cliente, ResultadoSimulacion
from simulador.dominio.reglas import ID_COLA_POR_PRIORIDAD
from simulador.infraestructura import (
    cargar_clientes,
    cargar_procesos,
    generar_csv_metricas,
    generar_csv_resultados,
    generar_csv_traza,
)
from simulador.presentacion.avance import renderizar_avance
from simulador.presentacion.estado_sesion import (
    NOMBRES_COLA,
    ColaEditable,
    EstadoSesion,
    construir_colas,
    tipos_cliente_de_cola,
)
from simulador.presentacion.gantt import renderizar_gantt

MODALIDADES = ("FIFO", "SJF", "Round Robin", "MLQ", "Comparación")
ALGORITMOS_POR_MODALIDAD = {
    "FIFO": Algoritmo.FIFO,
    "SJF": Algoritmo.SJF,
    "Round Robin": Algoritmo.ROUND_ROBIN,
}
ALGORITMOS_DE_COLA = (Algoritmo.FIFO, Algoritmo.SJF, Algoritmo.ROUND_ROBIN)

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
        "La prioridad y la cola se derivan del tipo de cliente. Ajuste la configuración de "
        "colas y ejecute la simulación en las secciones siguientes."
    )


def renderizar_configuracion(estado: EstadoSesion) -> None:
    """Permite ajustar prioridad, algoritmo y quantum de las colas MLQ."""

    st.header("4. Configuración de colas MLQ")
    st.caption(
        "Cada proceso entra a la cola derivada de su tipo de cliente. Menor prioridad se "
        "atiende primero; si dos colas empatan, se usa el orden en que aparecen."
    )

    actuales = {cola.id_cola: cola for cola in estado.configuracion_colas}
    with st.form("formulario_configuracion"):
        especificaciones: list[ColaEditable] = []
        for id_cola, nombre in NOMBRES_COLA.items():
            actual = actuales.get(id_cola)
            tipos = ", ".join(tipo.value for tipo in tipos_cliente_de_cola(id_cola))
            st.markdown(f"**Cola {nombre}** - tipos de cliente: {tipos}")
            columnas = st.columns(3)
            with columnas[0]:
                prioridad = st.number_input(
                    f"Prioridad de la cola {nombre}",
                    min_value=1,
                    step=1,
                    value=actual.prioridad_cola if actual else _prioridad_canonica(id_cola),
                    key=f"prioridad_{id_cola}",
                )
            with columnas[1]:
                algoritmo = st.selectbox(
                    f"Algoritmo de la cola {nombre}",
                    ALGORITMOS_DE_COLA,
                    index=(ALGORITMOS_DE_COLA.index(actual.algoritmo) if actual else 0),
                    key=f"algoritmo_{id_cola}",
                )
            with columnas[2]:
                quantum_actual = (
                    actual.quantum if actual and actual.algoritmo is Algoritmo.ROUND_ROBIN else None
                )
                quantum = st.number_input(
                    f"Quantum de la cola {nombre}",
                    min_value=1,
                    step=1,
                    value=quantum_actual,
                    key=f"quantum_{id_cola}",
                    help="Obligatorio solo cuando la cola usa Round Robin.",
                )
            especificaciones.append(
                ColaEditable(
                    id_cola=id_cola,
                    prioridad_cola=int(prioridad),
                    algoritmo=algoritmo,
                    quantum=(
                        int(quantum)
                        if algoritmo is Algoritmo.ROUND_ROBIN and quantum is not None
                        else None
                    ),
                )
            )
        aplicar = st.form_submit_button("Aplicar configuración")

    if aplicar:
        try:
            estado.establecer_configuracion(construir_colas(especificaciones))
        except ErrorDominio as error:
            st.error(f"No se pudo aplicar la configuración: {error}.")
        else:
            st.success("Configuración de colas aplicada. Los resultados anteriores se descartaron.")

    st.dataframe(_tabla_configuracion(estado), hide_index=True)


def renderizar_ejecucion(estado: EstadoSesion) -> None:
    """Ejecuta la modalidad elegida con la carga y la configuración vigentes."""

    st.header("5. Ejecución")
    try:
        cantidad = estado.validar_cantidad()
    except ErrorValidacion as error:
        st.warning(f"No se puede ejecutar todavía: {error}.")
        return

    modalidad = st.selectbox(
        "Modalidad de ejecución",
        MODALIDADES,
        key="modalidad_ejecucion",
    )

    quantum: int | None = None
    if modalidad in ("Round Robin", "Comparación"):
        valor_inicial = estado.quantum_comparacion if modalidad == "Comparación" else 2
        quantum = int(
            st.number_input(
                "Quantum de la ejecución",
                min_value=1,
                step=1,
                value=valor_inicial,
                key=f"quantum_ejecucion_{modalidad}",
            )
        )
        if modalidad == "Comparación":
            estado.establecer_quantum_comparacion(quantum)

    if st.button("Ejecutar simulación", key="ejecutar_simulacion"):
        try:
            _ejecutar(estado, modalidad, quantum)
        except ErrorDominio as error:
            st.error(f"No se pudo ejecutar la simulación: {error}.")
        else:
            st.success(f"Simulación ejecutada con {cantidad} procesos.")


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


def _ejecutar(estado: EstadoSesion, modalidad: str, quantum: int | None) -> None:
    """Llama al caso de uso correspondiente y conserva su resultado en la sesión."""

    procesos = estado.procesos_ordenados
    if modalidad == "MLQ":
        resultado = ejecutar_algoritmo(
            procesos,
            Algoritmo.MLQ,
            configuracion=estado.configuracion_colas,
        )
        estado.registrar_resultado_mlq(resultado)
        return

    if modalidad == "Comparación":
        if quantum is None:
            raise ErrorValidacion("la comparación requiere un quantum")
        comparacion = comparar_algoritmos(procesos, quantum=quantum)
        estado.registrar_comparacion(comparacion, quantum=quantum)
        return

    algoritmo = ALGORITMOS_POR_MODALIDAD[modalidad]
    resultado = ejecutar_algoritmo(
        procesos,
        algoritmo,
        quantum=quantum if algoritmo is Algoritmo.ROUND_ROBIN else None,
    )
    estado.registrar_resultado_individual(resultado)


def renderizar_resultados(estado: EstadoSesion) -> None:
    """Muestra Gantt, métricas, avance paso a paso y descargas vigentes."""

    st.header("6. Resultados")
    _renderizar_resumen_resultados(estado)

    if estado.resultado_individual is not None:
        _renderizar_resultado(estado.resultado_individual, clave="individual")
    if estado.resultado_mlq is not None:
        _renderizar_resultado(estado.resultado_mlq, clave="mlq")
    if estado.comparacion is not None:
        _renderizar_comparacion(estado.comparacion, quantum=estado.quantum_comparacion)


def _renderizar_resumen_resultados(estado: EstadoSesion) -> None:
    """Anuncia qué resultados siguen vigentes después del último rerun."""

    if (
        estado.resultado_individual is None
        and estado.resultado_mlq is None
        and estado.comparacion is None
    ):
        st.info(
            "Ejecute una simulación para consultar el Gantt, las métricas y el avance paso a paso."
        )
        return

    if estado.resultado_individual is not None:
        st.info("Última ejecución individual: " + _resumen_resultado(estado.resultado_individual))
    if estado.resultado_mlq is not None:
        st.info("Última ejecución MLQ: " + _resumen_resultado(estado.resultado_mlq))
    if estado.comparacion is not None:
        resumenes = " | ".join(
            _resumen_resultado(resultado) for resultado in estado.comparacion.resultados
        )
        st.info(f"Comparación vigente con quantum {estado.quantum_comparacion}: {resumenes}")


def _renderizar_resultado(resultado: ResultadoSimulacion, *, clave: str) -> None:
    """Presenta una ejecución individual o MLQ con todos sus detalles."""

    st.subheader(f"{resultado.algoritmo.value} con {len(resultado.resultados)} procesos")
    _renderizar_metricas(resultado)
    renderizar_gantt(resultado)

    st.markdown("**Resultados por proceso**")
    st.dataframe(_tabla_resultados(resultado), hide_index=True)

    renderizar_avance(resultado, clave=clave)
    _renderizar_descargas(resultado, clave=clave)


def _renderizar_metricas(resultado: ResultadoSimulacion) -> None:
    """Muestra las métricas globales ya calculadas por el dominio."""

    columnas = st.columns(5)
    columnas[0].metric("Espera promedio", f"{resultado.promedio_espera:.2f}")
    columnas[1].metric("Retorno promedio", f"{resultado.promedio_retorno:.2f}")
    columnas[2].metric("CPU ocupado", resultado.tiempo_cpu_ocupado)
    columnas[3].metric("CPU inactivo", resultado.tiempo_cpu_inactivo)
    columnas[4].metric("Utilización", f"{resultado.utilizacion_cpu:.2f} %")


def _renderizar_comparacion(comparacion: Comparacion, *, quantum: int) -> None:
    """Resume los algoritmos comparados y permite abrir cada detalle."""

    st.subheader(f"Comparación de algoritmos con quantum {quantum}")
    st.dataframe(_tabla_comparacion(comparacion), hide_index=True)

    for resultado in comparacion.resultados:
        clave = f"comparacion_{resultado.algoritmo.name.lower()}"
        with st.expander(f"Detalle de {resultado.algoritmo.value}"):
            _renderizar_metricas(resultado)
            renderizar_gantt(resultado)
            st.dataframe(_tabla_resultados(resultado), hide_index=True)
            renderizar_avance(resultado, clave=clave)
            _renderizar_descargas(resultado, clave=clave)


def _renderizar_descargas(resultado: ResultadoSimulacion, *, clave: str) -> None:
    """Ofrece la traza, los resultados por proceso y las métricas en CSV."""

    sufijo = resultado.algoritmo.name.lower()
    st.markdown("**Descarga de resultados**")
    columnas = st.columns(3)
    columnas[0].download_button(
        "Traza en CSV",
        data=generar_csv_traza(resultado),
        file_name=f"traza_{sufijo}.csv",
        mime="text/csv",
        key=f"descarga_traza_{clave}",
    )
    columnas[1].download_button(
        "Resultados por proceso",
        data=generar_csv_resultados(resultado),
        file_name=f"resultados_{sufijo}.csv",
        mime="text/csv",
        key=f"descarga_resultados_{clave}",
    )
    columnas[2].download_button(
        "Métricas en CSV",
        data=generar_csv_metricas(resultado),
        file_name=f"metricas_{sufijo}.csv",
        mime="text/csv",
        key=f"descarga_metricas_{clave}",
    )


def _tabla_resultados(resultado: ResultadoSimulacion) -> pd.DataFrame:
    """Convierte los resultados por proceso en una tabla de presentación."""

    return pd.DataFrame(
        [
            {
                "Proceso": item.id_proceso,
                "Cola": item.id_cola or "no aplica",
                "Llegada": item.tiempo_llegada,
                "Ráfaga": item.rafaga,
                "Finalización": item.tiempo_finalizacion,
                "Espera": item.tiempo_espera,
                "Retorno": item.tiempo_retorno,
            }
            for item in resultado.resultados
        ]
    )


def _tabla_comparacion(comparacion: Comparacion) -> pd.DataFrame:
    """Resume las métricas de FIFO, SJF y Round Robin en una sola tabla."""

    return pd.DataFrame(
        [
            {
                "Algoritmo": resultado.algoritmo.value,
                "Espera promedio": round(resultado.promedio_espera, 2),
                "Retorno promedio": round(resultado.promedio_retorno, 2),
                "CPU ocupado": resultado.tiempo_cpu_ocupado,
                "CPU inactivo": resultado.tiempo_cpu_inactivo,
                "Utilización (%)": round(resultado.utilizacion_cpu, 2),
            }
            for resultado in comparacion.resultados
        ]
    )


def _resumen_resultado(resultado: ResultadoSimulacion) -> str:
    """Resume métricas ya calculadas por el motor."""

    return (
        f"{resultado.algoritmo.value} con {len(resultado.resultados)} procesos; "
        f"espera promedio {resultado.promedio_espera:.2f}, "
        f"retorno promedio {resultado.promedio_retorno:.2f}, "
        f"utilización {resultado.utilizacion_cpu:.2f} %."
    )


def _prioridad_canonica(id_cola: str) -> int:
    """Obtiene la prioridad que el dominio asigna por convención a una cola."""

    return next(prioridad for prioridad, cola in ID_COLA_POR_PRIORIDAD.items() if cola == id_cola)


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


def _tabla_configuracion(estado: EstadoSesion) -> pd.DataFrame:
    """Convierte la configuración MLQ en una tabla de presentación."""

    return pd.DataFrame(
        [
            {
                "Cola": cola.nombre,
                "Prioridad": cola.prioridad_cola,
                "Algoritmo": cola.algoritmo.value,
                "Quantum": str(cola.quantum) if cola.quantum is not None else "no aplica",
                "Tipos de cliente": ", ".join(tipo.value for tipo in cola.tipos_cliente),
            }
            for cola in estado.configuracion_colas
        ]
    )


@contextmanager
def _archivo_temporal(archivo: ArchivoCargado) -> Iterator[Path]:
    """Escribe el archivo subido en una carpeta temporal durante la importación."""

    with TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / (Path(archivo.name).name or "carga.csv")
        ruta.write_bytes(archivo.getvalue())
        yield ruta
