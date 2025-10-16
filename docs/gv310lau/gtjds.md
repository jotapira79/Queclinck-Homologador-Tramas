# GV310LAU — +RESP/+BUFF:GTJDS (Network Jamming Indication Notification)

Formato ASCII separado por comas y terminado con `$`. Sigue el **estilo** usado en GTFRI: segmentación en **Head / Body / Tail**, más **Append Mask** (`position_append_mask`) para campos GNSS opcionales.

---

## 1) Estructura

### 1.1 Head
| # | Campo | Long. | Rango/Formato | Ejemplo |
|--:|-------|:-----:|---------------|---------|
| 1 | `header` | 8 | `+RESP:GTJDS` \| `+BUFF:GTJDS` | `+RESP:GTJDS` |
| 2 | `full_protocol_version` | 6 | `000000–FFFFFF` (hex) | `6E0C03` |
| 3 | `unique_id` | 15 | IMEI | `868589060379784` |
| 4 | `device_name` | ≤ 20 | `0–9 a–z A–Z _ - '` | `GV310LAU` |

### 1.2 Body
| # | Campo | Long. | Rango/Formato | Notas |
|--:|-------|:-----:|---------------|-------|
| 5 | `jamming_net` | 1 | `1–5` | 1=EGPRS/GSM, 2=LTE-Cat4, 3=WCDMA+EGPRS/GSM+LTE, 4=WCDMA, 5=WCDMA+EGPRS |
| 6 | `gnss_accuracy_level` | ≤ 2 | `0–50` | — |
| 7 | `jamming_state` | 1 | `0`/`1` | 0=No jamming / Cleared, 1=Jamming detectado |
| 8 | `speed_kmh` | ≤ 5 | `0.0–999.9` (km/h) | — |
| 9 | `azimuth_deg` | ≤ 3 | `0–359` | — |
|10 | `altitude_m` | ≤ 8 | `(-)xxxxx.x` (m) | — |
|11 | `longitude_deg` | ≤ 11 | `(-)xxx.xxxxxx` | — |
|12 | `latitude_deg` | ≤ 10 | `(-)xx.xxxxxx` | — |
|13 | `gnss_utc_time` | 14 | `YYYYMMDDHHMMSS` (UTC) | — |
|14 | `mcc` | 4 | `0XXX` | Puede faltar |
|15 | `mnc` | 4 | `0XXX` | Puede faltar |
|16 | `lac_hex` | 4 | `XXXX` (hex) | Puede faltar |
|17 | `cell_id_hex` | 4 \| 8 | `XXXX` \| `XXXXXXXX` (hex) | Puede faltar |
|18 | `position_append_mask` | 2 | `00–FF` (hex) | **Gobierna campos 19–22** |
|19 | `satellites_in_use` *(opt.)* | ≤ 2 | `0–72` | **Bit0=1** |
|20 | `horizontal_gnss_accuracy` *(opt.)* | ≤ 5 | `0.00–99.99` | **Bit1=1** |
|21 | `vertical_gnss_accuracy` *(opt.)* | ≤ 5 | `0.00–99.99` | **Bit2=1** |
|22 | `gnss_3d_accuracy` *(opt.)* | ≤ 5 | `0.00–99.99` | **Bit3=1** |

### 1.3 Tail
| # | Campo | Long. | Rango/Formato | Notas |
|--:|-------|:-----:|---------------|-------|
|23 | `send_time` | 14 | `YYYYMMDDHHMMSS` (UTC) | — |
|24 | `count_number` | 4 | `0000–FFFF` (hex) | **Contador, no CRC** |
|25 | `tail` | 1 | `$` | — |

---

## 2) Append Mask (Position Append Mask)

**Campo:** `position_append_mask` (2 hex). Igual interpretación bit a bit que GTFRI.

| Bit | Campo | Rango |
|----:|---------------------------|--------|
|  0  | `satellites_in_use`      | 0–72   |
|  1  | `horizontal_gnss_accuracy`| 0.00–99.99 |
|  2  | `vertical_gnss_accuracy` | 0.00–99.99 |
|  3  | `gnss_3d_accuracy`       | 0.00–99.99 |

**Regla:** si un bit = **1**, el campo correspondiente **debe** estar presente (puede venir vacío si el firmware así lo envía). Si bit = **0**, el campo puede omitirse o venir vacío y el parser debe asignar `null`/vacío.

---

## 3) Reglas de parsing / validaciones

- Tokenizar por `,` y exigir `tail = '$'`.
- `device_name` **debe** ser `GV310LAU`.
- Rangos:  
  - `gnss_accuracy_level ∈ [0,50]`  
  - `speed_kmh ∈ [0.0, 999.9]`  
  - `azimuth_deg ∈ [0,359]`  
  - `jamming_state ∈ {0,1}`
- `count_number`: exactamente **4** hex (`0000–FFFF`), **contador** de reporte (no checksum).

---

## 4) Derivaciones recomendadas

- `lac` = `hex_to_uint(lac_hex)`  
- `cell_id` = `hex_to_uint(cell_id_hex)`  
- `gnss_chile_time` = `gnss_utc_time` en `America/Santiago` (respeta horario de verano/invierno).  
- `send_chile_time` = `send_time` en `America/Santiago`.

> Ejemplo de conversión (Chile continental, DST vigente al **16 Oct 2025**):  
> `gnss_utc_time=20251016202522` → `gnss_chile_time=2025-10-16 17:25:22 -03`

---

## 5) Ejemplos reales (+RESP / +BUFF)

```
+BUFF:GTJDS,6E0201,868589060108605,GV310LAU,2,5,0,0.0,33,110.2,-109.357724,-27.142409,20251016195902,,,,,00,20251016195946,28A3$
+BUFF:GTJDS,6E0201,868589060108605,GV310LAU,1,5,0,0.0,33,110.2,-109.357724,-27.142409,20251016195902,0730,0001,158F,0530E982,00,20251016195902,28A2$
+RESP:GTJDS,6E0C03,868589060379784,GV310LAU,1,3,1,85.7,350,1206.3,-69.972567,-28.038460,20251016202522,0730,0001,0C82,00550412,00,20251016202522,8170$
+BUFF:GTJDS,6E0201,868589060079137,GV310LAU,2,5,0,0.0,249,117.2,-109.358792,-27.140638,20251016201343,,,,,00,20251016201442,8A0F$
+RESP:GTJDS,6E0C03,868589060379784,GV310LAU,2,3,1,50.4,254,1222.4,-69.965529,-28.043803,20251016202421,,,,,00,20251016202421,816B$
+RESP:GTJDS,6E0C03,868589060255190,GV310LAU,2,3,1,115.9,312,756.3,-70.623718,-33.350398,20251016202230,,,,,00,20251016202231,8378$
+RESP:GTJDS,6E0C03,868589060255190,GV310LAU,1,3,0,126.8,339,759.7,-70.625297,-33.348113,20251016202239,0730,0002,0517,00103625,00,20251016202301,837A$
+RESP:GTJDS,6E0C03,868589060379784,GV310LAU,1,3,1,64.8,314,1230.5,-69.958904,-28.047502,20251016202333,0730,0002,A413,006E130A,00,20251016202334,8168$
+RESP:GTJDS,6E0C03,868589060379784,GV310LAU,2,3,1,88.6,347,1266.0,-69.951155,-28.065686,20251016202145,,,,,00,20251016202146,8162$
+BUFF:GTJDS,6E0405,868589060248765,GV310LAU,2,3,0,29.1,64,472.4,-72.157288,-38.322191,20251016201851,,,,,00,20251016201851,80DE$
```

**Notas de los ejemplos**
- Cuando `mcc/mnc/lac/cell_id` están vacíos, el parser debe aceptar `null` para esos campos.  
- `position_append_mask=00` en todas las tramas mostradas ⇒ no aparecen campos 19–22.  
- `count_number` es el **contador** (4 hex), p.ej. `8170`, `28A2`.

---

## 6) Casos de prueba sugeridos

1. **Básico sin máscara**: `position_append_mask=00` y ausencia de campos 19–22.  
2. **Máscara completa**: `position_append_mask=0F` con los 4 campos GNSS adicionales.  
3. **Estados de jamming**: `jamming_state=1` (detectado) y `jamming_state=0` (liberado).  
4. **Con/Si red celular**: con `mcc/mnc/lac/cell_id` presentes y ausentes.  
5. **Varias redes**: `jamming_net=1..5`.  

---

## 7) Referencias de protocolo

- **Jamming Net** (valores 1–5) declarado en sección JDR/JDS del protocolo.  
- **Lista de IDs de mensajes**: `GTJDS` tiene **Message ID = 32**.

