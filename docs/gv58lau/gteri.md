# GV58LAU — GTERI (Expand Fixed Report Information)

**Archivo:** `docs/gv58lau/gteri.md`  
**Spec asociado:** `specs/gv58lau/gteri.yml`  
**Mensajes soportados:** `+RESP:GTERI`, `+BUFF:GTERI`  
**Codificación:** ASCII, delimitador `,`, terminador `$`

---

## 1. Descripción general

El mensaje **GTERI** (Expand Fixed Report Information) es el informe de posición extendido del modelo **GV58LAU**.  
Incluye datos GNSS, red celular, estado del vehículo y, opcionalmente, información **CAN** y **BLE**.  
Puede recibirse como **+RESP** (en línea) o **+BUFF** (almacenado en buffer).

Este reporte amplía la información del `GTFRI`, añadiendo campos opcionales controlados por:

- **ERI Mask** → habilita bloques como CAN y accesorios BLE.  
- **Position Append Mask** → habilita datos GNSS adicionales (satélites, DOPs, etc.).

---

## 2. Estructura general

+RESP:GTERI,<version>,<imei>,<device>,<eri_mask>,<ext_power_mv>,<report_type>,<number>,
<gnss_acc>,<speed_kmh>,<azimuth_deg>,<altitude_m>,<lon>,<lat>,<gnss_utc>,
<mcc>,<mnc>,<lac>,<cell_id>,<pos_append_mask>,
[campos controlados por pos_append_mask...],
<mileage_km>,<hour_meter>,<reserved_1>,<reserved_2>,<reserved_3>,
<backup_batt_pct>,<device_status>,<reserved_after_status>,
[can_data si ERI lo habilita...],
[ble_count, bloque(s) BLE si ERI lo habilita...],
<send_time>,<count_hex>$


> Para `+BUFF:GTERI` la estructura es idéntica, solo cambia el encabezado.

---

## 3. Encabezado

| Campo | Tipo | Descripción |
|--------|------|-------------|
| `header` | string | Prefijo del mensaje (`+RESP:GTERI` o `+BUFF:GTERI`). |
| `full_protocol_version` | hex | Versión del protocolo (6 a 10 hex). |
| `imei` | string | IMEI de 15 dígitos. |
| `device_name` | string | Nombre del modelo (`GV58LAU`). |

---

## 4. Campos principales

| Campo | Tipo | Unidad | Descripción |
|--------|------|--------|-------------|
| `eri_mask` | hex | — | Máscara que activa bloques opcionales (ver §5). |
| `ext_power_mv` | int | mV | Voltaje externo (0–32000). |
| `report_type` | string | — | Tipo de reporte (2 caracteres). |
| `number` | int | — | Número de secuencia (0–15). |
| `gnss_acc` | float | — | Precisión GNSS general (HDOP). |
| `speed_kmh` | float | km/h | Velocidad. |
| `azimuth_deg` | int | ° | Rumbo (0–359). |
| `altitude_m` | float | m | Altitud. |
| `lon` | float | ° | Longitud (-180 a 180). |
| `lat` | float | ° | Latitud (-90 a 90). |
| `gnss_utc` | datetime | — | Hora UTC del fix GNSS (`YYYYMMDDHHMMSS`). |
| `mcc` | string | — | Código de país móvil. |
| `mnc` | string | — | Código de red móvil. |
| `lac` | hex | — | Local Area Code (4 hex). |
| `cell_id` | hex | — | Identificador de celda (4 u 8 hex). |

---

## 5. Position Append Mask

Controla la presencia de campos GNSS adicionales.  
El valor viene después de `cell_id`.

| Bit | Campo | Descripción |
|------|--------|-------------|
| 0 | `satellites` | Número de satélites. |
| 1 | `hdop` | Horizontal Dilution of Precision. |
| 2 | `vdop` | Vertical Dilution of Precision. |
| 3 | `pdop` | 3D Dilution of Precision. |

**Campos asociados:**

| Campo | Tipo | Rango / Descripción |
|--------|------|---------------------|
| `satellites` | int | 0–72 (opcional). |
| `hdop` | float | 0.00–99.99 (opcional). |
| `vdop` | float | 0.00–99.99 (opcional). |
| `pdop` | float | 0.00–99.99 (opcional). |
| `gnss_trigger_type` | int | Tipo de trigger GNSS (firmware dependiente, solo presente cuando se reportan valores DOP). |

---

## 6. Contadores y estado del dispositivo

| Campo | Tipo | Unidad | Descripción |
|--------|------|--------|-------------|
| `mileage_km` | float | km | Odómetro acumulado. |
| `hour_meter` | string | D:HH:MM | Horómetro (`0000000:00:00`). |
| `backup_batt_pct` | int | % | Porcentaje batería interna. |
| `device_status` | hex | — | Estado del dispositivo (bitfield). |
| `reserved_1..3` | string | — | Reservados. |
| `reserved_after_status` | string | — | Reservado posterior al status. |

---

## 7. Campos opcionales por ERI Mask

La **ERI Mask** activa bloques adicionales según bits configurados.

| Bit | Bloque habilitado |
|------|-------------------|
| 2 | `can_data` |
| 3 | Bloque de accesorios `ble_accessories` |

### 7.1 CAN data (bit 2)

| Campo | Tipo | Descripción |
|--------|------|-------------|
| `can_data` | string | Datos crudos CAN reportados (hasta ~1 KB). |

### 7.2 Accesorios BLE (bit 3)

| Campo | Tipo | Descripción |
|--------|------|-------------|
| `ble_count` | int | Cantidad de accesorios BLE reportados. |
| `ble_accessories` | grupo | Bloque repetido `ble_count` veces. |

**Estructura de cada accesorio BLE:**

| Campo | Tipo | Presencia (según `ble_append_mask`) |
|--------|------|-------------------------------------|
| `ble_index` | int | — |
| `ble_type` | int | — |
| `ble_model` | int | — |
| `ble_raw_data` | string | — |
| `ble_append_mask` | hex | Controla subcampos siguientes. |
| `ble_name` | string | bit0 |
| `ble_mac` | hex | bit1 |
| `ble_status` | int | bit2 |
| `ble_batt_mv` | int | bit3 |
| `ble_temp_c` | float | bit4 |
| `ble_humidity_rh` | float | bit5 |
| `ble_io_output_status` | int | bit7 |
| `ble_io_input_status` | int | bit7 |
| `ble_io_analog_mv` | int | bit7 |
| `ble_mode` | int | bit8 |
| `ble_event` | int | bit8 |
| `ble_tire_pressure_kpa` | int | bit9 |
| `ble_timestamp` | datetime | bit10 |
| `ble_temp_c_enhanced` | float | bit11 |
| `ble_magnet_id` | hex | bit12 |
| `ble_mag_event_counter` | int | bit12 |
| `ble_magnet_state` | int | bit12 |
| `ble_batt_pct` | int | bit13 |
| `ble_relay_state` | int | bit14 |

---

## 8. Cola (Tail)

| Campo | Tipo | Descripción |
|--------|------|-------------|
| `send_time` | datetime | Hora UTC de envío (`YYYYMMDDHHMMSS`). |
| `count_hex` | hex | Contador hexadecimal de 4 dígitos. |
| `$` | string | Terminador de línea. |

---

## 9. Ejemplos

### 9.1 Ejemplo con BLE y DOPs
+RESP:GTERI,8020040900,866314060268081,GV58LAU,00000100,,10,1,2,14.2,71,35.6,117.243103,31.854079,20250320015848,0460,0000,550B,0E9E30A5,0009,9,2.01,1.47,2.49,0.0,1234:56:07,,85,220100,,2,00,1,0,00000001,001F,TD_100109,FD6D3DE6D704,1,3600,18,01,1,3,0000006D,011F,DU_100361,F022A2143F36,1,3500,0,9,0,20250320015850,00D0$

- `eri_mask=00000100` → bloque BLE activo.  
- `pos_append_mask=0009` → satélites y PDOP activos.  
- `ble_count=2` → dos accesorios reportados.

---

### 9.2 Ejemplo en buffer sin BLE
+BUFF:GTERI,8020040305,866314060965330,GV58LAU,00000008,12000,21,3,1,0.0,0,0.0,0.000000,0.000000,20250930110413,0736,0001,1234,0000,0001,8,1.50,,,100,220100,,0,20250930110413,ED27$


- `eri_mask=00000008` → sin CAN/BLE.  
- `pos_append_mask=0001` → puede incluir satélites.  
- `is_buff=true` (por encabezado).  

---

## 10. Buenas prácticas

- Convertir `gnss_utc` y `send_time` a zona horaria **America/Santiago** para análisis local.  
- Usar `is_buff` (por encabezado) para diferenciar buffer vs online.  
- En mapas:  
  - Azul → `+RESP`  
  - Rojo → `+BUFF`
- Priorizar `hdop/vdop/pdop` sobre `gnss_acc` si están presentes.  
- Aceptar campos vacíos o reservados sin romper el parsing.  

---

## 11. Validaciones sugeridas

- Línea termina en `$`.  
- `header` ∈ `{+RESP:GTERI, +BUFF:GTERI}`.  
- `pos_append_mask` define presencia real de subcampos GNSS.  
- Tolerar longitudes variables (`cell_id`, `device_status`, `ble_append_mask`).  
- `count_dec = int(count_hex,16)` puede calcularse para debug o auditoría.  

---

## 12. Campos derivados recomendados (para SQLite)

| Campo derivado | Definición | Uso |
|----------------|-------------|-----|
| `is_buff` | `header.startswith('+BUFF')` | Identificar tramas en buffer. |
| `count_dec` | `int(count_hex, 16)` | Ordenar por secuencia. |
| `dt_gnss_cl` | `gnss_utc` → TZ Chile | Análisis por hora local. |
| `dt_send_cl` | `send_time` → TZ Chile | Latencia / auditoría. |

---

## 13. Errores comunes

- Exigir subcampos DOP sin que el bit correspondiente esté activo.  
- Tratar `report_type` como número y perder ceros.  
- Rechazar `cell_id` de 4 hex cuando la red usa 16 bits.  
- Fallar por reservados vacíos o campos adicionales.  

---

## 14. Referencias cruzadas

- `specs/gv58lau/gteri.yml` → definición técnica usada por el parser.  
- `specs/gv58lau/gtinf.yml` → estructura base del informe de información.  
- `parser/gteri.py` → implementación de parsing (si aplica).  

---

## 15. Historial del documento

| Versión | Fecha | Descripción |
|----------|--------|-------------|
| v1.0 | 2025-10-09 | Documento inicial completo para homologación GTERI en GV58LAU. |

---
