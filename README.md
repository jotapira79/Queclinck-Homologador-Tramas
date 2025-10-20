# Queclinck-Homlogador-Tramas

Herramientas para homologar y analizar tramas Queclink (`+RESP:GTERI` y `+RESP:GTINF`) de los
modelos GV310LAU, GV58LAU y GV350CEU. Permite convertir archivos de texto/CSV/XLSX a una base de
datos SQLite y, a partir de ella, generar mapas diarios con los recorridos diferenciando entre
reportes buffer y no buffer.

## Requisitos

- Python 3.9 o superior.
- Dependencias opcionales del parser: `pandas` y `openpyxl` (para leer CSV/XLSX).
- Dependencias del módulo de visualización: `folium`, `pytz`, `python-dateutil`.

Instala los paquetes mínimos para los mapas con:

```bash
pip install folium pytz python-dateutil
```

## Homologación de tramas GTINF/GTERI

Ejemplo rápido para convertir un archivo de tramas a SQLite:

```bash
python queclink_tramas.py --in datos.txt --out salida.db
```

### Detección automática de mensaje y modelo

El CLI identifica el tipo de mensaje leyendo el `Head` (`+RESP:GTINF`, `+BUFF:GTERI`, etc.) y
extrae el nombre corto (`INF`, `ERI`) para localizar automáticamente el archivo YAML adecuado
(`spec/<modelo>/<mensaje>.yml`).

El modelo se determina exclusivamente por los **primeros ocho dígitos del IMEI**:

- `86631406` → **GV58LAU**
- `86858906` → **GV310LAU**
- `86252406` → **GV350CEU**

Si el prefijo no está homologado se omite la trama y se deja un log de advertencia.

### Esquema estrictamente definido por YAML

Cada spec define los campos disponibles para un mensaje y modelo concretos. La base de datos
SQLite se crea (o amplía) únicamente con esas columnas. El proceso de ingestión nunca agrega
columnas auxiliares como `raw_line`, `is_buffer`, `send_time`, `count_number` o similares a menos
que estén declaradas explícitamente en el YAML.

La lógica del parser también respeta los campos opcionales controlados por máscaras (por ejemplo
`position_append_mask.bitX` o `eri_mask.bitY`), cargando solamente los datos habilitados en la
trama.

## Visualización de recorridos diarios

El módulo `viz` entrega un CLI que genera un mapa HTML (Folium) y un GeoJSON agrupando los
recorridos por día local (`America/Santiago`). Los puntos buffer se dibujan en rojo y los
reportes directos en azul, incluyendo tooltips con hora local y coordenadas.


### Ejemplos de uso

**Linux/macOS**

```bash
python -m viz.cli \
  --db salida.db \
  --imei 8646960600004173 \
  --date 2023-08-01 \
  --provider "CartoDB Positron" \
  --out mapas/gv310lau_2023-08-01


```bash
python -m viz.cli \
  --db salida.db \
  --imei 864696060004173 \
  --date 2023-08-01 \
  --provider "CartoDB Positron" \
  --out mapas/gv310lau_2023-08-01
```


**Windows (PowerShell)** – usa el acento grave `` ` `` como continuador y el lanzador `py`:

```powershell
py -m viz.cli `
  --db salida.db `
  --imei 8646960600004173 `
  --date 2023-08-01 `
  --provider "CartoDB Positron" `
  --out mapas/gv310lau_2023-08-01
```

**Windows (CMD)** – usa `^` como continuador:

```cmd
py -m viz.cli ^
  --db salida.db ^
  --imei 8646960600004173 ^
  --date 2023-08-01 ^
  --provider "CartoDB Positron" ^
  --out mapas/gv310lau_2023-08-01
```

Consulta `docs/viz/windows.md` para más consejos y una captura de pantalla del resultado.

El comando anterior creará los archivos:

- `mapas/gv310lau_2023-08-01.html`: mapa interactivo listo para compartir.
- `mapas/gv310lau_2023-08-01.geojson`: puntos del recorrido con hora local y tipo de reporte.

Para más ejemplos y capturas de pantalla revisa `docs/viz/mapas.md`.

## Mapas interactivos por IMEI y operador

La funcionalidad descrita en `docs/viz/mapa_recorridos_por_imei.md` genera un mapa HTML
que combina los reportes de posición (`GTERI`/`GTFRI`) con la información de red (`GTINF`).
Cada punto adopta la última medición `GTINF` cuyo `send_time` sea menor o igual, por lo que
los tramos del recorrido heredan la tecnología (2G/3G/4G) y la calidad de señal asociadas a
la red disponible en ese instante.

Características destacadas:

- Capas independientes por operador, tecnología y día.
- Tooltips con IMEI, coordenadas, reporte origen, tecnología, clasificación de señal y valores
  de CSQ/BER cuando estén presentes.
- Corrección automática de coordenadas cuando los reportes invierten latitud/longitud, incluso
  si la trama no incluye códigos MCC.
- Los recorridos y filtros se construyen exclusivamente a partir de las bases enriquecidas
  `<reporte>_<modelo>_map.db`, que ahora incluyen una columna `operador` con el nombre del
  carrier normalizado (Entel, Movistar, Claro, WOM o Desconocido).
- Filtros `--day`, `--operator`, `--network` y `--report`, todos compatibles con la palabra
  clave `All` para desactivar la restricción.

Ejecución básica:

```bash
python generate_map.py \
  --model gv350ceu \
  --imei 862524060869597 \
  --db-dir bases_sqlite \
  --out-dir mapas
```

Consulta la guía completa para más ejemplos, la explicación del algoritmo de fusión y las
consideraciones de uso.

## Pruebas

Ejecuta los tests (incluye las validaciones del módulo de visualización):

```bash
pytest
```
