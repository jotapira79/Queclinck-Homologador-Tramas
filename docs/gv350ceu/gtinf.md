# +RESP/+BUFF:GTINF — GV350CEU

> **Referencia oficial:** Sección 4.3.1 *INF (Device Information)* — *GV350CEU @Track Air Interface Protocol*  
> **Mensaje:** +RESP:GTINF o +BUFF:GTINF  
> **Función:** Reporte periódico con el estado general del dispositivo.

---

## 1️⃣ Descripción general

El mensaje **GTINF** entrega información de estado del equipo, potencia, tipo de red, batería, IO digitales/analógicos y último *fix GNSS*.  
Se envía periódicamente cuando la función está habilitada por el comando:



### 🧩 Estructura general

```text
+RESP|+BUFF:GTINF,<ProtocolVersion>,<IMEI>,<DeviceName>,<MotionStatus>,<ICCID>,
<CSQ>,<BER>,<ExtPowerSupply>,<ExtPowerVoltage>,<NetworkType>,<BackupBattVolt>,
<Charging>,<LEDState>,,,<LastFixUTC>,,<AI1>,<AI2>,<AI3>,<DI>,<DO>,
<TimeZoneOffset>,<DST>,<SendTime>,<CountHex>$

- Los campos marcados con ,,, o ,, indican reservados o no usados.
- La longitud y el orden pueden variar ligeramente según firmware.
- Los prefijos +RESP: o +BUFF: indican si el mensaje es en tiempo real o almacenado en buffer.

---

## 2️⃣ Tramas de ejemplo

**RESP**
+RESP:GTINF,74040A,862524060748775,GV350CEU,11,89999112400719062394,37,0,1,13074,,4.19,0,1,,,20251007213710,,0,0,0,00,00,+0000,0,20251007213751,6B91$
+RESP:GTINF,740904,862524060876527,GV350CEU,11,8935711001088072340f,27,0,1,25526,3,4.10,0,1,,,20251008123045,,0,0,0,10,00,+0000,0,20251008123244,3F27$
+RESP:GTINF,740904,862524060869597,GV350CEU,11,8935711001092192068f,40,0,1,12741,3,4.14,0,1,,,20251008040714,,0,0,0,10,00,+0000,0,20251008040944,283D$
+RESP:GTINF,740904,862524060869597,GV350CEU,11,8935711001092192068f,40,0,1,12592,3,4.14,0,1,,,20251008010712,,0,0,0,10,00,+0000,0,20251008010944,2816$
+RESP:GTINF,74040A,862524060748775,GV350CEU,11,89999112400719062394,38,0,1,12917,,4.19,0,1,,,20251008023706,,0,0,0,00,00,+0000,0,20251008023753,6CE0$


**BUFF**
+BUFF:GTINF,740904,862524060867948,GV350CEU,11,8935711001088072837f,69,0,1,12992,3,4.15,0,1,,,20251008120817,,0,0,0,10,02,+0000,0,20251008121018,59E7$
+BUFF:GTINF,740904,862524060867948,GV350CEU,22,8935711001088072837f,41,0,1,14037,3,4.16,0,1,,,20251008111017,,0,0,0,11,02,+0000,0,20251008111018,5901$
+BUFF:GTINF,740904,862524060876527,GV350CEU,21,8935711001088072340f,22,0,1,28328,3,4.09,0,1,,,20251008053249,,0,0,0,11,00,+0000,0,20251008053250,3BB4$
+BUFF:GTINF,740904,862524060876527,GV350CEU,11,8935711001088072340f,6,0,1,26137,1,4.10,0,1,,,20251008042911,,0,0,0,10,00,+0000,0,20251008042911,3B28$
+BUFF:GTINF,740904,862524060876527,GV350CEU,11,8935711001088072340f,4,0,1,25127,0,4.10,0,1,,,20251008032812,,0,0,0,10,00,+0000,0,20251008032911,3AA3$

---

## 3️⃣ Campos principales

| Parte | Campo | Longitud | Ejemplo | Descripción |
|--------|--------|-----------|-----------|-------------|
| **Head** | `Header` | 8 | +RESP:GT / +BUFF:GT | Indica el tipo de mensaje: respuesta normal (+RESP) o almacenada en buffer (+BUFF). |
|  | `Message Name` | 3 | INF | Nombre del mensaje reportado (GTINF). |
|  | `Leading Symbol` | 1 | , | Separador entre el encabezado y los campos del cuerpo. |
| **Body** | `Protocol Version` | 6 | 740B05 | Versión completa del protocolo (000000–FFFFFF). |
|  | `Unique ID` | 15 | 862524060748775 | IMEI del dispositivo (identificador único). |
|  | `Device Name` | ≤20 | GV350CEU | Nombre del modelo reportado. |
|  | `Motion Status` | 2 | 11, 12, 21, 22, 16, 1A | Estado de movimiento (ver tabla correspondiente). |
|  | `ICCID` | ≤20 | 89999112400719062394 | Identificador de la tarjeta SIM; puede contener letras a–f. |
|  | `CSQ` | 1–3 | 37 | Intensidad de señal (RSSI o RSRP según tecnología). |
|  | `BER` | 1–2 | 0 | Bit Error Rate (calidad de señal GSM). |
|  | `ExtPowerSupply` | 1 | 1 | Indica si la fuente externa está conectada (1=Sí, 0=No). |
|  | `ExtPowerVoltage` | 4–5 | 13074 | Voltaje de alimentación externa en milivoltios. |
|  | `NetworkType` | 1 | 3 | Tipo de red: 0=No registrado, 1=EGPRS, 2=UMTS, 3=LTE. |
|  | `BackupBattVoltage` | 4 | 4.19 | Voltaje de batería de respaldo en voltios. |
|  | `Charging` | 1 | 0 | Estado de carga de batería (1=Cargando, 0=No). |
|  | `LEDState` | 1 | 1 | Estado del LED indicador (1=Encendido, 0=Apagado). |
|  | `LastFixUTC` | 14 | 20251007213710 | Última posición GNSS válida (UTC). |
|  | `AnalogInput1` | 0–5 | 0 | Valor analógico 1 (voltaje o porcentaje según configuración). |
|  | `AnalogInput2` | 0–5 | 0 | Valor analógico 2 (voltaje o porcentaje según configuración). |
|  | `AnalogInput3` | 0–5 | 0 | Valor analógico 3 (voltaje o porcentaje según configuración). |
|  | `DigitalInput` | 4 | 0000 | Estado lógico de entradas digitales (bits). |
|  | `DigitalOutput` | 4 | 0000 | Estado lógico de salidas digitales (bits). |
|  | `TimeZoneOffset` | 5 | +0000 | Diferencia horaria local respecto a UTC. |
|  | `DaylightSaving` | 1 | 0 | Horario de verano (1=Activo, 0=Inactivo). |
|  | `SendTime` | 14 | 20251007213751 | Timestamp de envío del mensaje (UTC). |
|  | `CountHex` | 4 | 6B91 | Contador incremental en formato hexadecimal (MAYÚSCULAS). |

---

### 🔹 Notas

- Los campos del bloque **Head** (`Header`, `Message Name`, `Leading Symbol`) forman parte de la cabecera del mensaje, pero generalmente no se almacenan en la base de datos.
- El parser `parse_line()` usa el prefijo `+RESP:` o `+BUFF:` para determinar automáticamente el campo `source` (`RESP` o `BUFF`).
- `Message Name` (`INF`) y `Leading Symbol` (`,`) se utilizan internamente para identificar el tipo de mensaje y separar los campos.
- `Protocol Version` siempre debe representarse en **mayúsculas HEX**.
- `SendTime` se normaliza a formato ISO-8601 (`send_time_iso`) tomando **el último timestamp de 14 dígitos** en la trama.
- La identificación del modelo en homologación se realiza por el prefijo del IMEI (`86252406`).



---

## 4️⃣ Tabla de Motion Status

| Código | Estado | Descripción |
|--------|---------|-------------|
| 16 | Tow | Ignición OFF, vehículo remolcado |
| 1A | Fake Tow | Ignición OFF, posible remolque |
| 11 | Ign. Off Rest | Motor apagado, inmóvil |
| 12 | Ign. Off Motion | Motor apagado, en movimiento breve |
| 21 | Ign. On Rest | Motor encendido, inmóvil |
| 22 | Ign. On Motion | Motor encendido, en movimiento |
| 41 | Sensor Rest | Sin ignición detectada, inmóvil |
| 42 | Sensor Motion | Sin ignición detectada, en movimiento |

---

## 5️⃣ Reglas de parsing (para homologación)

- `protocol_version`: siempre en **mayúsculas HEX**.  
- Detectar `source` según prefijo `+RESP` o `+BUFF`.  
- `imei`: validar 15 dígitos.  
- `iccid`: alfanumérico (puede incluir letras `a–f`).  
- `count_hex`: normalizar a **mayúsculas**.  
- `send_time_iso`: derivar del **último timestamp (14 dígitos)** encontrado.  
- Campos numéricos → convertir a int/float según tipo.  
- `tz_offset` y `daylight_saving` → opcionales (si faltan, default `+0000`, `0`).  

---

## 6️⃣ Consideraciones adicionales

- El valor de `BackupBatteryVoltage` solo es válido si `ExtPowerSupply=0`.  
- Si no hay fix GNSS, `LastFixUTC` puede venir vacío.  
- En modo *buffered*, los campos pueden variar ligeramente según firmware.  
- El mensaje no se envía por SMS (solo TCP/UDP).  

---

### ✅ Resumen homologación GTINF GV350CEU

- Compatible con parser modular (`queclink/messages/gtinf.py`).  
- `parse_line()` debe entregar:
  ```json
  {
    "message": "GTINF",
    "device": "GV350CEU",
    "source": "RESP|BUFF",
    "imei": "862524060748775",
    "protocol_version": "74040A",
    "send_time_iso": "2025-10-07T21:37:51Z",
    "count_hex": "6B91"
  }
