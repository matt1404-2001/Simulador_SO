"""Estado mutable de la carga que la interfaz conserva entre reruns."""

from collections.abc import Iterable, MutableMapping
from dataclasses import dataclass, field
from types import MappingProxyType

import streamlit as st

from simulador.aplicacion.comparar import Comparacion
from simulador.dominio.enumeraciones import Algoritmo, Servicio, TipoCliente
from simulador.dominio.excepciones import ErrorConfiguracion, ErrorValidacion
from simulador.dominio.modelos import (
    Cliente,
    ConfiguracionCola,
    Proceso,
    ResultadoSimulacion,
)
from simulador.dominio.reglas import REGLAS_TIPO_CLIENTE, derivar_cola, derivar_prioridad

CLAVE_ESTADO_SESION = "estado_simulador"

# Las cuatro colas fijas se derivan de la prioridad del cliente y conservan esos
# identificadores en todo el sistema; la interfaz solo edita su comportamiento.
NOMBRES_COLA = MappingProxyType(
    {"alta": "Alta", "media": "Media", "normal": "Normal", "baja": "Baja"}
)
QUANTUM_COMPARACION_POR_DEFECTO = 2


@dataclass(frozen=True, slots=True)
class ColaEditable:
    """Valores que la interfaz captura antes de construir una cola MLQ.

    El nombre y los tipos de cliente no se editan: se derivan de `reglas.py` para
    que la configuración no contradiga la cola asignada a cada proceso.
    """

    id_cola: str
    prioridad_cola: int
    algoritmo: Algoritmo
    quantum: int | None = None


def tipos_cliente_de_cola(id_cola: str) -> tuple[TipoCliente, ...]:
    """Devuelve los tipos de cliente que el dominio envía a esa cola."""

    return tuple(tipo for tipo, regla in REGLAS_TIPO_CLIENTE.items() if regla.id_cola == id_cola)


def construir_colas(especificaciones: Iterable[ColaEditable]) -> tuple[ConfiguracionCola, ...]:
    """Construye la configuración MLQ a partir de los valores de la interfaz.

    Exige un quantum entero positivo únicamente en las colas Round Robin y
    rechaza que un tipo de cliente quede asignado a dos colas, porque la cola de
    cada proceso se deriva de su tipo.
    """

    recibidas = tuple(especificaciones)
    if not recibidas:
        raise ErrorConfiguracion("la configuración de colas está vacía")
    if any(not isinstance(especificacion, ColaEditable) for especificacion in recibidas):
        raise ErrorConfiguracion("la configuración contiene una cola inválida")

    identificadores = [especificacion.id_cola for especificacion in recibidas]
    if len(set(identificadores)) != len(identificadores):
        raise ErrorConfiguracion("la configuración contiene colas duplicadas")

    colas: list[ConfiguracionCola] = []
    for especificacion in recibidas:
        nombre = NOMBRES_COLA.get(especificacion.id_cola)
        if nombre is None:
            raise ErrorConfiguracion(
                f"la cola {especificacion.id_cola} no está definida en el sistema"
            )
        if not isinstance(especificacion.algoritmo, Algoritmo):
            raise ErrorConfiguracion("cada cola debe tener un algoritmo válido")
        colas.append(
            ConfiguracionCola(
                id_cola=especificacion.id_cola,
                nombre=nombre,
                prioridad_cola=especificacion.prioridad_cola,
                algoritmo=especificacion.algoritmo,
                quantum=_validar_quantum(especificacion),
                tipos_cliente=tipos_cliente_de_cola(especificacion.id_cola),
            )
        )

    _validar_tipos_unicos(colas)
    return tuple(colas)


def configuracion_por_defecto() -> tuple[ConfiguracionCola, ...]:
    """Reproduce la configuración MLQ de demostración documentada."""

    return construir_colas(
        (
            ColaEditable("alta", 1, Algoritmo.ROUND_ROBIN, 2),
            ColaEditable("media", 2, Algoritmo.SJF),
            ColaEditable("normal", 3, Algoritmo.FIFO),
            ColaEditable("baja", 4, Algoritmo.FIFO),
        )
    )


def _validar_quantum(especificacion: ColaEditable) -> int | None:
    """Acepta quantum solo en Round Robin y exige un entero positivo."""

    nombre = NOMBRES_COLA[especificacion.id_cola]
    if especificacion.algoritmo is not Algoritmo.ROUND_ROBIN:
        if especificacion.quantum is not None:
            raise ErrorConfiguracion(f"la cola {nombre} no usa Round Robin y no admite quantum")
        return None

    quantum = especificacion.quantum
    if quantum is None:
        raise ErrorConfiguracion(f"la cola {nombre} usa Round Robin y requiere quantum")
    if isinstance(quantum, bool) or not isinstance(quantum, int) or quantum < 1:
        raise ErrorConfiguracion(
            f"el quantum de la cola {nombre} debe ser un número entero mayor o igual que 1"
        )
    return quantum


def _validar_tipos_unicos(colas: Iterable[ConfiguracionCola]) -> None:
    """Rechaza que un tipo de cliente aparezca en más de una cola."""

    asignaciones: dict[TipoCliente, str] = {}
    for cola in colas:
        for tipo in cola.tipos_cliente:
            anterior = asignaciones.get(tipo)
            if anterior is not None:
                raise ErrorConfiguracion(
                    f"el tipo de cliente {tipo.value} aparece en las colas "
                    f"{anterior} y {cola.id_cola}"
                )
            asignaciones[tipo] = cola.id_cola


@dataclass(slots=True)
class EstadoSesion:
    """Carga, configuración y resultados vigentes de la sesión.

    La clase no depende del navegador ni de un contexto de ejecución de
    Streamlit: la interfaz la obtiene de `st.session_state` mediante
    `obtener_estado` y las pruebas pueden instanciarla directamente.

    Cualquier cambio del catálogo, de la carga o de la configuración descarta los
    resultados anteriores. Cambiar `N` no los descarta porque no altera los
    procesos que se planifican.
    """

    clientes: tuple[Cliente, ...] = ()
    procesos: list[Proceso] = field(default_factory=list)
    cantidad_solicitada: int | None = None
    configuracion_colas: tuple[ConfiguracionCola, ...] = field(
        default_factory=configuracion_por_defecto
    )
    quantum_comparacion: int = QUANTUM_COMPARACION_POR_DEFECTO
    resultado_individual: ResultadoSimulacion | None = None
    resultado_mlq: ResultadoSimulacion | None = None
    comparacion: Comparacion | None = None

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
        self._invalidar_resultados()

    def importar_procesos(self, procesos: Iterable[Proceso]) -> None:
        """Reemplaza la carga con los procesos recibidos, ya validados."""

        cargados = list(procesos)
        _validar_lista_procesos(cargados)
        for proceso in cargados:
            self._validar_proceso(proceso)
        self.procesos = cargados
        self._invalidar_resultados()

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
        self._invalidar_resultados()
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
        self._invalidar_resultados()
        return actualizado

    def eliminar_proceso(self, id_proceso: str) -> None:
        """Quita un proceso de la carga."""

        del self.procesos[self._posicion(id_proceso)]
        self._invalidar_resultados()

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

    def establecer_configuracion(
        self, colas: Iterable[ConfiguracionCola]
    ) -> tuple[ConfiguracionCola, ...]:
        """Reemplaza la configuración MLQ e invalida los resultados vigentes.

        Exige colas conocidas, sin identificadores repetidos, sin tipos de cliente
        compartidos y con una cola para cada proceso de la carga.
        """

        configuracion = tuple(colas)
        if not configuracion:
            raise ErrorConfiguracion("la configuración de colas está vacía")
        if any(not isinstance(cola, ConfiguracionCola) for cola in configuracion):
            raise ErrorConfiguracion("la configuración contiene una cola inválida")

        identificadores = [cola.id_cola for cola in configuracion]
        if len(set(identificadores)) != len(identificadores):
            raise ErrorConfiguracion("la configuración contiene colas duplicadas")
        for cola in configuracion:
            if cola.id_cola not in NOMBRES_COLA:
                raise ErrorConfiguracion(f"la cola {cola.id_cola} no está definida en el sistema")

        _validar_tipos_unicos(configuracion)

        colas_configuradas = set(identificadores)
        faltantes = sorted({proceso.id_cola for proceso in self.procesos} - colas_configuradas)
        if faltantes:
            raise ErrorConfiguracion(
                "la configuración no incluye las colas de la carga: " + ", ".join(faltantes)
            )

        self.configuracion_colas = configuracion
        self._invalidar_resultados()
        return configuracion

    def establecer_quantum_comparacion(self, quantum: int) -> int:
        """Registra el quantum de la comparación y descarta la comparación previa."""

        if isinstance(quantum, bool) or not isinstance(quantum, int):
            raise ErrorValidacion("el quantum de la comparación debe ser un número entero")
        if quantum < 1:
            raise ErrorValidacion("el quantum de la comparación debe ser mayor o igual que 1")
        if quantum != self.quantum_comparacion:
            self.quantum_comparacion = quantum
            self.comparacion = None
        return quantum

    def registrar_resultado_individual(self, resultado: ResultadoSimulacion) -> None:
        """Conserva el último resultado de FIFO, SJF o Round Robin."""

        if not isinstance(resultado, ResultadoSimulacion):
            raise ErrorValidacion("el resultado individual debe ser una simulación válida")
        self.resultado_individual = resultado

    def registrar_resultado_mlq(self, resultado: ResultadoSimulacion) -> None:
        """Conserva el último resultado de la configuración MLQ."""

        if not isinstance(resultado, ResultadoSimulacion):
            raise ErrorValidacion("el resultado MLQ debe ser una simulación válida")
        self.resultado_mlq = resultado

    def registrar_comparacion(self, comparacion: Comparacion, *, quantum: int) -> None:
        """Conserva la comparación y el quantum con el que fue calculada."""

        if not isinstance(comparacion, Comparacion):
            raise ErrorValidacion("la comparación debe ser un resultado válido")
        self.establecer_quantum_comparacion(quantum)
        self.comparacion = comparacion

    def reiniciar(self) -> None:
        """Limpia procesos, N y resultados; catálogo y configuración se conservan."""

        self.procesos.clear()
        self.cantidad_solicitada = None
        self._invalidar_resultados()

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

    def _invalidar_resultados(self) -> None:
        """Descarta resultados que dejan de corresponder a la carga o configuración."""

        self.resultado_individual = None
        self.resultado_mlq = None
        self.comparacion = None

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
