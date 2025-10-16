# GV310LAU — +RESP/+BUFF:GTFRI (Fixed Report Information)

Formato ASCII separado por comas y terminado con `$`. Este documento sigue la **misma estructura** usada para GV58LAU: segmentación en **Head / Body / Tail**, con manejo explícito de **Append Mask** (`position_append_mask`) y campos condicionales por bits.

---

## 1) Estructura

### 1.1 Head
| # | Campo                 | Long. | Rango/Formato                               | Ejemplo                 |
|--:|-----------------------|:-----:|---------------------------------------------|-------------------------|
| 1 | `header`              |   8   | `+RESP:GTFRI` \| `+BUFF:GTFRI`              | `+RESP:GTFRI`           |
| 2 | `full_protocol_version` | 6   | `000000`–`FFFFFF` (hex)                     | `6E0C03`                |
| 3 | `unique_id`           |  15   | IMEI                                         | `868589060693259`       |
| 4 | `device_name`         | ≤ 20  | `0–9 a–z A–Z _ - '`                          | `GV310LAU`              |

### 1.2 Body
| # | Campo                         | Long. | Rango/Formato                                  | Notas |
|--:|-------------------------------|:-----:|------------------------------------------------|-------|
| 5 | `external_power_mv`           | ≤ 5   | `0–32000` (mV)                                 | Opcional |
| 6 | `report_id_type`              |  2    | `X(0–5)Y(0–6)`                                 | ID/Tipo de reporte |
| 7 | `number`                      | ≤ 2   | `1–15`                                         | Opcional |
| 8 | `gnss_accuracy_level`         | ≤ 2   | `0–50`                                         | — |
| 9 | `speed_kmh`                   | ≤ 5   | `0.0–999.9` (km/h)                             | — |
|10 | `azimuth_deg`                 | ≤ 3   | `0–359`                                        | — |
|11 | `altitude_m`                  | ≤ 8   | `(-)xxxxx.x` (m)                               | — |
|12 | `longitude_deg`               | ≤ 11  | `(-)xxx.xxxxxx`                                | — |
|13 | `latitude_deg`                | ≤ 10  | `(-)xx.xxxxxx`                                 | — |
|14 | `gnss_utc_time`               |  14   | `YYYYMMDDHHMMSS` (UTC)                         | — |
|15 | `mcc`                         |  4    | `0XXX`                                         | — |
|16 | `mnc`                         |  4    | `0XXX`                                         | — |
|17 | `lac_hex`                     |  4    | `XXXX` (hex)                                   | — |
|18 | `cell_id_hex`                 | 4 \| 8| `XXXX` \| `XXXXXXXX` (hex)                     | — |
|19 | `position_append_mask`        |  2    | `00–FF` (hex)                                  | **Gobierna campos 20–23** |
|20 | `satellites_in_use` *(opt.)*  | ≤ 2   | `0–72`                                         | **Bit0=1** |
|21 | `horizontal_gnss_accuracy` *(opt.)* | ≤ 5 | `0.00–99.99`                                  | **Bit1=1** |
|22 | `vertical_gnss_accuracy` *(opt.)*   | ≤ 5 | `0.00–99.99`                                  | **Bit2=1** |
|23 | `gnss_3d_accuracy` *(opt.)*         | ≤ 5 | `0.00–99.99`                                  | **Bit3=1** |
|24 | `mileage_km`                  | ≤ 9   | `0.0–4294967.0` (km)                           | — |
|25 | `hour_meter`                  |  13   | `0000000:00:00–1193000:00:00`                  | — |
|26 | `analog_in_1`                 | ≤ 5   | `0–16000(mV)` \| `F(0–100)`                    | Opcional |
|27 | `analog_in_2`                 | ≤ 5   | `0–16000(mV)` \| `F(0–100)`                    | Opcional |
|28 | `analog_in_3`                 | ≤ 5   | `0–16000(mV)` \| `F(0–100)`                    | Opcional |
|29 | `backup_battery_percentage`   | ≤ 3   | `0–100` (%)                                    | Opcional |
|30 | `device_status`               | 6 \| 10 | `000000–FFFFFF` \| `0000000000–0FFFFFFFFF` (hex)| Máscara IO/estados |
|31 | `reserved1`                   |  0    | —                                              | Puede faltar |
|32 | `reserved2`                   |  0    | —                                              | Puede faltar |
|33 | `reserved3`                   |  0    | —                                              | Puede faltar |

### 1.3 Tail
| # | Campo         | Long. | Rango/Formato           | Notas                   |
|--:|---------------|:-----:|-------------------------|-------------------------|
|34 | `send_time`   |  14   | `YYYYMMDDHHMMSS` (UTC)  | —                       |
|35 | `count_number`|   4   | `0000–FFFF` (hex)       | **Contador, no CRC**    |
|36 | `tail`        |   1   | `$`                     | —                       |

---

## 2) Append Mask (Position Append Mask)

**Campo:** `position_append_mask` (2 hex). Se interpreta bit a bit al estilo GV58LAU:

| Bit | Campo                         | Rango       |
|----:|-------------------------------|-------------|
|  0  | `satellites_in_use`          | 0–72        |
|  1  | `horizontal_gnss_accuracy`   | 0.00–99.99  |
|  2  | `vertical_gnss_accuracy`     | 0.00–99.99  |
|  3  | `gnss_3d_accuracy`           | 0.00–99.99  |

**Regla:** si un bit = **1**, el campo correspondiente **debe** estar presente (puede venir vacío si el firmware así lo envía).  
Si bit = **0**, el campo puede omitirse o venir vacío y el parser debe asignar `null`/vacío.

---

## 3) Reglas de parsing / validaciones

- Tokenizar por `,` y exigir `tail = '$'`.
- `device_name` **debe** ser `GV310LAU`.
- Rangos:  
  - `gnss_accuracy_level ∈ [0,50]`  
  - `speed_kmh ∈ [0.0, 999.9]`  
  - `azimuth_deg ∈ [0,359]`  
  - `backup_battery_percentage` (si presente) ∈ `[0,100]`
- `count_number`: exactamente **4** hex (`0000–FFFF`), actúa como **contador** de reporte (no checksum).
- Campos gobernados por **Append Mask** usan la condición por bit (Bit0..Bit3) y son opcionales si la máscara lo permite.

---

## 4) Derivaciones recomendadas

- `lac` = `hex_to_uint(lac_hex)`  
- `cell_id` = `hex_to_uint(cell_id_hex)`  
- `gnss_chile_time` = `gnss_utc_time` en `America/Santiago` (respeta horario de verano/invierno).  
- `send_chile_time` = `send_time` en `America/Santiago`.

---
+RESP:GTFRI,6E0C03,868589060693259,GV310LAU,25194,10,1,1,0.0,16,440.5,-70.309823,-23.760673,20251016180342,0730,0002,00CE,0985D171,00,183603.6,0000748:27:41,,,,100,210100,,,,20251016180343,28C2$


Notas:
- En este sample los campos gobernados por **Append Mask** aparecen vacíos; el parser debe aceptarlos como opcionales.
- `count_number = 28C2` (hex) → es el **contador**, no un CRC.

---

## 6) Casos de prueba sugeridos

1. **Básico sin máscara**: `position_append_mask = 00` y campos 20–23 ausentes/vacíos.  
2. **Máscara completa**: `position_append_mask = 0F` con `satellites_in_use`, `horizontal_gnss_accuracy`, `vertical_gnss_accuracy`, `gnss_3d_accuracy`.  
3. **Velocidad y acimut en extremos**: `speed_kmh=0.0` y `azimuth_deg=359`.  
4. **Rangos de batería**: `backup_battery_percentage=0`, `100`.  
5. **Versión +BUFF**: mismo contenido con encabezado `+BUFF:GTFRI`.
