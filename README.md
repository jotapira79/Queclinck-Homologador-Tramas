# Queclinck-Homlogador-Tramas

Herramientas para homologar y analizar tramas Queclink (`GTINF, GTERI, GTFRI y GTJDS`) de los
modelos GV310LAU, GV58LAU, GV75LAU, GV350CEU y GV37CAU. Permite convertir archivos de
texto/CSV/XLSX a una base de datos SQLite y, a partir de ella, generar mapas diarios con los
recorridos diferenciando entre reportes buffer y no buffer.

## Requisitos

- Python 3.9 o superior.
- Dependencias opcionales del parser: `pandas` y `openpyxl` (para leer CSV/XLSX).
- Dependencias del módulo de visualización: `folium`, `pytz`, `python-dateutil`.

Instala los paquetes mínimos para los mapas con:

```bash
pip install folium pytz python-dateutil
```

## Homologación de tramas GTINF/GTERI/GTFRI/GTJDS

Ejemplo rápido para convertir un archivo de tramas a SQLite en PowerShell:

```bash
py queclink_tramas.py --in datos.txt --out <rep>_<modelo>.db
```
Ejemplo
```bash
py queclink_tramas.py --in gtfri_gv58lau.txt --out gtfri_gv58lau.db
```

### Detección automática de mensaje y modelo

El CLI identifica el tipo de mensaje leyendo el `Head` (`+RESP:GTINF`, `+BUFF:GTERI`, etc.) y
extrae el nombre corto (`INF`, `ERI`) para localizar automáticamente el archivo YAML adecuado
(`spec/<modelo>/<mensaje>.yml`).

El modelo se determina combinando los **primeros ocho dígitos del IMEI** y, cuando es necesario,
el nombre de equipo reportado en la trama:

- `86858906` → **GV310LAU**
- `86252406` → **GV350CEU**
- `86631406` → **GV58LAU** (si el cuarto campo no indica otro modelo)
- `86631406` + `device_name=GV75LAU` → **GV75LAU**
- `86848700` → **GV37CAU** (o `device_name=GV37CAU` cuando el IMEI no viene completo)

Si los identificadores no corresponden a un modelo soportado se omite la trama y se deja un log de
advertencia detallando el IMEI y el `device_name` recibido.

### Esquema estrictamente definido por YAML

Cada spec define los campos disponibles para un mensaje y modelo concretos. La base de datos
SQLite se crea (o amplía) únicamente con esas columnas. El proceso de ingestión nunca agrega
columnas auxiliares como `raw_line`, `is_buffer`, `send_time`, `count_number` o similares a menos
que estén declaradas explícitamente en el YAML.

La lógica del parser también respeta los campos opcionales controlados por máscaras (por ejemplo
`position_append_mask.bitX` o `eri_mask.bitY`), cargando solamente los datos habilitados en la
trama.


## Bases de Datos GTERI o GTFRI Enriquecidas con Datos GTINF

`viz/mapa_recorridos.py` ya no genera archivos HTML ni GeoJSON. Su responsabilidad es crear y
mantener las bases `gteri_<modelo>_map.db` y `gtfri_<modelo>_map.db`, cruzando automáticamente
las ubicaciones (`GTERI`/`GTFRI`) con la información de red proveniente de `GTINF`.

Las bases de datos GTERI / GTFRI y GTINF deben estar en la carpeta `bases_sqlite` las bases de datos
deberían estar con los siguientes nombres `gteri_<modelo>.db`, `gtfri_<modelo>.db` o `gtinf_<modelo>.db`
(ej: `gteri_gv310lau.db`). Para el equipo **GV75LAU** (que reporta recorridos vía `GTFRI`) asegúrate
de contar con `gtfri_gv75lau.db` y `gtinf_gv75lau.db` (o sus variantes `_map.db` si ya fueron
generadas). Actualmente se soportan los modelos GV310LAU, GV58LAU, GV75LAU, GV350CEU y GV37CAU.

El proceso agrega/actualiza las columnas `tecnologia_celular`, `calidad_senal`,
`nivel_senal_dbm` y `operador`, rellenándolas con la mejor medición `GTINF` disponible para cada
`send_time` del recorrido. También normaliza el operador a los nombres locales (Entel, Movistar,
Claro, WOM o Desconocido) cuando solo se dispone de MCC/MNC.

Ejemplo de ejecución:

```bash
py generate_map.py --model gv350ceu --db-dir bases_sqlite
```

```bash
py generate_map.py --model gv75lau --db-dir bases_sqlite --report gtfri
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
