"""Modelos inmutables compartidos por el motor de simulación."""

from dataclasses import dataclass
from math import isclose
from numbers import Real

from simulador.dominio.enumeraciones import Algoritmo, EstadoProceso, Servicio, TipoCliente
from simulador.dominio.excepciones import ErrorConfiguracion, ErrorValidacion


def _normalizar_texto(valor: object, campo: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ErrorValidacion(f"{campo} debe ser un texto no vacío")
    return valor.strip()


def _validar_entero(valor: object, campo: str, minimo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{campo} debe ser un número entero")
    if valor < minimo:
        raise ErrorValidacion(f"{campo} debe ser mayor o igual que {minimo}")
    return valor


def _validar_real_no_negativo(valor: object, campo: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, Real):
        raise ErrorValidacion(f"{campo} debe ser un número")
    if valor < 0:
        raise ErrorValidacion(f"{campo} no puede ser negativo")
    return float(valor)


@dataclass(frozen=True, slots=True)
class Cliente:
    """Cliente registrado que puede solicitar atención."""

    id_cliente: str
    nombre: str
    tipo_cliente: TipoCliente
    prioridad: int
    maximo_gestiones: int
    activo: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "id_cliente", _normalizar_texto(self.id_cliente, "id_cliente"))
        object.__setattr__(self, "nombre", _normalizar_texto(self.nombre, "nombre"))
        if not isinstance(self.tipo_cliente, TipoCliente):
            raise ErrorValidacion("tipo_cliente debe ser un TipoCliente válido")
        _validar_entero(self.prioridad, "prioridad", 1)
        _validar_entero(self.maximo_gestiones, "maximo_gestiones", 1)
        if not isinstance(self.activo, bool):
            raise ErrorValidacion("activo debe ser un valor booleano")


@dataclass(frozen=True, slots=True)
class Proceso:
    """Tiquete de servicio representado como proceso planificable."""

    id_proceso: str
    id_cliente: str
    servicio: Servicio
    cantidad_gestiones: int
    tiempo_llegada: int
    rafaga: int
    prioridad: int
    id_cola: str
    orden_ingreso: int
    tiempo_restante: int | None = None
    estado: EstadoProceso = EstadoProceso.NUEVO

    def __post_init__(self) -> None:
        object.__setattr__(self, "id_proceso", _normalizar_texto(self.id_proceso, "id_proceso"))
        object.__setattr__(self, "id_cliente", _normalizar_texto(self.id_cliente, "id_cliente"))
        object.__setattr__(self, "id_cola", _normalizar_texto(self.id_cola, "id_cola"))
        if not isinstance(self.servicio, Servicio):
            raise ErrorValidacion("servicio debe ser un Servicio válido")
        if not isinstance(self.estado, EstadoProceso):
            raise ErrorValidacion("estado debe ser un EstadoProceso válido")

        _validar_entero(self.cantidad_gestiones, "cantidad_gestiones", 1)
        _validar_entero(self.tiempo_llegada, "tiempo_llegada", 0)
        _validar_entero(self.rafaga, "rafaga", 1)
        _validar_entero(self.prioridad, "prioridad", 1)
        _validar_entero(self.orden_ingreso, "orden_ingreso", 0)

        tiempo_restante = self.rafaga if self.tiempo_restante is None else self.tiempo_restante
        _validar_entero(tiempo_restante, "tiempo_restante", 0)
        if tiempo_restante > self.rafaga:
            raise ErrorValidacion("tiempo_restante no puede superar la ráfaga")
        if tiempo_restante == 0 and self.estado is not EstadoProceso.TERMINADO:
            raise ErrorValidacion("un proceso sin tiempo restante debe estar terminado")
        if tiempo_restante > 0 and self.estado is EstadoProceso.TERMINADO:
            raise ErrorValidacion("un proceso terminado debe tener tiempo restante igual a cero")
        object.__setattr__(self, "tiempo_restante", tiempo_restante)


@dataclass(frozen=True, slots=True)
class ConfiguracionCola:
    """Algoritmo y prioridad asignados a una cola fija de MLQ."""

    id_cola: str
    nombre: str
    prioridad_cola: int
    algoritmo: Algoritmo
    quantum: int | None = None
    tipos_cliente: tuple[TipoCliente, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id_cola", _normalizar_texto(self.id_cola, "id_cola"))
        object.__setattr__(self, "nombre", _normalizar_texto(self.nombre, "nombre"))
        _validar_entero(self.prioridad_cola, "prioridad_cola", 1)
        if not isinstance(self.algoritmo, Algoritmo):
            raise ErrorConfiguracion("algoritmo debe ser un Algoritmo válido")
        if self.algoritmo is Algoritmo.MLQ:
            raise ErrorConfiguracion("una cola interna no puede utilizar MLQ")

        tipos_cliente = tuple(self.tipos_cliente)
        if any(not isinstance(tipo, TipoCliente) for tipo in tipos_cliente):
            raise ErrorConfiguracion("tipos_cliente contiene una categoría inválida")
        if len(set(tipos_cliente)) != len(tipos_cliente):
            raise ErrorConfiguracion("tipos_cliente no puede contener duplicados")
        object.__setattr__(self, "tipos_cliente", tipos_cliente)

        if self.algoritmo is Algoritmo.ROUND_ROBIN:
            if self.quantum is None:
                raise ErrorConfiguracion("una cola Round Robin requiere quantum")
            _validar_entero(self.quantum, "quantum", 1)
        elif self.quantum is not None:
            raise ErrorConfiguracion("quantum solo se configura para Round Robin")


@dataclass(frozen=True, slots=True)
class SegmentoEjecucion:
    """Intervalo continuo de CPU asignado a un proceso o marcado como inactivo."""

    id_proceso: str | None
    inicio: int
    fin: int
    id_cola: str | None = None

    def __post_init__(self) -> None:
        if self.id_proceso is not None:
            object.__setattr__(self, "id_proceso", _normalizar_texto(self.id_proceso, "id_proceso"))
        if self.id_cola is not None:
            object.__setattr__(self, "id_cola", _normalizar_texto(self.id_cola, "id_cola"))
        _validar_entero(self.inicio, "inicio", 0)
        _validar_entero(self.fin, "fin", 1)
        if self.fin <= self.inicio:
            raise ErrorValidacion("fin debe ser mayor que inicio")
        if self.id_proceso is None and self.id_cola is not None:
            raise ErrorValidacion("un segmento IDLE no puede pertenecer a una cola")

    @property
    def duracion(self) -> int:
        """Cantidad de unidades de tiempo ocupadas por el segmento."""

        return self.fin - self.inicio

    @property
    def es_inactivo(self) -> bool:
        """Indica si el segmento representa CPU sin trabajo."""

        return self.id_proceso is None

    @property
    def etiqueta(self) -> str:
        """Nombre legible del proceso o del periodo inactivo."""

        return "IDLE" if self.es_inactivo else self.id_proceso or "IDLE"


@dataclass(frozen=True, slots=True)
class ResultadoProceso:
    """Métricas finales de un proceso terminado."""

    id_proceso: str
    tiempo_llegada: int
    rafaga: int
    tiempo_finalizacion: int
    tiempo_espera: int
    tiempo_retorno: int
    id_cola: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id_proceso", _normalizar_texto(self.id_proceso, "id_proceso"))
        if self.id_cola is not None:
            object.__setattr__(self, "id_cola", _normalizar_texto(self.id_cola, "id_cola"))
        _validar_entero(self.tiempo_llegada, "tiempo_llegada", 0)
        _validar_entero(self.rafaga, "rafaga", 1)
        _validar_entero(self.tiempo_finalizacion, "tiempo_finalizacion", 1)
        _validar_entero(self.tiempo_espera, "tiempo_espera", 0)
        _validar_entero(self.tiempo_retorno, "tiempo_retorno", 1)

        retorno_esperado = self.tiempo_finalizacion - self.tiempo_llegada
        if self.tiempo_retorno != retorno_esperado:
            raise ErrorValidacion("tiempo_retorno no coincide con finalización menos llegada")
        if self.tiempo_espera != self.tiempo_retorno - self.rafaga:
            raise ErrorValidacion("tiempo_espera no coincide con retorno menos ráfaga")


@dataclass(frozen=True, slots=True)
class ResultadoSimulacion:
    """Traza y métricas consolidadas de una ejecución completa."""

    algoritmo: Algoritmo
    segmentos: tuple[SegmentoEjecucion, ...]
    resultados: tuple[ResultadoProceso, ...]
    promedio_espera: float
    promedio_retorno: float
    tiempo_cpu_ocupado: int
    tiempo_cpu_inactivo: int
    tiempo_total: int
    utilizacion_cpu: float
    configuraciones_colas: tuple[ConfiguracionCola, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.algoritmo, Algoritmo):
            raise ErrorValidacion("algoritmo debe ser un Algoritmo válido")

        segmentos = tuple(self.segmentos)
        resultados = tuple(self.resultados)
        configuraciones = tuple(self.configuraciones_colas)
        if not segmentos:
            raise ErrorValidacion("una simulación debe contener segmentos")
        if not resultados:
            raise ErrorValidacion("una simulación debe contener resultados")
        if any(not isinstance(segmento, SegmentoEjecucion) for segmento in segmentos):
            raise ErrorValidacion("segmentos contiene un elemento inválido")
        if any(not isinstance(resultado, ResultadoProceso) for resultado in resultados):
            raise ErrorValidacion("resultados contiene un elemento inválido")
        if any(
            not isinstance(configuracion, ConfiguracionCola) for configuracion in configuraciones
        ):
            raise ErrorValidacion("configuraciones_colas contiene un elemento inválido")

        identificadores = [resultado.id_proceso for resultado in resultados]
        if len(set(identificadores)) != len(identificadores):
            raise ErrorValidacion("resultados contiene procesos duplicados")

        promedio_espera = _validar_real_no_negativo(self.promedio_espera, "promedio_espera")
        promedio_retorno = _validar_real_no_negativo(self.promedio_retorno, "promedio_retorno")
        utilizacion_cpu = _validar_real_no_negativo(self.utilizacion_cpu, "utilizacion_cpu")
        _validar_entero(self.tiempo_cpu_ocupado, "tiempo_cpu_ocupado", 1)
        _validar_entero(self.tiempo_cpu_inactivo, "tiempo_cpu_inactivo", 0)
        _validar_entero(self.tiempo_total, "tiempo_total", 1)

        if self.tiempo_total != self.tiempo_cpu_ocupado + self.tiempo_cpu_inactivo:
            raise ErrorValidacion("tiempo_total debe ser la suma del tiempo ocupado e inactivo")
        if utilizacion_cpu > 100:
            raise ErrorValidacion("utilizacion_cpu no puede superar 100")

        ocupado_esperado = sum(resultado.rafaga for resultado in resultados)
        if self.tiempo_cpu_ocupado != ocupado_esperado:
            raise ErrorValidacion("tiempo_cpu_ocupado no coincide con la suma de ráfagas")
        if self.tiempo_total != max(resultado.tiempo_finalizacion for resultado in resultados):
            raise ErrorValidacion("tiempo_total no coincide con la última finalización")

        cantidad_resultados = len(resultados)
        espera_esperada = (
            sum(resultado.tiempo_espera for resultado in resultados) / cantidad_resultados
        )
        retorno_esperado = (
            sum(resultado.tiempo_retorno for resultado in resultados) / cantidad_resultados
        )
        utilizacion_esperada = self.tiempo_cpu_ocupado / self.tiempo_total * 100
        if not isclose(promedio_espera, espera_esperada, rel_tol=1e-9):
            raise ErrorValidacion("promedio_espera no coincide con los resultados")
        if not isclose(promedio_retorno, retorno_esperado, rel_tol=1e-9):
            raise ErrorValidacion("promedio_retorno no coincide con los resultados")
        if not isclose(utilizacion_cpu, utilizacion_esperada, rel_tol=1e-9):
            raise ErrorValidacion("utilizacion_cpu no coincide con los tiempos de CPU")

        object.__setattr__(self, "segmentos", segmentos)
        object.__setattr__(self, "resultados", resultados)
        object.__setattr__(self, "configuraciones_colas", configuraciones)
        object.__setattr__(self, "promedio_espera", promedio_espera)
        object.__setattr__(self, "promedio_retorno", promedio_retorno)
        object.__setattr__(self, "utilizacion_cpu", utilizacion_cpu)
