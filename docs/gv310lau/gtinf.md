# +RESP/+BUFF:GTINF — GV310LAU

> **Referencia oficial:** Sección 4.3.1 *INF (Device Information)* — *GV310LAU @Track Air Interface Protocol v0705*  
> **Mensaje:** +RESP:GTINF o +BUFF:GTINF  
> **Función:** Reporte informativo periódico del estado general del dispositivo.

---

## 🧭 Descripción general

El mensaje **GTINF** se envía cuando la función de reporte de información del dispositivo está habilitada mediante el comando **AT+GTCFG**.  
Este mensaje entrega información general sobre el estado del terminal, incluyendo voltajes, estado de alimentación, tipo de red, señal, antena GNSS, entradas/salidas digitales, hora del último *GNSS fix* y parámetros de zona horaria.

---

## 🧩 Estructura general

+RESP|+BUFF:GTINF,<ProtocolVersion>,<IMEI>,GV310LAU,<MotionStatus>,<ICCID>,<CSQ>,<BER>,<ExtPowerSupply>,<ExtPowerVoltage>,<NetworkType>,<BackupBattVolt>,<Charging>,<LEDState>,<PowerSavingMode>,<ExtGNSSAntenna>,<LastFixUTC>,,<PinMask>,<AIN1>,<AIN2>,<AIN3>,<DI>,<DO>,<TimeZoneOffset>,<DST>,<SendTime>,<CountHex>$


---

## 🧪 Ejemplo real

+RESP:GTINF,6E0C03,868589060720300,GV310LAU,22,89999202003110006092,51,0,1,26894,3,0.00,0,1,2,0,20251008152152,3,,0,,01,00,+0000,0,20251008152152,0BE0$


---

## 🧾 Descripción de campos

| Campo | Descripción | Tipo / Formato | Valores posibles |
|--------|--------------|----------------|------------------|
| **Header** | Prefijo del mensaje | Texto | +RESP o +BUFF |
| **Message Name** | Nombre del reporte | Texto | GTINF |
| **Leading Symbol** | Separador inicial | `,` | — |
| **ProtocolVersion** | Versión del protocolo implementado | HEX (6) | 000000–FFFFFF |
| **IMEI** | Identificador único del dispositivo | Numérico (15) | — |
| **DeviceName** | Nombre del modelo del equipo | Texto (<=20) | GV310LAU |
| **MotionStatus** | Estado actual de movimiento | Numérico (2) | 11, 12, 21, 22, 41, 42, 1A, 16 |
| **ICCID** | ICCID de la SIM | Numérico (20) | — |
| **CSQ (RSSI/RSRP)** | Intensidad de señal celular | Numérico | 0–31 / 99 (2G/3G), 0–97 / 255 (4G) |
| **BER** | Calidad de señal GSM | Numérico | 0–7 / 99 |
| **ExtPowerSupply** | Estado de la fuente externa | 1 dígito | 0 = Desconectada, 1 = Conectada |
| **ExtPowerVoltage** | Voltaje de la fuente externa (mV) | Numérico (<=5) | 0–32000 |
| **NetworkType** | Tipo de red móvil actual | Numérico (1) | 0 = Unregistered, 1 = EGPRS, 2 = WCDMA, 3 = LTE |
| **BackupBattVolt** | Voltaje de batería interna (V) | Decimal (4) | 0.00–4.50 |
| **Charging** | Estado de carga de batería interna | 1 dígito | 0 = No cargando, 1 = Cargando |
| **LEDState** | Estado de los LEDs del equipo | 1 dígito | 0 = Todos apagados, 1 = Alguno encendido |
| **PowerSavingMode** | Modo de ahorro de energía | Numérico | 0–2 |
| **ExtGNSSAntenna** | Estado de la antena GNSS externa | Numérico | 0 = OK, 1 = Open circuit, 3 = Desconocido |
| **LastFixUTC** | Hora UTC del último fix GNSS | YYYYMMDDHHMMSS | — |
| **PinMask** | Modo de trabajo actual del pin | HEX (1) | 0–F |
| **AIN1/AIN2/AIN3** | Voltajes de entrada analógica | Numérico (<=5) | F(0–100) o 0–16000 mV |
| **DI (Digital Input)** | Entradas digitales (bitwise) | HEX (<=4) | 0000–0F0F |
| **DO (Digital Output)** | Salidas digitales (bitwise) | HEX (<=4) | 0000–0F07 |
| **TimeZoneOffset** | Diferencia horaria local respecto a UTC | Texto (5) | +HHMM / -HHMM |
| **DST** | Estado de horario de verano | 1 dígito | 0 = Desactivado, 1 = Activado |
| **SendTime** | Hora UTC de envío del mensaje | YYYYMMDDHHMMSS | — |
| **CountHex** | Contador del mensaje | HEX (4) | 0000–FFFF |

---

## 🚗 Códigos de Motion Status

| Código | Descripción |
|--------|--------------|
| 16 | Tow — Vehículo con ignición OFF y siendo remolcado |
| 1A | Fake Tow — Ignición OFF, posible remolque |
| 11 | Ignition Off Rest — Ignición OFF y detenido |
| 12 | Ignition Off Motion — Ignición OFF, en movimiento antes de considerarse remolque |
| 21 | Ignition On Rest — Ignición ON y detenido |
| 22 | Ignition On Motion — Ignición ON y en movimiento |
| 41 | Sensor Rest — Sin señal de ignición, detenido |
| 42 | Sensor Motion — Sin señal de ignición, en movimiento |

---

## 📶 Niveles de señal (CSQ RSSI / RSRP)

| Tecnología | Valor | Intensidad (dBm) |
|-------------|--------|------------------|
| **2G/3G** | 0 | < -113 |
|  | 1 | -111 |
|  | 2–30 | -109 a -53 |
|  | 31 | > -51 |
|  | 99 | Desconocido |
| **4G (LTE)** | 0 | < -140 |
|  | 1 | -140 |
|  | 2–96 | -139 a -44 |
|  | 97 | >= -44 |
|  | 255 | Desconocido |

---

## ⚙️ Máscaras digitales (DI/DO)

### Entradas digitales (DI)
| Bit | Entrada | Descripción |
|------|----------|-------------|
| 0 | Ignition | Detección de ignición |
| 1 | DI1 | Entrada digital 1 |
| 2 | DI2 | Entrada digital 2 |
| 3 | DI3 | Entrada digital 3 |
| 9–11 | EIO100 (A–C) | Entradas extendidas |
| 15 | — | Reservado |

### Salidas digitales (DO)
| Bit | Salida | Descripción |
|------|----------|-------------|
| 0 | DO1 | Salida digital 1 |
| 1 | DO2 | Salida digital 2 |
| 2 | DO3 | Salida digital 3 |
| 9–11 | EIO100 (A–C) | Salidas extendidas |
| 15 | — | Reservado |

---

## 📝 Notas adicionales

- Los valores `ffff` en los campos `<LAC>` y `<Cell ID>` indican que el terminal desconoce esos valores.
- Este mensaje **no puede enviarse vía SMS**.
- Si no hay celdas vecinas detectadas, los campos correspondientes estarán vacíos.
- Los voltajes analógicos pueden mostrar `F(0–100)` si se configuran en modo porcentaje.
- La identificación del modelo en homologación se realiza por el prefijo del IMEI (`86858906`).

---

> 🧾 **Fuente:** *GV310LAU @Track Air Interface Protocol – Sección 4.3.1 INF (Device Information)*:contentReference[oaicite:0]{index=0}
