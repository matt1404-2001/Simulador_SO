"""Estado mutable de la carga que la interfaz conserva entre reruns."""

from collections.abc import Iterable, MutableMapping
from dataclasses import dataclass, field

import streamlit as st

from simulador.dominio.enumeraciones import Servicio
from simulador.dominio.excepciones import ErrorValidacion
from simulador.dominio.modelos import Cliente, Proceso
from simulador.dominio.reglas import derivar_cola, derivar_prioridad

CLAVE_ESTADO_SESION = "estado_simulador"


@dataclass(slots=True)
class EstadoSesion:
    """Carga editable compuesta por catálogo, procesos y cantidad N.

    La clase no depende del navegador ni de un contexto de ejecución de
    Streamlit: la interfaz la obtiene de `st.session_state` mediante
    `obtener_estado` y las pruebas pueden instanciarla directamente.
    """

    clientes: tuple[Cliente, ...] = ()
    procesos: list[Proceso] = field(default_factory=list)
    cantidad_solicitada: int | None = None

    def cargar_catalogo(self, clientes: Iterable[Cliente]) -> None:
        """Reemplaza el catálogo de clientes registrados.

        Un cambio de catálogo no puede dejar procesos apuntando a clientes
        inexistentes; en ese caso se rechaza y se pide reiniciar la carga antes
        de continuar.
        """

        catalogo = tuple(clientes)
        _validar_catalogo(catalogo)
        identificadores = {cliente.id_cliente for cliente in catalogo}
        huerfanos = [
            proceso.id_proceso
            for proceso in self.procesos
            if proceso.id_cliente not in identificadores
        ]
        if huerfanos:
            raise ErrorValidacion(
                "el catálogo no incluye los clientes de los procesos "
                + ", ".join(huerfanos)
                + "; reinicie la carga antes de cambiar el catálogo"
            )
        self.clientes = catalogo

    def importar_procesos(self, procesos: Iterable[Proceso]) -> None:
        """Reemplaza la carga con los procesos recibidos, ya validados."""

        cargados = list(procesos)
        _validar_lista_procesos(cargados)
        for proceso in cargados:
            self._validar_proceso(proceso)
        self.procesos = cargados

    def agregar_proceso(
        self,
        *,
        id_proceso: str,
        id_cliente: str,
        servicio: Servicio,
        cantidad_gestiones: int,
        tiempo_llegada: int,
        rafaga: int,
    ) -> Proceso:
        """Agrega un tiquete manual y deriva su prioridad y cola del cliente.

        El nuevo proceso recibe el siguiente `orden_ingreso`, por lo que FIFO lo
        ubica después de los procesos ya registrados aunque su llegada sea menor.
        """

        if self.buscar_proceso(id_proceso) is not None:
            raise ErrorValidacion(f"el identificador {id_proceso} ya existe en la carga")

        proceso = self._construir_proceso(
            id_proceso=id_proceso,
            id_cliente=id_cliente,
            servicio=servicio,
            cantidad_gestiones=cantidad_gestiones,
            tiempo_llegada=tiempo_llegada,
            rafaga=rafaga,
            orden_ingreso=self._siguiente_orden_ingreso(),
        )
        self.procesos.append(proceso)
        return proceso

    def editar_proceso(
        self,
        id_proceso: str,
        *,
        id_cliente: str,
        servicio: Servicio,
        cantidad_gestiones: int,
        tiempo_llegada: int,
        rafaga: int,
    ) -> Proceso:
        """Reemplaza los datos editables conservando identificador y orden."""

        posicion = self._posicion(id_proceso)
        anterior = self.procesos[posicion]
        actualizado = self._construir_proceso(
            id_proceso=anterior.id_proceso,
            id_cliente=id_cliente,
            servicio=servicio,
            cantidad_gestiones=cantidad_gestiones,
            tiempo_llegada=tiempo_llegada,
            rafaga=rafaga,
            orden_ingreso=anterior.orden_ingreso,
        )
        self.procesos[posicion] = actualizado
        return actualizado

    def eliminar_proceso(self, id_proceso: str) -> None:
        """Quita un proceso de la carga."""

        del self.procesos[self._posicion(id_proceso)]

    def establecer_cantidad_solicitada(self, cantidad: int | None) -> None:
        """Registra la cantidad N indicada por el usuario."""

        if cantidad is None:
            self.cantidad_solicitada = None
            return
        if isinstance(cantidad, bool) or not isinstance(cantidad, int):
            raise ErrorValidacion("N debe ser un número entero")
        if cantidad < 1:
            raise ErrorValidacion("N debe ser mayor o igual que 1")
        self.cantidad_solicitada = cantidad

    def validar_cantidad(self) -> int:
        """Exige que N esté indicada y coincida con los procesos cargados."""

        if self.cantidad_solicitada is None:
            raise ErrorValidacion("indique la cantidad N de procesos")
        cargados = len(self.procesos)
        if cargados != self.cantidad_solicitada:
            raise ErrorValidacion(
                f"N es {self.cantidad_solicitada} y la carga tiene {cargados} procesos; "
                "ajuste N o la carga"
            )
        return self.cantidad_solicitada

    def reiniciar(self) -> None:
        """Limpia procesos y N; el catálogo de clientes se conserva."""

        self.procesos.clear()
        self.cantidad_solicitada = None

    def buscar_proceso(self, id_proceso: str) -> Proceso | None:
        """Devuelve el proceso con ese identificador o `None` si no existe."""

        for proceso in self.procesos:
            if proceso.id_proceso == id_proceso:
                return proceso
        return None

    def buscar_cliente(self, id_cliente: str) -> Cliente | None:
        """Devuelve el cliente registrado o `None` si no está en el catálogo."""

        for cliente in self.clientes:
            if cliente.id_cliente == id_cliente:
                return cliente
        return None

    @property
    def procesos_ordenados(self) -> tuple[Proceso, ...]:
        """Procesos en el orden de ingreso que usa el motor para desempatar."""

        return tuple(sorted(self.procesos, key=lambda proceso: proceso.orden_ingreso))

    def siguiente_id_proceso(self) -> str:
        """Genera un identificador libre con el formato P001."""

        usados = {proceso.id_proceso for proceso in self.procesos}
        numero = 1
        while f"P{numero:03d}" in usados:
            numero += 1
        return f"P{numero:03d}"

    def _construir_proceso(
        self,
        *,
        id_proceso: str,
        id_cliente: str,
        servicio: Servicio,
        cantidad_gestiones: int,
        tiempo_llegada: int,
        rafaga: int,
        orden_ingreso: int,
    ) -> Proceso:
        """Valida el cliente y deriva prioridad y cola antes de crear el proceso."""

        if not self.clientes:
            raise ErrorValidacion("cargue el catálogo de clientes antes de registrar procesos")
        cliente = self.buscar_cliente(id_cliente)
        if cliente is None:
            raise ErrorValidacion(f"el cliente {id_cliente} no está en el catálogo cargado")
        if not cliente.activo:
            raise ErrorValidacion(f"el cliente {id_cliente} está inactivo")
        if (
            isinstance(cantidad_gestiones, int)
            and not isinstance(cantidad_gestiones, bool)
            and cantidad_gestiones > cliente.maximo_gestiones
        ):
            raise ErrorValidacion(
                f"la cantidad de gestiones no puede superar {cliente.maximo_gestiones} "
                f"para el cliente {id_cliente}"
            )

        prioridad = derivar_prioridad(cliente.tipo_cliente)
        return Proceso(
            id_proceso=id_proceso,
            id_cliente=id_cliente,
            servicio=servicio,
            cantidad_gestiones=cantidad_gestiones,
            tiempo_llegada=tiempo_llegada,
            rafaga=rafaga,
            prioridad=prioridad,
            id_cola=derivar_cola(prioridad),
            orden_ingreso=orden_ingreso,
        )

    def _validar_proceso(self, proceso: Proceso) -> None:
        """Comprueba que un proceso importado siga las reglas de su cliente."""

        cliente = self.buscar_cliente(proceso.id_cliente)
        if cliente is None:
            raise ErrorValidacion(
                f"el proceso {proceso.id_proceso} referencia un cliente inexistente "
                f"{proceso.id_cliente}"
            )
        if not cliente.activo:
            raise ErrorValidacion(
                f"el proceso {proceso.id_proceso} referencia al cliente inactivo "
                f"{proceso.id_cliente}"
            )
        if proceso.cantidad_gestiones > cliente.maximo_gestiones:
            raise ErrorValidacion(
                f"el proceso {proceso.id_proceso} supera el máximo de gestiones "
                f"del cliente {proceso.id_cliente}"
            )

    def _posicion(self, id_proceso: str) -> int:
        for posicion, proceso in enumerate(self.procesos):
            if proceso.id_proceso == id_proceso:
                return posicion
        raise ErrorValidacion(f"no existe el proceso {id_proceso} en la carga")

    def _siguiente_orden_ingreso(self) -> int:
        return max((proceso.orden_ingreso for proceso in self.procesos), default=-1) + 1


def _validar_catalogo(catalogo: tuple[Cliente, ...]) -> None:
    """Exige clientes del dominio con identificadores únicos y no vacíos."""

    if not catalogo:
        raise ErrorValidacion("el catálogo de clientes está vacío")
    if any(not isinstance(cliente, Cliente) for cliente in catalogo):
        raise ErrorValidacion("el catálogo contiene un cliente inválido")
    identificadores = [cliente.id_cliente for cliente in catalogo]
    if len(set(identificadores)) != len(identificadores):
        raise ErrorValidacion("el catálogo contiene identificadores de cliente duplicados")


def _validar_lista_procesos(procesos: list[Proceso]) -> None:
    """Exige procesos del dominio con identificadores únicos y no vacíos."""

    if not procesos:
        raise ErrorValidacion("la carga no contiene procesos")
    if any(not isinstance(proceso, Proceso) for proceso in procesos):
        raise ErrorValidacion("la carga contiene un proceso inválido")
    identificadores = [proceso.id_proceso for proceso in procesos]
    if len(set(identificadores)) != len(identificadores):
        raise ErrorValidacion("la carga contiene identificadores de proceso duplicados")


def obtener_estado(
    sesion: MutableMapping[str, object] | None = None,
) -> EstadoSesion:
    """Obtiene o crea el estado del simulador en la sesión indicada.

    Sin argumentos utiliza `st.session_state`. Recibir un diccionario permite
    probar la reutilización del estado sin un navegador ni un runtime de
    Streamlit.
    """

    almacen: MutableMapping[str, object] = st.session_state if sesion is None else sesion
    estado = almacen.get(CLAVE_ESTADO_SESION)
    if not isinstance(estado, EstadoSesion):
        estado = EstadoSesion()
        almacen[CLAVE_ESTADO_SESION] = estado
    return estado


def reiniciar_estado(sesion: MutableMapping[str, object] | None = None) -> EstadoSesion:
    """Limpia procesos y N del estado y devuelve la instancia reutilizada."""

    estado = obtener_estado(sesion)
    estado.reiniciar()
    return estado
