# GTERI (Expand Fixed Report Information) — GV350CEU

**Mensajes soportados:** `+RESP:GTERI` y `+BUFF:GTERI`

- **Formato:** ASCII, campos separados por `,`, terminador `$`.
- **Estructura general:** `Head → Body → Tail`.
- **Compatibilidad:** Alineado con `spec/gv350ceu/gteri.yml`.

---

## 1. Orden y campos principales

```
+RESP/+BUFF:GTERI,
<full_protocol_version>,
<imei>,
<device_name>,
<eri_mask>,
<external_power_mv?>,
<report_type>,
<number?>,
<gnss_accuracy?>,
<speed_kmh>,
<azimuth_deg>,
<altitude_m?>,
<lon>,
<lat>,
<gnss_utc_time>,
<mcc>,
<mnc>,
<lac_hex>,
<cell_id_hex>,
<position_append_mask?>,
[anexos controlados por position_append_mask],
<mileage_km?>,
<hour_meter?>,
<analog_in_1?>,
<analog_in_2?>,
<analog_in_3?>,
<backup_batt_percent?>,
<device_status?>,
<uart_device_type?>,
[accesorios BLE (bit 8 de eri_mask)],
[rat/band (bit 13 de eri_mask)],
<send_time>,
<count_hex>$
```

Los campos marcados con `?` pueden venir vacíos. Las máscaras **Position Append Mask** y **ERI Mask** habilitan anexos opcionales en el mismo orden mostrado.

---

## 2. Head

| Campo | Tipo | Descripción |
|---|---|---|
| `header` | string | `+RESP:GT` o `+BUFF:GT`. |
| `message` | string | Siempre `ERI`. |
| `full_protocol_version` | hex | Versión de protocolo (`6` o `7` caracteres). |
| `imei` | string | 15 dígitos. |
| `device_name` | string | Nombre del equipo (p. ej. `GV350CEU`). |

---

## 3. Body

### 3.1 Núcleo ERI

| Campo | Tipo | Notas |
|---|---|---|
| `eri_mask` | hex(8) | Bitmask que habilita bloques opcionales. |
| `external_power_mv` | int | Voltaje externo (puede venir vacío). |
| `report_type` | hex(2) | Tipo/subtipo de evento. |
| `number` | int | Contador interno (0–15). |
| `gnss_accuracy` | int | Precisión GNSS (m). |
| `speed_kmh` | float | Velocidad en km/h. |
| `azimuth_deg` | int | Rumbo. |
| `altitude_m` | float | Altitud (puede faltar). |
| `lon`, `lat` | float | Coordenadas (-180/+180, -90/+90). |
| `gnss_utc_time` | datetime | `YYYYMMDDHHMMSS`. |
| `mcc`, `mnc` | string | Prefijos celulares `0xxx`. |
| `lac_hex`, `cell_id_hex` | hex | Datos de celda. |
| `position_append_mask` | hex | Máscara de anexos GNSS. |

### 3.2 Position Append Mask

| Bit | Campo | Descripción |
|---|---|---|
| 0 | `satellites_in_use` | Satélites utilizados. |
| 1 | `hdop` + `gnss_trigger_type` | HDOP y tipo de trigger (opcional). |
| 2 | `vdop` | VDOP. |
| 3 | `pdop` | PDOP. |
| 4 | `gnss_jamming_state` | Estado de interferencia (0–3). |

Los campos solo aparecen si el bit correspondiente está activo. El orden siempre sigue el listado anterior.

### 3.3 Contadores, entradas y estado

| Campo | Tipo | Notas |
|---|---|---|
| `mileage_km` | float | Odómetro en km. |
| `hour_meter` | string | Horas de motor `ddddddd:hh:mm`. |
| `analog_in_1`..`analog_in_3` | string | Lecturas analógicas (mV o `Fxx`). |
| `backup_batt_percent` | int | % batería interna. |
| `device_status` | hex | 3 bytes (24 bits) o extendido (40 bits). |
| `uart_device_type` | int | Tipo de periférico por UART (0,1,7...). |

### 3.4 1-Wire (bit 1 de `eri_mask`)

Cuando el bit 1 de `eri_mask` está habilitado, el equipo reporta la cantidad de dispositivos 1-Wire conectados y, para cada uno, la información disponible. Si el bit está en `0`, el bloque completo no aparece en la trama.

1. `one_wire_device_number` indica cuántos dispositivos se describen. Si es `0`, no se listan campos adicionales.
2. Cada elemento de `one_wire_devices` incluye los siguientes campos en el orden indicado:

   | Campo | Tipo | Notas |
   |---|---|---|
   | `one_wire_device_id` | hex | ID del dispositivo (8 bytes en ASCII HEX). |
   | `one_wire_device_type?` | int | Tipo de accesorio (1 = sensor de temperatura). Puede omitirse si el firmware no lo provee. |
   | `one_wire_device_data?` | hex | Datos crudos asociados. Solo se publica cuando el bit 1 está activo en el *mask* y el equipo tiene información adicional. |

Los campos marcados con `?` son opcionales en la trama y el parser los tolera tanto vacíos como ausentes.

### 3.5 Accesorios BLE (bit 8 de `eri_mask`)

Cuando el bit 8 está activo:

1. `ble_count` indica cuántos accesorios se describen.
2. Cada accesorio aporta:
   - `ble_index`, `ble_type`, `ble_model`, `ble_raw`, `ble_append_mask`.
   - Campos adicionales controlados por `ble_append_mask`:
     | Bit | Campo | Descripción |
     |---|---|---|
     | 0 | `ble_name` | Nombre del accesorio. |
     | 1 | `ble_mac` | MAC (12 hex). |
     | 2 | `ble_status` | 0=OFF, 1=ON. |
     | 3 | `ble_batt_mv` | Batería en mV. |
     | 4 | `ble_temp_c` | Temperatura °C. |
     | 5 | `ble_humidity_pct` | Humedad %. |
     | 12 | `ble_magnet_id`, `ble_mag_event_counter`, `ble_magnet_state` | Datos de sensor magnético. |

Todos los valores se procesan en el orden descrito; los no presentes se omiten.

### 3.6 RAT / Band (bit 13 de `eri_mask`)

Si el bit 13 está activo se agregan dos campos al final del cuerpo:

| Campo | Tipo | Descripción |
|---|---|---|
| `rat` | int | Tecnología de acceso radio (0=No Service, 1=EGPRS, 4=LTE Cat1, etc.). |
| `band` | string | Banda o canal reportado por el módem. |

---

## 4. Tail

| Campo | Tipo | Descripción |
|---|---|---|
| `send_time` | datetime | Hora de envío (`YYYYMMDDHHMMSS`). |
| `count_hex` | hex | Contador incremental del mensaje. |

---

## 5. Ejemplo

```
+RESP:GTERI,740904,862524060204589,GV350CEU,00000100,,10,1,1,0.0,355,97.7,117.129252,31.839388,20240415054037,0460,0000,550B,085BE2AA,01,11,3.6,,,,,0,210100,0,1,00,11,0,0000001E,100F,,D325C2B2A2F8,1,2967,0,15,0,20240415154438,405C$
```

- `satellites_in_use = 11` (Position Append Mask = `01`).
- `ble_count = 1` con `ble_mac = D325C2B2A2F8` y `ble_batt_mv = 2967`.
- `send_time = 20240415154438`, `count_hex = 405C`.

Este ejemplo produce una fila válida en `gteri_gv350ceu` con todos los campos clave (`imei`, `lon`, `lat`, `gnss_utc_time`, `send_time`, `eri_mask`, `position_append_mask`).
