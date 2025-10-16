+RESP/+BUFF:GTFRI — GV58LAU

Mensaje: FRI (Fixed Report Information) — reporte fijo de posición sin bloques ERI.
Dispositivo: GV58LAU
Formato: ASCII separado por comas ,, terminado con $.

1) Descripción

GTFRI entrega posición GNSS y datos básicos del terminal cuando no hay datos de periféricos (ERI).
Si la ERI Mask de AT+GTFRI habilita periféricos y existen datos de ellos, el equipo enviará +RESP:GTERI en lugar de GTFRI.

2) Ejemplo de trama
+RESP:GTFRI,6E1203,866314060873492,GV58LAU,12041,11,1,0,64.0,117.129299,31.838832,20250314085445,0460,0000,550B,0E9E30A5,0D,12,210100,0.00,0.00,0.00,20250314085447,0132$
Nota: El ejemplo anterior es minimalista y está pensado para pruebas de parsing; los campos opcionales controlados por Position Append Mask (Sats/HDOP/VDOP/PDOP o Accuracy Factor) pueden aparecer o no según los bits activos. Los campos reservados pueden venir como vacíos o con 0.00 según firmware/configuración.

3) Estructura de la trama
La trama se divide en Head, Body y Tail. Los nombres/orden coinciden con gtfri.yml.

3.1 Head
| Orden | Campo                   | Tipo   | Formato/Valores               | Ejemplo           |
| ----: | ----------------------- | ------ | ----------------------------- | ----------------- |
|     1 | `header`                | string | `+RESP:GTFRI` | `+BUFF:GTFRI` | `+RESP:GTFRI`     |
|     2 | `full_protocol_version` | hex    | 6 hex (mayúsculas)            | `6E1203`          |
|     3 | `imei`                  | string | 15 dígitos                    | `866314060873492` |
|     4 | `device_name`           | string | 1–20 (`0-9A-Za-z-_`)          | `GV58LAU`         |

3.2 Body
| Orden | Campo                         | Tipo     | Formato/Valores                 | Notas                                    |
| ----: | ----------------------------- | -------- | ------------------------------- | ---------------------------------------- |
|     5 | `external_power_mv`           | int      | 0–32000 (mV) | vacío            | Puede venir vacío.                       |
|     6 | `report_type`                 | string   | 2 chars, `X(1-5)Y(0-6)`         | En `Mode=99` suele ser `00`.             |
|     7 | `number`                      | int      | 1–15                            | Secuencia / multipunto.                  |
|     8 | `gnss_accuracy_level`         | int      | 0–50                            | 0 = sin fix.                             |
|     9 | `speed_kmh`                   | float    | 0.0–999.9 (km/h)                | —                                        |
|    10 | `azimuth_deg`                 | int      | 0–359 (grados)                  | —                                        |
|    11 | `altitude_m`                  | float    | (-)xxxxx.x (m)                  | —                                        |
|    12 | `longitude_deg`               | float    | (-)xxx.xxxxxx                   | —                                        |
|    13 | `latitude_deg`                | float    | (-)xx.xxxxxx                    | —                                        |
|    14 | `gnss_utc_time`               | datetime | `YYYYMMDDHHMMSS` (UTC)          | Convertir a America/Santiago.            |
|    15 | `mcc`                         | string   | `0XXX`                          | —                                        |
|    16 | `mnc`                         | string   | `0XXX`                          | —                                        |
|    17 | `lac`                         | hex      | 4 hex                           | —                                        |
|    18 | `cell_id`                     | hex      | 4 u 8 hex                       | —                                        |
|    19 | `position_append_mask`        | hex      | 1 byte (`00`–`FF`)              | Controla campos 20–23.                   |
|    20 | `sats_in_use` *(opt.)*        | int      | 0–72                            | Presente si **bit 0** = 1.               |
|    21 | `hdop` *(opt.)*               | float    | 0.00–99.99                      | Presente si **bit 1** = 1.               |
|    22 | `vdop` *(opt.)*               | float    | 0.00–99.99                      | Presente si **bit 2** = 1.               |
|    23 | `pdop_or_acc_factor` *(opt.)* | float    | 0.00–99.99                      | Presente si **bit 3** = 1 (ver compat.). |
|    24 | `mileage_km`                  | float    | 0.0–4,294,967.0 (km)            | —                                        |
|    25 | `hour_meter`                  | string   | `0000000:00:00`–`1193000:00:00` | Horómetro.                               |
|    26 | `reserved1`                   | number   | —                               | Puede venir vacío/0.00.                  |
|    27 | `reserved2`                   | number   | —                               | Puede venir vacío/0.00.                  |
|    28 | `reserved3`                   | number   | —                               | Puede venir vacío/0.00.                  |
|    29 | `backup_batt_pct`             | int      | 0–100 (%) | vacío               | Opcional.                                |
|    30 | `device_status`               | hex      | 6 u 10 hex                      | Flags del equipo.                        |
|    31 | `reserved4`                   | number   | —                               | Puede venir vacío/0.00.                  |
|    32 | `reserved5`                   | number   | —                               | Puede venir vacío/0.00.                  |
|    33 | `reserved6`                   | number   | —                               | Puede venir vacío/0.00.                  |

3.3 Tail
| Orden | Campo          | Tipo     | Formato/Valores        |
| ----: | -------------- | -------- | ---------------------- |
|    34 | `send_time`    | datetime | `YYYYMMDDHHMMSS` (UTC) |
|    35 | `count_number` | hex      | 4 hex (`0000`–`FFFF`)  |
|    36 | `tail`         | string   | `$`                    |


4) Máscaras y campos opcionales
4.1 position_append_mask (1 byte, hex)
| Bit | Campo                | Descripción                                                   |
| --: | -------------------- | ------------------------------------------------------------- |
|   0 | `sats_in_use`        | Satélites usados en la solución GNSS                          |
|   1 | `hdop`               | Precisión horizontal                                          |
|   2 | `vdop`               | Precisión vertical                                            |
|   3 | `pdop_or_acc_factor` | **PDOP** o **GNSS accuracy factor** (según compatibilidad FW) |

Compatibilidad (config.posmask_bit3_mode):
"pdop" → interpretar el bit 3 como PDOP.
"accuracy_factor" → interpretar el bit 3 como Accuracy Factor.

5) Reglas de parsing y validación
Tokenización: dividir por , y validar header (+RESP:GTFRI/+BUFF:GTFRI) y tail ($).
Tipos: convertir enteros/float/hex y fechas (YYYYMMDDHHMMSS → UTC).
Máscaras: aplicar position_append_mask para decidir la presencia de sats_in_use, hdop, vdop, pdop_or_acc_factor.
Rangos: validar contra la tabla (errores → ParseError(campo, valor, motivo)).
Fix GNSS: si gnss_accuracy_level = 0, marcar fix=false y aplicar tu política (p. ej., mantener última posición válida).
Mode=99: si AT+GTFRI Mode=99 (real-time), esperar report_type = "00" cuando aplique.
Zona horaria Chile: convertir gnss_utc_time y send_time de UTC a America/Santiago, respetando DST para la fecha del evento.
Reservados: reserved1..reserved6 pueden venir vacíos o con 0.00; deben parsearse como null/0 según convención del proyecto (recomendado: null si vacío).

6) Salida JSON sugerida
Ajusta tipos null/0 para reservados según tu convención.
{
  "header": "+RESP:GTFRI",
  "full_protocol_version": "6E1203",
  "imei": "866314060873492",
  "device_name": "GV58LAU",

  "external_power_mv": 12041,
  "report_type": "11",
  "number": 1,

  "gnss_accuracy_level": 0,
  "speed_kmh": 64.0,
  "azimuth_deg": 0,
  "altitude_m": 64.0,
  "longitude_deg": 117.129299,
  "latitude_deg": 31.838832,
  "gnss_utc_time": "2025-03-14T08:54:45Z",

  "mcc": "0460",
  "mnc": "0000",
  "lac": "550B",
  "cell_id": "0E9E30A5",

  "position_append_mask": "0D",
  "sats_in_use": 12,
  "hdop": null,
  "vdop": null,
  "pdop_or_acc_factor": null,

  "mileage_km": 0.0,
  "hour_meter": "0000000:00:00",
  "reserved1": 0.00,
  "reserved2": 0.00,
  "reserved3": 0.00,
  "backup_batt_pct": null,
  "device_status": "210100",
  "reserved4": 0.00,
  "reserved5": 0.00,
  "reserved6": 0.00,

  "send_time": "2025-03-14T08:54:47Z",
  "count_number": "0132"
}
Nota: En el JSON anterior los DOP se dejan en null porque el ejemplo de trama no los incluye tras la máscara. Si tu firmware envía esos campos con el bit correspondiente activo, deben mapearse a float.

7) Casos de prueba mínimos
Sin opcionales: position_append_mask = 00 → no parsear Sats/HDOP/VDOP/PDOP.
Con DOP completos: bits 1–3 activos; validar límites 0.00–99.99.
Sin fix: gnss_accuracy_level = 0; marcar fix=false.
Mode=99: report_type = "00" en real-time.
Reservados: vacíos/0.00 deben aceptarse sin error y mapearse a null/0 según convención.
Errores: valores fuera de rango o formato incorrecto → ParseError con nombre del campo y detalle.

8) Notas de interoperabilidad
GTFRI no incluye bloques ERI (CAN, 1-wire, BLE, Fuel). Si hay periféricos habilitados y presentes, el equipo emitirá GTERI.
El tamaño de device_status puede variar (6 u 10 hex) según firmware.
cell_id puede venir en 4 u 8 hex según tecnología/red.
El bit-3 de position_append_mask puede significar PDOP o Accuracy Factor (configurable en config.posmask_bit3_mode).

9) Referencias cruzadas
AT+GTFRI — configuración de periodicidad, ERI mask y modos de reporte.
Position Append Mask — presencia de Sats/HDOP/VDOP/PDOP o Accuracy Factor.
AT+GTRTO — consulta de configuración AT (auditoría de FRI).
