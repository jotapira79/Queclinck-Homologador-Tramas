[docs_protocolo_gv310lau_gteri.md](https://github.com/user-attachments/files/22680988/docs_protocolo_gv310lau_gteri.md)
# Protocolo +RESP:GTERI para GV310LAU (Resumen operativo)

> **Sección fuente:** 4.2.3 ERI (Expand Fixed Report Information) — "GV310LAU @Track Air Interface Protocol".

Este documento resume, normaliza y hace operativa la especificación del mensaje **+RESP:GTERI** para el equipo **GV310LAU**. Está pensado para que herramientas como GitHub Copilot/Codex y colaboradores humanos puedan:

- Entender rápidamente la estructura campo a campo.
- Implementar/ajustar parsers (ASCII) y validadores.
- Generar casos de prueba (válidos/erróneos).
- Activar campos opcionales según **Position Append Mask** y **ERI Mask**.

---

## 1) Descripción general

- **Nombre de mensaje:** `+RESP/+BUFF:GTERI`
- **Dispositivo:** `GV310LAU`  
- **Propósito:** Reporte de posición ampliado (sustituye a `+RESP:GTFRI` cuando la función ERI está habilitada).  
- **Formato:** ASCII, campos separados por coma `,` y terminados con `$`.
- **Identificación del modelo:** la homologación usa el prefijo IMEI `86858906`,
  independiente del valor configurado en `Device Name`.

> Cuando `+RESP:GTERI` está habilitado, el equipo envía `+RESP:GTERI` en lugar de `+RESP:GTFRI`.

---

## 2) Ejemplo de trama

```
+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000100,,10,1,1,0.0,0,115.8,117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,0000102:34:33,14549,42,11172,100,210000,0,1,0,06,12,0,001A42A2,0617,TMPS,08351B00043C,1,26,65,20231030085704,20231030085704,0017$
```

> **Nota:** Puede variar la presencia de campos opcionales dependiendo de **Position Append Mask** y **ERI Mask**.

---

## 3) Estructura y campos

La trama se divide en **Head**, **Body** y **Tail**. A continuación, se listan los campos en orden, con rangos y formato esperado. Los campos "Opcional" aparecen sólo si los habilitan las máscaras indicadas.

### 3.1 Head

| Parte  | Campo            | Longitud | Rango/Formato                            |
|--------|------------------|----------|------------------------------------------|
| Head   | Header           | 8        | `+RESP:GT` \| `+BUFF:GT`                 |
|        | Message Name     | 3        | `ERI`                                     |
|        | Coma separadora  | 1        | `,`                                       |
|        | Full Proto Ver.  | 6        | `000000` – `FFFFFF` (hex)                |
|        | Unique ID        | 15       | IMEI                                      |
|        | Device Name      | ≤20      | 0–9, a–z, A–Z, `-`, `_` (personalizable)  |

### 3.2 Body

| Parte | Campo                                | Long.  | Rango/Formato                                  | Notas |
|------|--------------------------------------|--------|------------------------------------------------|-------|
| Body | ERI Mask                             | 8      | `00000000` – `FFFFFFFF` (hex)                  | Controla datos ERI (p. ej., 1-wire, CAN, fuel). |
|      | External Power Supply                | ≤5     | 0 – 32000 (mV)                                 | — |
|      | Report ID / Report Type              | 2      | `X(1-5)Y(0-6)`                                 | — |
|      | Number                               | ≤2     | 1 – 15                                         | — |
|      | GNSS Accuracy                        | ≤2     | 0 – 50                                         | — |
|      | Speed                                | ≤5     | 0.0 – 999.9 (km/h)                             | — |
|      | Azimuth                              | ≤3     | 0 – 359                                        | — |
|      | Altitude                             | ≤8     | (-)xxxxx.x (m)                                 | — |
|      | Longitude                            | ≤11    | (-)xxx.xxxxxx                                  | — |
|      | Latitude                             | ≤10    | (-)xx.xxxxxx                                   | — |
|      | GNSS UTC Time                        | 14     | `YYYYMMDDHHMMSS`                               | UTC |
|      | MCC                                  | 4      | `0XXX`                                         | — |
|      | MNC                                  | 4      | `0XXX`                                         | — |
|      | LAC                                  | 4      | `XXXX` (hex)                                   | — |
|      | Cell ID                              | 4/8    | `XXXX` o `XXXXXXXX` (hex)                      | — |
|      | Position Append Mask                 | 2      | `00` – `FF` (hex)                              | Define presencia de campos posicionales anexos. |
|      | Satellites in Use (Opcional)         | ≤2     | 0 – 72                                         | Bit 0 de Position Append Mask. |
|      | Horizontal GNSS Accuracy (HDOP)*     | ≤5     | 0.00 – 99.99                                   | 0=fix fallido (usa última pos.); ≠0=HDOP actual. |
|      | Vertical GNSS Accuracy (VDOP)*       | ≤5     | 0.00 – 99.99                                   | Igual lógica; representa VDOP. |
|      | 3D GNSS Accuracy (PDOP)*             | ≤5     | 0.00 – 99.99                                   | Igual lógica; representa PDOP. |
|      | Mileage                              | ≤9     | 0.0 – 4294967.0 (km)                           | — |
|      | Hour Meter Count                     | 13     | `0000000:00:00` – `1193000:00:00`              | Horómetro. |
|      | Analog Input 1                       | ≤5     | 0 – 16000 (mV) \/ `F(0–100)`                   | Según modo. |
|      | Analog Input 2                       | ≤5     | 0 – 16000 (mV) \/ `F(0–100)`                   | — |
|      | Analog Input 3                       | ≤5     | 0 – 16000 (mV) \/ `F(0–100)`                   | — |
|      | Backup Battery Percentage            | ≤3     | 0 – 100 (%)                                    | — |
|      | Device Status                        | 6/10   | `000000`–`FFFFFF` o `0000000000`–`0F0FFFFFFF` | — |
|      | UART Device Type                     | 1      | 0–2 \| 5–7                                      | Ver tabla abajo. |
|      | Digital Fuel Sensor Data (Opc.)      | ≤20    | —                                              | ERI Mask bit 0. |
|      | 1‑wire Data (Opc.)                   | —      | —                                              | ERI Mask bit 1. |
|      | CAN Data (Opc.)                      | ≤1000  | —                                              | ERI Mask bit 2. |
|      | Fuel Sensor Data (Opc.)              | —      | —                                              | ERI Mask bit 10 + tipo. |
|      | RF433 Accessory Data (Opc.)          | —      | —                                              | — |
|      | Bluetooth Accessory Data (Opc.)      | —      | —                                              | Ver máscara propia. |

\* *HDOP/VDOP/PDOP:* 0 indica fix GNSS fallido (usa última posición conocida). Valor >0 representa el DOP actual (menor es mejor).

### 3.3 Tail

| Parte | Campo       | Longitud | Rango/Formato        |
|------|-------------|----------|----------------------|
| Tail | Send Time   | 14       | `YYYYMMDDHHMMSS`     |
|      | Count N°    | 4        | `0000` – `FFFF` (hex) |
|      | Terminador  | 1        | `$`                  |

---

## 4) Máscaras y datos opcionales

### 4.1 Position Append Mask (1 byte, hex)
Controla los **campos posicionales** después de `<Cell ID>`.  
- **Bit 0** habilita **Satellites in Use**.
- Otros bits activan los campos de precisión **HDOP/VDOP/PDOP**, etc. (según firmware).

### 4.2 ERI Mask (4 bytes, hex)
Controla los **bloques ERI**:
- **Bit 0** → *Digital Fuel Sensor Data*.
- **Bit 1** → *1‑wire Data* (incluye ID/Type/Data). Si Type=1 (temperatura), los datos están en **complemento a dos**; convertir a decimal y multiplicar × 0.0625 °C. Si el bit está deshabilitado, el bloque completo (número de dispositivos y lista) no aparece en la trama. Cuando `Device Number` es `0`, tampoco se listan ID/Type/Data. Algunos firmwares omiten `Type` y/o `Data` cuando no hay información adicional; el parser acepta esos campos vacíos/ausentes.
- **Bit 2** → *CAN Data*.
- **Bit 10** → *Fuel Sensor Data* (si *Sensor Type* es 2 ó 6, puede incluir *Fuel Temperature*).

> *Sensor Type* (combustible): 0 (EPSILON ES2/ES4), 1 (LLS 20160), 2 (DUT‑E), 3 (QFS100), 4 (UFSxxx RS232), 6 (DUT‑E SUM), 8 (Escort Fuel), 20/21/22 (ADC1/2/3).

### 4.3 UART Device Type
- 0: Sin dispositivo  
- 1: Digital fuel sensor  
- 2: 1‑wire bus  
- 5: CANBUS device  
- 6: AU100 device  
- 7: WRT100 accessory

### 4.4 RF433 Accessory Data (opcional)
- **Accessory Number** (0–10).  
- **Accessory Serial Number** (5 hex).  
- **Accessory Type**: 1=WTS100 (Temp), 2=WTH100 (Temp+Humedad).  
- **Temperature**: −20 a 60 °C (x1). **Humidity**: 0–100 % (si Type=2).

### 4.5 Bluetooth Accessory Data (opcional)
Incluye múltiples sub‑campos: Number, Index, Type, Model/BeaconID, Raw Data, **Accessory Append Mask** y varios opcionales (Name, MAC, Status, Battery Voltage/%, Temperature/Humidity, I/O, Mode/Event, Tire pressure, Timestamp, Enhanced Temp, Magnet ID/State/Event Counter, Relay state, etc.).

**Accessory Append Mask (16 bits)**

| Bit | Ítem                                           |
|-----|------------------------------------------------|
| 0   | Accessory Name                                 |
| 1   | Accessory MAC                                  |
| 2   | Accessory Status (conectado/desconectado)      |
| 3   | Accessory Battery Voltage                      |
| 4   | Accessory Temperature                          |
| 5   | Accessory Humidity                             |
| 6   | Reservado                                      |
| 7   | Accessory I/O (Output status / Digital Input / Analog V) |
| 8   | Accessory Event Notification (Mode/Event)      |
| 9   | Tire pressure                                  |
| 10  | Timestamp                                      |
| 11  | Enhanced Temperature                           |
| 12  | Magnet Data (ID / Event Counter / State)       |
| 13  | Accessory Battery Percentage                   |
| 14  | Relay Data (config/result, state)              |
| 15  | Si =0 → válidos bits 0–14                      |

**Notas de "Raw Data" según accesorio (ejemplos)**
- **WTH300**: 4 bytes hex; 2 bytes altos = Temp, 2 bytes bajos = Humedad. Temp = (low/256 + high) °C; Humidity = (low/256 + high) %rh.
- **WTS300**: 4 bytes hex; 2 bytes altos = Battery (mV), 2 bytes bajos = Temp (low/256 + high) °C.
- **WMS301/WTH301**: 4 bytes hex; 2 bytes altos = Humidity/100 %rh; 2 bytes bajos = Temp/100 °C.
- **Fuel sensor**: decimal; para Mechatronics, si inicia con `FXX` es porcentaje (si no, valor crudo). Ver `AT+GTBAS` (*Fuel Level Format*).
- **ATP100/ATP102**: 4 bytes hex; byte2 presión (kPa ≈ byte×2.5), byte3 temperatura (°C = byte−40), nibble alto byte4=modelo, nibble bajo byte4=fw.
- **MAG ELA**: 4 bytes hex; 2 bytes bajos= MAG data, 2 bytes altos= MAG ID.
- **Escort Angle Sensor**: 4 bytes hex; byte alto #1 reservado (00), #2 = Event Notification, 2 bytes bajos = Tilt Angle.
- **Mechatronics Angle Sensor**: 8 bytes; Reservado, X/Y/Z (−90..90), Status, Single/Complex events.

---

## 5) Reglas de parsing y validación

1. **Tokenización:** separar por comas `,`; validar que el primer token sea `+RESP:GTERI` o `+BUFF:GTERI` y el último termine con `$`.
2. **Tipos:** convertir numéricos (enteros, float) y fechas (`YYYYMMDDHHMMSS` → UTC ISO‑8601).
3. **Máscaras:** evaluar **Position Append Mask** (1 byte) y **ERI Mask** (4 bytes) para decidir presencia de campos opcionales.
4. **Rangos:** aplicar validaciones de rango/forma indicadas en las tablas. Rechazar valores fuera de rango.
5. **Consistencia:** si GNSS Accuracy (HDOP/VDOP/PDOP) = 0, marcar `fix=false` y considerar lat/lon como última posición conocida (flag `is_last_fix=true`).
6. **Accesorios:** parsear bloques RF433/BLE iterando por cantidad reportada; aplicar máscara de *Accessory Append Mask* a cada accesorio.

---

## 6) Salida sugerida del parser

Estructura JSON sugerida para `parse_gteri(trama: str) -> dict`:

```json
{
  "header": "+RESP:GTERI",
  "proto_ver": "6E1203",
  "imei": "864696060004173",
  "device": "GV310LAU",
  "eri_mask": "00000100",
  "ext_power_mv": 0,
  "report_type": "10",
  "seq": 1,
  "gnss_acc": 1,
  "speed_kmh": 0.0,
  "azimuth_deg": 0,
  "alt_m": 115.8,
  "lon": 117.129356,
  "lat": 31.839248,
  "utc": "2023-08-08T06:15:40Z",
  "mcc": "0460",
  "mnc": "0001",
  "lac": "DF5C",
  "cell_id": "05FE6667",
  "pos_append_mask": "03",
  "sats": 15,
  "hdop": 4.0,
  "vdop": null,
  "pdop": null,
  "mileage_km": 14549.0,
  "hour_meter": "0000102:34:33",
  "ai1": 42,
  "ai2": 11172,
  "device_status": "210000",
  "uart_type": 0,
  "fuel": { "type": "TMPS", "raw": "08351B00043C" },
  "ble": { "count": 1, "items": [ { "idx": 0, "temp_c": 26, "humidity_pct": 65 } ] },
  "send_time": "2023-10-30T08:57:04Z",
  "count_hex": "0017"
}
```

> **Nota:** el ejemplo de salida es ilustrativo; adapte nombres/normalización a su code‑style.

---

## 7) Casos de prueba mínimos

- **Trama válida con ERI/Position Mask** activas (como el ejemplo).
- **Trama válida sin campos opcionales** (máscaras a 0).
- **GNSS Accuracy = 0** (usar última posición conocida; flags `fix=false`, `is_last_fix=true`).
- **RF433/BLE con múltiples accesorios**.
- **Sensor de combustible Mechatronics (Fxx)** y DUT‑E (Type=2/6) con temperatura.
- **Valores fuera de rango** → excepción controlada `ParseError`.

---

## 8) Referencias cruzadas

- *AT+GTFRI* (controla **ERI Mask** y campos opcionales).
- *AT+GTBAS* (Fuel Level Format para sensores Mechatronics, etc.).

---

## 9) Notas de implementación

- Conservar los campos crudos (hex/ASCII) junto a los normalizados cuando haya conversiones.
- Encapsular lógica de máscaras y bloques en funciones independientes (mantenibilidad y tests unitarios).
- Definir `NamedTuple/dataclass` para la parte posicional y para cada bloque (RF433, BLE, Fuel, 1‑wire, CAN).
- Incluir *doctests* en funciones de conversión (p. ej., temperatura 1‑wire a °C, presión ATP100 a kPa, etc.).

