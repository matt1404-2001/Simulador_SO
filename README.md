# Simulador de planificación de procesos

Aplicación académica para simular la atención de tiquetes de servicio con un único
CPU. Cada tiquete es un proceso que compite por el procesador y se planifica con
FIFO, SJF, Round Robin o una configuración multinivel por colas (MLQ).

El programa permite cargar clientes y procesos desde CSV, configurar las colas,
ejecutar los algoritmos, recorrer la traza paso a paso, consultar el Gantt y las
métricas, comparar FIFO, SJF y Round Robin sobre la misma carga y exportar los
resultados.

## Requisitos

- Python 3.12.
- [uv](https://docs.astral.sh/uv/) para instalar y ejecutar el proyecto.
- Un navegador web local.
- Plataforma de entrega: Linux. El proyecto también funciona en macOS y Windows.

Las dependencias de ejecución son `streamlit`, `plotly` y `pandas`. Las de
desarrollo son `pytest` y `ruff`.

## Instalación

Desde la carpeta `codigo/`, que es la raíz del repositorio:

```bash
uv python install 3.12
uv sync --extra desarrollo
```

`uv sync` crea el entorno virtual en `.venv/` e instala las dependencias fijadas
en `uv.lock`.

Instalación alternativa con `pip`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[desarrollo]"
```

## Ejecución de la aplicación web

```bash
uv run streamlit run app.py
```

Abra la dirección que muestra la consola, por defecto
`http://localhost:8501`.

Flujo recomendado:

1. Cargar el catálogo de ejemplo o importar un archivo de clientes.
2. Cargar los procesos de ejemplo o importarlos desde CSV.
3. Revisar `N`: si está vacío se completa con la cantidad de filas importadas; si
   ya tiene valor, la importación carga solo las primeras `N`.
4. Revisar la configuración de las cuatro colas MLQ.
5. Elegir FIFO, SJF, Round Robin, MLQ o Comparación y ejecutar.
6. Consultar el Gantt, el avance paso a paso, las métricas y las descargas CSV.

Si `N` está confirmada y el archivo trae más filas, la importación carga solo los
primeros `N` procesos, en el orden de las filas, y lo informa. Si la carga ya
quedó desalineada con `N` (por ejemplo, tras agregar procesos a mano), el botón
"Ajustar la carga a N" conserva los primeros `N` por orden de ingreso y quita el
resto de una sola vez, sin borrar proceso por proceso.

Para ejecutar en un servidor sin abrir el navegador automáticamente:

```bash
uv run streamlit run app.py --server.headless true --server.address 127.0.0.1
```

## Modo consola

Imprime la secuencia de ejecución y las métricas de la configuración MLQ de
demostración:

```bash
uv run python -m simulador.presentacion.consola --archivo data/procesos_ejemplo.csv
```

El archivo de procesos no contiene datos del cliente. La consola busca
`clientes.csv` junto al archivo indicado y, si no existe, usa `data/clientes.csv`.
También se puede indicar de forma explícita:

```bash
uv run python -m simulador.presentacion.consola \
  --archivo data/procesos_ejemplo.csv \
  --clientes data/clientes.csv
```

La salida incluye cada segmento de la traza, los resultados por proceso y los
promedios, el tiempo de CPU ocupado e inactivo y la utilización. Los tramos sin
trabajo se muestran como `IDLE`.

## Pruebas y calidad

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

La suite cubre modelos, métricas, los cuatro planificadores, importación y
exportación CSV, estado de sesión, Gantt, avance paso a paso y el flujo completo
con los archivos de ejemplo.

## Formatos CSV

Todos los archivos usan UTF-8, separador coma y encabezado obligatorio. El
encabezado debe contener exactamente las columnas documentadas, en cualquier
orden. Se rechazan columnas faltantes, sobrantes o repetidas. Los errores indican
el número de línea, el campo y la causa.

### Catálogo de clientes

```csv
id_cliente,nombre,tipo_cliente,prioridad,maximo_gestiones,activo
C001,Ana Rojas,VIP,1,3,true
C002,Luis Mora,Empresarial,2,4,true
```

Reglas:

- `id_cliente` es único y no puede estar vacío.
- `tipo_cliente` debe ser uno de los tipos documentados.
- `prioridad` y `maximo_gestiones` deben coincidir con la regla del tipo de
  cliente; el archivo no puede contradecir el dominio.
- `activo` solo admite `true` o `false`. Un cliente inactivo no puede generar
  procesos.

Tipos de cliente vigentes:

| Tipo de cliente | Prioridad | Máximo de gestiones | Cola |
|---|---:|---:|---|
| VIP | 1 | 3 | Alta |
| Embarazada | 1 | 2 | Alta |
| Adulto mayor | 1 | 2 | Alta |
| Empresarial | 2 | 4 | Media |
| Regular | 3 | 2 | Normal |
| Ocasional | 4 | 1 | Baja |

### Procesos

```csv
id_proceso,id_cliente,servicio,cantidad_gestiones,tiempo_llegada,rafaga
P001,C001,Internet,2,0,5
P002,C003,Cable,1,2,3
```

Reglas:

- `id_proceso` es único y no puede estar vacío.
- `id_cliente` debe existir en el catálogo y estar activo.
- `servicio` debe ser `Internet`, `Cable`, `Telefonía` u `Hosting`.
- `cantidad_gestiones` es un entero mayor o igual que 1 y no supera el máximo del
  cliente.
- `tiempo_llegada` es un entero mayor o igual que 0.
- `rafaga` es un entero mayor que 0.
- La prioridad, la cola y el orden de ingreso se derivan del cliente y del orden
  de las filas. El archivo no puede declarar esas columnas.
- Si `N` está confirmada, la importación lee solo las primeras `N` filas del
  archivo; las siguientes no se validan ni se cargan. El orden de las filas
  define cuáles entran.

### Datos de demostración

- `data/clientes.csv`: 6 clientes ficticios, sin datos personales reales.
- `data/procesos_ejemplo.csv`: 8 procesos con `N = 8`.
- `P008` llega en el tiempo 40, después de que el CPU quedó libre, por lo que la
  traza contiene un tramo `IDLE` obligatorio entre 30 y 40.

Configuración MLQ de la demostración:

| Cola | Prioridad | Algoritmo | Quantum |
|---|---:|---|---:|
| Alta | 1 | Round Robin | 2 |
| Media | 2 | SJF | no aplica |
| Normal | 3 | FIFO | no aplica |
| Baja | 4 | FIFO | no aplica |

## Reglas de planificación

- Un único CPU con tiempo discreto entero.
- El reloj comienza en cero y nunca retrocede.
- El costo de cambio de contexto es cero.
- No se simulan entrada/salida, bloqueos ni múltiples núcleos.
- Todo intervalo sin trabajo se representa con un segmento `IDLE`.
- FIFO elige la menor llegada y desempata por orden de ingreso e identificador.
- SJF no apropiativo elige la menor ráfaga entre los procesos ya llegados y
  desempata por llegada, orden de ingreso e identificador.
- Round Robin ejecuta `min(quantum, tiempo_restante)` y devuelve al final de la
  cola circular los procesos que no terminan.
- MLQ usa colas fijas sin retroalimentación. En cada punto de despacho elige la
  cola no vacía de menor `prioridad_cola`; si empatan, la de menor índice en la
  configuración. Una ejecución FIFO o SJF ya iniciada no se interrumpe por una
  llegada a una cola superior. Las colas se reevalúan al terminar un proceso o un
  quantum de Round Robin.

Fórmulas:

```text
tiempo_retorno = tiempo_finalizacion - tiempo_llegada
tiempo_espera = tiempo_retorno - rafaga
tiempo_cpu_ocupado = suma de las rafagas
tiempo_total = finalizacion del ultimo proceso
tiempo_cpu_inactivo = tiempo_total - tiempo_cpu_ocupado
utilizacion_cpu = tiempo_cpu_ocupado / tiempo_total * 100
```

Los promedios se calculan sobre todos los procesos terminados. La comparación
ejecuta FIFO, SJF y Round Robin sobre copias equivalentes de la misma carga, con
el quantum configurado para la comparación. MLQ se ejecuta por separado porque usa
el quantum de cada cola.

## Exportación

La interfaz ofrece tres descargas por ejecución:

- Traza: `algoritmo,inicio,fin,duracion,proceso,id_cola`.
- Resultados por proceso:
  `algoritmo,id_proceso,id_cola,tiempo_llegada,rafaga,tiempo_finalizacion,tiempo_espera,tiempo_retorno`.
- Métricas:
  `algoritmo,promedio_espera,promedio_retorno,tiempo_cpu_ocupado,tiempo_cpu_inactivo,tiempo_total,utilizacion_cpu`.

## Arquitectura

```text
app.py y simulador/presentacion/   Streamlit, Plotly, consola y estado de sesión
                 |
simulador/aplicacion/              casos de uso: preparar, ejecutar y comparar
                 |
simulador/dominio/                 modelos, reglas, planificadores y métricas
                 ^
simulador/infraestructura/         lectura y exportación de CSV
```

El dominio no importa Streamlit, Pandas ni Plotly. La interfaz no calcula
planificación ni métricas: consume los resultados del motor. Los planificadores
trabajan sobre copias y nunca modifican la carga original.

## Ejecución en Linux

Instalación desde cero en Debian, Ubuntu o WSL:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"

cd codigo
uv python install 3.12
uv sync --extra desarrollo

uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python -m simulador.presentacion.consola --archivo data/procesos_ejemplo.csv
uv run streamlit run app.py
```

Notas:

- Si la terminal no usa UTF-8, ejecute `export LANG=C.UTF-8` antes de iniciar la
  aplicación para que se lean correctamente los nombres con acentos.
- En WSL, abra `http://localhost:8501` desde el navegador de Windows.
- Para un servidor remoto, use `--server.address 0.0.0.0` y restrinja el acceso
  según la red donde se ejecute. La aplicación no incluye autenticación.

## Alcance

Fuera de alcance en esta versión: múltiples CPU, entrada/salida, bloqueos, SRTF o
SJF apropiativo, MLFQ con movimiento entre colas, base de datos, autenticación,
despliegue público y datos personales reales. La persistencia se limita a los CSV
de entrada, las descargas y el estado de la sesión de Streamlit.
