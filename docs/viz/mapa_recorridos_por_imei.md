# Mapas interactivos por IMEI y operador

Esta guía describe la nueva vista que combina los reportes de ubicación (`GTERI`/`GTFRI`)
con los reportes informativos (`GTINF`) para enriquecer un mapa interactivo por IMEI.
El proceso trabaja **solo en memoria** a partir de las bases SQLite generadas por el
homologador; no modifica ninguna de las bases existentes.

## Requisitos previos

- Contar con los archivos SQLite generados por el parser para los reportes
  `gteri_<modelo>.db`, `gtfri_<modelo>.db` (opcional) y `gtinf_<modelo>.db`.
- Instalar `folium`, `pytz` y `python-dateutil`:

  ```bash
  pip install folium pytz python-dateutil
  ```

## Cómo se fusionan los datos

1. **Carga de recorridos**: se leen todas las posiciones del IMEI indicado desde las
   bases `GTERI` y/o `GTFRI` (puedes limitar las fuentes con `--report`).
2. **Carga de GTINF**: se obtienen todos los registros `GTINF` del mismo IMEI ordenados
   por `send_time`.
3. **Enriquecimiento**: cada punto de recorrido adopta la tecnología (`network_type`) y
   la intensidad de señal (`csq`, `ber`) del **último GTINF cuyo `send_time` sea menor o
   igual** al del punto. Si no existe un GTINF anterior, el punto se marca como
   "Desconocida".
4. **Clasificación**: la señal se traduce a dBm y se clasifica como Pésima/Regular/Buena/
   Excelente según los umbrales definidos para 2G/3G/4G.

El siguiente ejemplo ilustra la correspondencia de tiempos:

| `send_time` GTERI | `send_time` GTINF aplicado | Tecnología | Calidad |
|-------------------|----------------------------|------------|---------|
| 2025-10-10 00:00:00 | 2025-10-10 00:00:00 | 3G | Buena |
| 2025-10-10 00:00:20 | 2025-10-10 00:00:00 | 3G | Buena |
| 2025-10-10 00:02:20 | 2025-10-10 00:01:40 | 4G | Excelente |

> Los reportes GTINF suelen llegar cada minuto, mientras que GTERI/GTFRI se reciben cada
> 20 segundos. Por ello varios puntos de recorrido comparten la misma medición GTINF.

## Elementos del mapa

- **Capas por operador**: Entel, Claro, Movistar y WOM tienen colores fijos.
- **Capas por tecnología**: 2G/3G/4G permiten aislar el tipo de red activa.
- **Capas por día**: agrupan el recorrido por fecha de `send_time`.
- **Tooltips**: muestran IMEI, reporte origen (GTERI/GTFRI), coordenadas, operador,
  tecnología, clasificación de señal y valores en dBm/CSQ/BER cuando existan.

## Filtros disponibles

Todos los filtros aceptan la palabra clave `All` (sin distinguir mayúsculas) para mostrar
el conjunto completo de puntos.

- `--day YYYY-MM-DD`: restringe la visualización a una fecha específica.
- `--operator <nombre>`: se puede repetir el flag para listar varios operadores.
- `--network <2G|3G|4G>`: limita la tecnología celular mostrada.
- `--report gteri|gtfri`: controla qué fuentes de coordenadas utilizar.

## Ejecución

```bash
python generate_map.py \
  --model gv350ceu \
  --imei 862524060869597 \
  --db-dir bases_sqlite \
  --out-dir mapas
```

El HTML generado se almacena como `mapa_<modelo>_<imei>.html` en el directorio indicado.

## Consideraciones

- La fusión se realiza cada vez que se genera el mapa; no persiste ningún cambio en las
  bases SQLite.
- Si no se encuentra un GTINF anterior para un punto, este se conserva con tecnología y
  señal "Desconocida".
- Los umbrales de clasificación pueden ajustarse en `viz/mapa_recorridos.py` si fuese
  necesario.
