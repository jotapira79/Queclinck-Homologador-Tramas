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

## Homologación de tramas GTINF/GTERI/GTFRI

Ejemplo rápido para convertir un archivo de tramas a SQLite en PowerShell:

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

## Bases enriquecidas por IMEI y operador

`viz/mapa_recorridos.py` ya no genera archivos HTML ni GeoJSON. Su responsabilidad es crear y
mantener las bases `gteri_<modelo>_map.db` y `gtfri_<modelo>_map.db`, cruzando automáticamente
las ubicaciones (`GTERI`/`GTFRI`) con la información de red proveniente de `GTINF`.

Las bases de datos GTERI / GTFRI y GTINF deben estar en la carpeta bases_sqlite las bases de datos
deberían estar con los siguientes nombres gteri_<modelo>.db, gtfri_<modelo>.db o gtinf_<modelo>.db
(ej: gteri_gv310lau.db).

El proceso agrega/actualiza las columnas `tecnologia_celular`, `calidad_senal`,
`nivel_senal_dbm` y `operador`, rellenándolas con la mejor medición `GTINF` disponible para cada
`send_time` del recorrido. También normaliza el operador a los nombres locales (Entel, Movistar,
Claro, WOM o Desconocido) cuando solo se dispone de MCC/MNC.

Ejemplo de ejecución:

```bash
py generate_map.py --model gv350ceu --db-dir bases_sqlite
```

El comando anterior creará o actualizará las bases enriquecidas disponibles en `bases_sqlite`.
Si se solicita un reporte que no exista (por ejemplo `gtfri`), el script emitirá una advertencia
indicando el archivo faltante. Usa `--report` para acotar qué reportes procesar y `--strict`
cuando prefieras que la ejecución falle ante cualquier ausencia.

## Pruebas

Ejecuta los tests (incluye las validaciones del módulo de visualización):

```bash
pytest
```
