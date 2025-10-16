## GV350CEU — +RESP/+BUFF:GTFRI (Fixed Report Information)

Formato ASCII separado por comas y terminado con `$`. Se mantiene la segmentación **Head / Body / Tail** y el uso de **Position Append Mask** para campos condicionales.

### Propósito del mensaje

Reporte fijo periódico (FRI) con datos GNSS, red celular, odómetro y estados del equipo. Se utiliza en reportes por tiempo/distancia y para bufferización (`+BUFF`).

---

## 1) Estructura

### 1.1 Head

|  # | Campo                   | Long. | Rango/Formato                 | Ejemplo           |
| -: | ----------------------- | :---: | ----------------------------- | ----------------- |
|  1 | `header`                |   8   | `+RESP:GTFRI` | `+BUFF:GTFRI` | `+RESP:GTFRI`     |
|  2 | `full_protocol_version` |   6   | `000000`–`FFFFFF` (hex)       | `740904`          |
|  3 | `unique_id`             |   15  | IMEI                          | `862524060867948` |
|  4 | `device_name`           |  ≤ 20 | `0–9 a–z A–Z _ - '`           | `GV350CEU`        |

### 1.2 Body

|  # | Campo                               |  Long. | Rango/Formato                                   | Notas              |
| -: | ----------------------------------- | :----: | ----------------------------------------------- | ------------------ |
|  5 | `external_power_mv`                 |   ≤ 5  | `0–32000` (mV)                                  | Opcional           |
|  6 | `report_id_type`                    |    2   | `X(0–5)Y(0–6)`                                  | ID/Tipo de reporte |
|  7 | `number`                            |   ≤ 2  | `1–15`                                          | Opcional           |
|  8 | `gnss_accuracy_level`               |   ≤ 2  | `0–50`                                          | —                  |
|  9 | `speed_kmh`                         |   ≤ 5  | `0.0–999.9` (km/h)                              | —                  |
| 10 | `azimuth_deg`                       |   ≤ 3  | `0–359`                                         | —                  |
| 11 | `altitude_m`                        |   ≤ 8  | `(-)xxxxx.x` (m)                                | —                  |
| 12 | `longitude_deg`                     |  ≤ 11  | `(-)xxx.xxxxxx`                                 | —                  |
| 13 | `latitude_deg`                      |  ≤ 10  | `(-)xx.xxxxxx`                                  | —                  |
| 14 | `gnss_utc_time`                     |   14   | `YYYYMMDDHHMMSS` (UTC)                          | —                  |
| 15 | `mcc`                               |    4   | `0XXX`                                          | —                  |
| 16 | `mnc`                               |    4   | `0XXX`                                          | —                  |
| 17 | `lac_hex`                           |    4   | `XXXX` (hex)                                    | —                  |
| 18 | `cell_id_hex`                       |  4 | 8 | `XXXX` | `XXXXXXXX` (hex)                       | —                  |
| 19 | `position_append_mask`              |    2   | `00–FF` (hex)                                   | **Gobierna 20–23** |
| 20 | `satellites_in_use` *(opt.)*        |   ≤ 2  | `0–72`                                          | **Bit0=1**         |
| 21 | `horizontal_gnss_accuracy` *(opt.)* |   ≤ 5  | `0.00–99.99`                                    | **Bit1=1**         |
| 22 | `vertical_gnss_accuracy` *(opt.)*   |   ≤ 5  | `0.00–99.99`                                    | **Bit2=1**         |
| 23 | `gnss_3d_accuracy` *(opt.)*         |   ≤ 5  | `0.00–99.99`                                    | **Bit3=1**         |
| 24 | `mileage_km`                        |   ≤ 9  | `0.0–4294967.0` (km)                            | —                  |
| 25 | `hour_meter`                        |   13   | `0000000:00:00–1193000:00:00`                   | —                  |
| 26 | `analog_in_1`                       |   ≤ 5  | `0–16000(mV)` | `F(0–100)`                      | Opcional           |
| 27 | `analog_in_2`                       |   ≤ 5  | `0–16000(mV)` | `F(0–100)`                      | Opcional           |
| 28 | `analog_in_3`                       |   ≤ 5  | `0–16000(mV)` | `F(0–100)`                      | Opcional           |
| 29 | `backup_battery_percentage`         |   ≤ 3  | `0–100` (%)                                     | Opcional           |
| 30 | `device_status`                     | 6 | 10 | `000000–FFFFFF` | `0000000000–0FFFFFFFFF` (hex) | Máscara IO/estados |
| 31 | `reserved1`                         |    0   | —                                               | Puede faltar       |
| 32 | `reserved2`                         |    0   | —                                               | Puede faltar       |
| 33 | `reserved3`                         |    0   | —                                               | Puede faltar       |

### 1.3 Tail

|  # | Campo          | Long. | Rango/Formato          | Notas                |
| -: | -------------- | :---: | ---------------------- | -------------------- |
| 34 | `send_time`    |   14  | `YYYYMMDDHHMMSS` (UTC) | —                    |
| 35 | `count_number` |   4   | `0000–FFFF` (hex)      | **Contador, no CRC** |
| 36 | `tail`         |   1   | `$`                    | —                    |

---

## 2) Position Append Mask

*Campo:* `position_append_mask` (2 hex). Bits:

| Bit | Campo                      | Rango      |
| --: | -------------------------- | ---------- |
|   0 | `satellites_in_use`        | 0–72       |
|   1 | `horizontal_gnss_accuracy` | 0.00–99.99 |
|   2 | `vertical_gnss_accuracy`   | 0.00–99.99 |
|   3 | `gnss_3d_accuracy`         | 0.00–99.99 |

**Regla:** si el bit es **1**, el campo correspondiente **debe** estar presente (puede venir vacío por firmware). Si es **0**, el campo puede omitirse y el parser asigna `null`.

---

## 3) Reglas de parsing / validaciones

* Tokenizar por `,` y exigir `tail = '$'`.
* `device_name` **debe** ser `GV350CEU`.
* Rangos: `gnss_accuracy_level ∈ [0,50]`, `speed_kmh ∈ [0.0,999.9]`, `azimuth_deg ∈ [0,359]`, `backup_battery_percentage` (si presente) ∈ `[0,100]`.
* `count_number`: exactamente **4** hex (`0000–FFFF`), actúa como **contador** de reporte (no checksum).
* Campos 20–23 condicionados por `position_append_mask`.

---

## 4) Derivaciones recomendadas

* `lac` = `hex_to_uint(lac_hex)`
* `cell_id` = `hex_to_uint(cell_id_hex)`
* `gnss_chile_time` = `gnss_utc_time` en `America/Santiago` (considera DST/STD).
* `send_chile_time` = `send_time` en `America/Santiago`.

---

## 5) Ejemplos (muestras reales GV350CEU)

```
+BUFF:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.6,168,690.2,-70.291068,-23.958760,20251016184113,0730,0001,0836,002BEE06,01,12,775825.1,0000439:31:11,,,,100,221102,,,,20251016184115,AA41$
+BUFF:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.6,169,697.5,-70.290138,-23.963163,20251016184133,0730,0001,0836,002BEE06,01,12,775825.6,0000439:31:29,,,,100,221102,,,,20251016184135,AA42$
+BUFF:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.3,169,683.0,-70.291984,-23.954364,20251016184053,0730,0001,0836,002BEE06,01,10,775824.6,0000439:30:50,,,,100,221102,,,,20251016184055,AA3F$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.5,169,672.9,-70.292914,-23.949947,20251016184033,0730,0001,0836,002BEE06,01,12,775824.1,0000439:30:29,,,,100,221102,,,,20251016184035,AA3C$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.5,169,663.7,-70.293839,-23.945541,20251016184013,0730,0001,0836,002BEE06,01,12,775823.6,0000439:30:11,,,,100,221102,,,,20251016184015,AA3B$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.5,168,654.6,-70.294756,-23.941129,20251016183953,0730,0001,0836,002BEE06,01,12,775823.1,0000439:29:50,,,,100,221102,,,,20251016183955,AA3A$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.4,169,644.8,-70.295675,-23.936720,20251016183933,0730,0001,0836,002BEE06,01,12,775822.6,0000439:29:29,,,,100,221102,,,,20251016183935,AA37$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.5,168,635.3,-70.296601,-23.932315,20251016183913,0730,0001,0836,002BEE06,01,12,775822.1,0000439:29:11,,,,100,221102,,,,20251016183915,AA36$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.3,168,626.6,-70.297523,-23.927917,20251016183853,0730,0001,0836,002BEE06,01,12,775821.7,0000439:28:50,,,,100,221102,,,,20251016183855,AA35$
+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.6,169,618.0,-70.298450,-23.923512,20251016183833,0730,0001,0836,002BEE06,01,12,775821.2,0000439:28:29,,,,100,221102,,,,20251016183835,AA32$
```

**Notas de homologación rápidas**

* En todas las muestras `position_append_mask = 01` → solo se incluye `satellites_in_use` (12 o 10 según el caso).
* `backup_battery_percentage=100` y `device_status=221102` presentes; los 3 campos `analog_in_*` vienen vacíos.
* Conversión horaria: `send_time=20251016184115` (UTC) → `2025-10-16 15:41:15` en `America/Santiago` (UTC−3, horario de verano).
