# +RESP/+BUFF:GTINF — GV58LAU

> **Referencia oficial:** Sección 4.3.1 *INF (Device Information)* — *GV58LAU @Track Air Interface Protocol*  
> **Mensaje:** +RESP:GTINF o +BUFF:GTINF  
> **Función:** Reporte periódico con el estado general del dispositivo.

---

## 🧭 Descripción general

El mensaje **GTINF** entrega información de estado del equipo, potencia, tipo de red, batería, IO digitales y el último *fix GNSS*.  

---

## 🧩 Estructura general

+RESP|+BUFF:GTINF,<ProtocolVersion>,<IMEI>,GV58LAU,<MotionStatus>,<ICCID>,<CSQ>,<BER>,<ExtPowerSupply>,<ExtPowerVoltage>,<NetworkType>,<BackupBattVolt>,<Charging>,<LEDState>,,,<LastFixUTC>,<PinMask>,,,,<DI>,<DO>,<TimeZoneOffset>,<DST>,<SendTime>,<CountHex>$


- Los campos marcados con `,,,` o `,,` indican reservados o no usados.  
- La longitud y el orden pueden variar ligeramente según firmware.  

---

## 🧪 Tramas de ejemplo

**RESP**
+RESP:GTINF,8020040803,866314060873492,GV58LAU,22,89860015123286906624,67,0,1,11916,3,0.00,0,1,,,20250314083427,4,,,,01,00,+0000,0,20250314083428,0086$
+RESP:GTINF,8020040600,866314060351135,GV58LAU,21,89999112400719070694,25,0,1,13115,3,4.15,0,1,,,20251008145833,0,,,,01,00,+0000,0,20251008145831,84C4$
+RESP:GTINF,8020040600,866314061758098,GV58LAU,11,89999202003110004857,28,0,1,26333,3,4.14,0,1,,,20251008150051,0,,,,00,00,+0000,0,20251008150056,0DA7$
+RESP:GTINF,8020040900,866314061805311,GV58LAU,11,89999202003110015093,83,0,1,12735,3,4.09,0,1,,,20251008143643,0,,,,00,00,+0000,0,20251008150046,0791$
+RESP:GTINF,8020040305,866314060938543,GV58LAU,11,89999112400719085932,10,0,1,12782,2,4.09,0,1,,,20251008150029,0,,,,00,00,+0000,0,20251008150030,E966$

**BUFF**
+BUFF:GTINF,8020040600,866314061654792,GV58LAU,11,89999202003110001176,99,0,1,12154,0,4.16,0,1,,,20251008101350,0,,,,00,00,+0000,0,20251008101526,77ED$
+BUFF:GTINF,8020040600,866314061654792,GV58LAU,11,89999202003110001176,99,0,1,12220,0,4.15,0,1,,,,0,,,,00,00,+0000,0,20251008031453,77CE$
+BUFF:GTINF,8020040600,866314061654792,GV58LAU,11,89999202003110001176,10,0,1,12342,0,4.16,0,1,,,20251007194508,0,,,,00,00,+0000,0,20251007195742,77A9$
+BUFF:GTINF,8020040600,866314061805212,GV58LAU,11,89999202003110002836,23,0,1,12778,0,4.18,0,1,,,,0,,,,00,00,+0000,0,20251008142242,3439$
+BUFF:GTINF,8020040503,866314061554059,GV58LAU,11,89999112400719083622,255,0,1,12803,0,4.20,0,1,,,,0,,,,00,00,+0000,0,20251008052925,75DF$

---

## 🧾 Descripción de campos

| Campo | Descripción | Tipo / Formato | Valores posibles |
|--------|--------------|----------------|------------------|
| **ProtocolVersion** | Versión del protocolo implementado | HEX (10) | 8000000000 – 80FFFFFFFF |
| **IMEI** | Identificador único del dispositivo | Numérico (15) | — |
| **DeviceName** | Nombre del modelo de dispositivo | Texto (<=20) | GV58LAU |
| **MotionStatus** | Estado actual de movimiento | Numérico (2) | 11, 12, 21, 22, 41, 42, 1A, 16 |
| **ICCID** | ICCID de la SIM | Numérico (20) | — |
| **CSQ (RSSI/RSRP)** | Nivel de señal de la red celular | Numérico (<=3) | 0–31 / 99 (2G/3G), 0–97 / 255 (4G) |
| **BER** | Calidad de señal GSM | Numérico (<=2) | 0–7 / 99 |
| **ExtPowerSupply** | Estado de alimentación externa | 1 dígito | 0 = No conectada, 1 = Conectada |
| **ExtPowerVoltage** | Voltaje de alimentación externa | mV (<=5) | 0–32000 |
| **NetworkType** | Tipo de red celular | Numérico (1) | 0 = Unregistered, 1 = EGPRS, 2 = WCDMA, 3 = LTE |
| **BackupBattVolt** | Voltaje de batería interna | Voltios (4) | 0.00–4.50 |
| **Charging** | Estado de carga de batería interna | 1 dígito | 0 = No cargando, 1 = Cargando |
| **LEDState** | Estado de los LEDs | 1 dígito | 0 = Todos apagados, 1 = Alguno encendido |
| **LastFixUTC** | Hora UTC del último *GNSS fix* exitoso | YYYYMMDDHHMMSS | — |
| **PinMask** | Modo actual de pines | HEX (1) | 0–F |
| **DI** | Entradas digitales (bitwise) | HEX (<=2) | 00–03 |
| **DO** | Salidas digitales (bitwise) | HEX (<=2) | 00–07 |
| **TimeZoneOffset** | Diferencia horaria respecto a UTC | Texto (5) | +HHMM / -HHMM |
| **DST** | Estado de horario de verano | 1 dígito | 0 = Desactivado, 1 = Activado |
| **SendTime** | Hora UTC en que se envió el reporte | YYYYMMDDHHMMSS | — |
| **CountHex** | Contador hexadecimal del mensaje | HEX (4) | 0000–FFFF |

---

## 🚗 Valores posibles del Motion Status

| Código | Descripción |
|--------|--------------|
| 16 | Tow — Vehículo con ignición OFF y siendo remolcado |
| 1A | Fake Tow — Ignición OFF, posible remolque |
| 11 | Ignition Off Rest — Ignición OFF y detenido |
| 12 | Ignition Off Motion — Ignición OFF, en movimiento antes de considerarse remolque |
| 21 | Ignition On Rest — Ignición ON y detenido |
| 22 | Ignition On Motion — Ignición ON y en movimiento |
| 41 | Sensor Rest — Sin señal de ignición, vehículo detenido |
| 42 | Sensor Motion — Sin señal de ignición, vehículo en movimiento |

---

## 📶 Niveles de señal (CSQ RSSI / RSRP)

| Tecnología | Valor | Intensidad (dBm) |
|-------------|--------|------------------|
| **2G/3G** | 0 | < -113 |
|  | 1 | -111 |
|  | 2–30 | -109 ~ -53 |
|  | 31 | > -51 |
|  | 99 | Desconocido |
| **4G (LTE)** | 0 | < -140 |
|  | 1 | -140 |
|  | 2–96 | -139 ~ -44 |
|  | 97 | >= -44 |
|  | 255 | Desconocido |

---

## 📝 Notas adicionales

- La identificación del modelo en homologación se realiza por el prefijo del IMEI (`86631406`).
- Los valores `ffff` en los campos `<LAC>` y `<Cell ID>` indican que el terminal desconoce el valor.
- Este mensaje **no puede ser enviado por SMS**.
- La información de celda puede incluir datos de celdas vecinas o estar vacía si no hay celdas detectadas.

---

**Ejemplo completo de trama interpretada:**

+RESP:GTINF,8020040600,866314061628994,GV58LAU,22,89999202003110001275,44,0,1,13869,3,4.12,0,1,,,20251008150220,0,,,,01,02,+0000,0,20251008150221,D1F3$


- `22` → Ignition ON Motion  
- `67` → Señal RSRP 4G moderada  
- `1` → Alimentación externa conectada  
- `3` → Red LTE  
- `0.00` → Sin carga en batería de respaldo  
- `+0000` → Hora local igual a UTC  
- `0` → Sin horario de verano activado  

---

> 🧾 **Fuente:** *GV58LAU @Track Air Interface Protocol – Sección 4.3.1 INF (Device Information)* :contentReference[oaicite:0]{index=0}
