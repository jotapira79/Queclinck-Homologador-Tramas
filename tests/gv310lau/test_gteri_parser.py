import re
import pytest

# Intentamos importar la función del proyecto. Ajusta estos imports si tu repo usa otra ruta.
try:
    from queclink.gteri import parse_gteri  # estilo paquete
except Exception:
    try:
        from src.gteri_parser import parse_gteri  # estilo src/
    except Exception:
        try:
            import importlib.util
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[2]
            module_path = repo_root / "queclink_tramas.py"
            spec = importlib.util.spec_from_file_location("queclink_tramas", module_path)
            if not spec or not spec.loader:  # pragma: no cover - carga alternativa
                raise ImportError("No se pudo cargar queclink_tramas.py")
            _module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_module)

            def _to_iso(ts: str) -> str:
                if not ts:
                    return ts
                from datetime import datetime

                for fmt in ("%Y%m%d%H%M%S",):
                    try:
                        return datetime.strptime(ts, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        continue
                return ts

            def _wrapper(raw: str):
                base = _module.parse_line_to_record(raw)  # type: ignore[attr-defined]
                if not base:
                    return {}
                data = dict(base)
                data["header"] = data.get("prefix")
                data["device"] = data.get("model") or data.get("device_name")
                data["utc"] = _to_iso(data.get("gnss_utc", "")) if data.get("gnss_utc") else data.get("gnss_utc")
                data["send_time"] = _to_iso(data.get("send_time", "")) if data.get("send_time") else data.get("send_time")
                data["sats"] = data.get("satellites")
                dop_candidate = data.get("dop1")
                if dop_candidate is None:
                    for key in ("dop2", "dop3"):
                        val = data.get(key)
                        if val is not None:
                            dop_candidate = val
                            break
                if dop_candidate is not None:
                    data["hdop"] = dop_candidate
                if isinstance(data.get("device_status"), str):
                    data["device_status"] = data["device_status"].upper()
                mask_lower = str(data.get("pos_append_mask", "")).lower()
                if mask_lower in {"00", "0"}:
                    data.setdefault("gnss_fix", False)
                    data.setdefault("is_last_fix", True)
                return data

            parse_gteri = _wrapper
        except Exception:
            from queclink_gteri_parser import parse_gteri  # último recurso


# Ejemplo real (del PDF) con varios opcionales activos
RAW_OK = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000100,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,42,11172,100,210000,0,1,0,06,12,0,001A42A2,0617,TMPS,"
    "08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)

# Variante con HDOP=0 (sin fix GNSS) y sin opcionales de posición (mask=00)
RAW_HDOP0 = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000000,,10,1,1,12.3,90,200.5,"
    "-70.123456,-33.456789,20250101010101,0730,0001,ABCD,00112233,00,"
    "0000000:00:10,0,0,0,80,210000,0,0,20250101010102,0001$"
)

RAW_ANALOG_PLACEHOLDERS = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000100,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,,,,100,220100,0,0,06,12,0,001A42A2,0617,TMPS,"
    "08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)

RAW_PDOP_ONLY = (
    "+RESP:GTERI,6E0C03,868589060796441,GV310LAU,00000000,14095,54,1,1,83.4,61,1120.9,"
    "-69.777507,-23.288856,20251013124747,0730,0002,00C9,08000620,09,12,,,0.88,,123.45,0000123:45:00,"
    "111,222,333,90,220100,0,20251013124750,0001$"
)

RAW_UART_DUP_ZERO = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000100,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,,,,100,220100,0,0,06,12,0,001A42A2,0617,TMPS,"
    "08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)

RAW_WITH_DIGITAL_FUEL = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000101,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,42,11172,100,210000,0,FUEL123,LEVEL80,1,0,06,12,0,001A42A2,"
    "0617,TMPS,08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)

RAW_ANALOG_NORMALIZED = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000100,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,F50,8000,F75,100,210000,0,1,0,06,12,0,001A42A2,0617,TMPS,"
    "08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)

RAW_WITH_WARNINGS = (
    "+RESP:GTERI,6E1203,864696060004173,GV310LAU,00000101,,10,1,1,0.0,0,115.8,"
    "117.129356,31.839248,20230808061540,0460,0001,DF5C,05FE6667,03,15,,4.0,"
    "0000102:34:33,14549,20000,-10,35000,130,0000000000-0F0FFFFFFF,3,FUELX,DATA,06,12,0,001A42A2,"
    "0617,TMPS,08351B00043C,1,26,65,20231030085704,20231030085704,0017$"
)


def test_parse_gteri_campos_basicos():
    d = parse_gteri(RAW_OK)
    assert isinstance(d, dict)

    # Campos de cabecera
    assert d.get("header") == "+RESP:GTERI"
    assert d.get("imei") == "864696060004173"
    assert d.get("device") == "GV310LAU"

    # Coordenadas y tiempo
    assert pytest.approx(d.get("longitude_deg"), rel=1e-6) == 117.129356
    assert pytest.approx(d.get("latitude_deg"), rel=1e-6) == 31.839248
    # UTC normalizado (ISO‑8601). Si tu implementación usa clave distinta, ajusta aquí.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", d.get("utc", ""))

    # Máscaras y opcionales
    mask = str(d.get("position_append_mask") or d.get("pos_append_mask") or "").lower()
    assert mask in {"03", "3"}
    assert d.get("sats_in_use") == 15
    # HDOP detectado y normalizado
    assert float(d.get("hdop") or 0) == pytest.approx(4.0)

    # Odómetro y horómetro
    assert isinstance(d.get("mileage_km"), (int, float))
    assert re.match(r"^[0-9]{7}:[0-9]{2}:[0-9]{2}$", d.get("hour_meter", ""))

    # Envío y contador
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", d.get("send_time", ""))
    assert re.match(r"^[0-9A-Fa-f]{4}$", d.get("count_hex", ""))

    # Bloques ERI normalizados
    ble = d.get("ble_block") or {}
    assert ble.get("accessory_number") == 1
    assert ble.get("items") and isinstance(ble["items"], list)


def test_semantica_hdop_sin_fix():
    d = parse_gteri(RAW_HDOP0)

    # Mask 00 => no deberían venir campos anexos de posición (sats/hdop/vdop/pdop)
    assert str(d.get("position_append_mask") or d.get("pos_append_mask") or "").lower() in {"00", "0"}
    assert d.get("sats_in_use") in (None, 0)

    # HDOP = 0 => sin fix GNSS (banderas esperadas)
    # La especificación sugiere exponer esto; si usas otra clave, ajusta aquí.
    assert d.get("gnss_fix") is False or d.get("is_last_fix") is True


@pytest.mark.parametrize(
    "raw, must_keys",
    [
        (RAW_OK, [
            "imei", "device", "longitude_deg", "latitude_deg", "gnss_utc_time", "mcc", "mnc", "lac", "cell_id",
            "mileage_km", "hour_meter", "send_time", "count_hex"
        ]),
        (RAW_HDOP0, [
            "imei", "device", "longitude_deg", "latitude_deg", "gnss_utc_time", "mcc", "mnc", "lac", "cell_id",
            "mileage_km", "hour_meter", "send_time", "count_hex"
        ]),
    ],
)
def test_claves_minimas_presentes(raw, must_keys):
    d = parse_gteri(raw)
    for k in must_keys:
        assert k in d, f"Falta clave requerida: {k}"


def test_rangos_basicos():
    d = parse_gteri(RAW_OK)
    assert -90 <= d.get("latitude_deg") <= 90
    assert -180 <= d.get("longitude_deg") <= 180
    assert d.get("backup_battery_pct") == d.get("backup_batt_pct") == 100


def test_valida_hour_meter_formato():
    d = parse_gteri(RAW_OK)
    hm = d.get("hour_meter", "")
    assert re.match(r"^[0-9]{7}:[0-9]{2}:[0-9]{2}$", hm)


def test_campos_post_dop_no_se_desplazan():
    d = parse_gteri(RAW_OK)

    assert d.get("mileage_km") == pytest.approx(14549.0)
    assert d.get("hour_meter") == "0000102:34:33"
    assert d.get("analog_in_1") == 42
    assert d.get("analog_in_1_raw") == "42"
    assert d.get("analog_in_1_mv") == 42
    assert d.get("analog_in_2") == 11172
    assert d.get("analog_in_2_raw") == "11172"
    assert d.get("analog_in_2_mv") == 11172
    assert d.get("analog_in_3") is None
    assert d.get("analog_in_3_raw") in (None, "")
    assert str(d.get("device_status", "")).upper() == "210000"
    assert d.get("uart_device_type_label") == "unknown"


def test_placeholders_no_bloquean_campos_posteriores():
    d = parse_gteri(RAW_ANALOG_PLACEHOLDERS)

    assert d.get("analog_in_1") is None
    assert d.get("analog_in_2") is None
    assert d.get("analog_in_3") is None
    assert d.get("analog_in_1_raw") is None
    assert d.get("analog_in_2_raw") is None
    assert d.get("analog_in_3_raw") is None
    assert d.get("backup_battery_pct") == 100
    assert d.get("device_status") == "220100"
    assert d.get("uart_device_type") == 0
    assert d.get("uart_device_type_label") == "unknown"


def test_pdop_only_mask_consumes_placeholders():
    d = parse_gteri(RAW_PDOP_ONLY)

    assert d.get("sats_in_use") == 12
    assert d.get("pdop") == pytest.approx(0.88)
    assert d.get("hour_meter") == "0000123:45:00"
    assert d.get("mileage_km") == pytest.approx(123.45)
    assert d.get("analog_in_1") == 111
    assert d.get("device_status") == "220100"


def test_uart_device_type_dup_zero():
    d = parse_gteri(RAW_UART_DUP_ZERO)

    assert isinstance(d.get("uart_device_type"), int)
    assert d.get("uart_device_type_label") == "unknown"


def test_digital_fuel_sensor_data_consumed():
    d = parse_gteri(RAW_WITH_DIGITAL_FUEL)

    assert d.get("uart_device_type") == 0
    assert d.get("digital_fuel_sensor_data") == "FUEL123|LEVEL80"
    assert "dfs_raw_list" not in d
    assert "dfs_count" not in d


def test_analog_f_normalization():
    d = parse_gteri(RAW_ANALOG_NORMALIZED)

    assert d.get("analog_in_1") == 8000
    assert d.get("analog_in_2") == 8000
    assert d.get("analog_in_3") == 22500
    assert d.get("analog_in_1_mv") == 8000
    assert d.get("analog_in_1_pct") == pytest.approx(50.0)
    assert d.get("analog_in_2_pct") == pytest.approx(50.0)
    assert d.get("analog_in_3_pct") == pytest.approx(75.0)
    warnings = set(d.get("validation_warnings") or [])
    assert "validation_warning" not in warnings


def test_warn_when_values_outside_range():
    d = parse_gteri(RAW_WITH_WARNINGS)

    assert d.get("analog_in_1") == 16000
    assert d.get("analog_in_2") == 0
    assert d.get("analog_in_3") == 30000
    assert d.get("device_status") == "0000000000-0F0FFFFFFF"
    assert d.get("uart_device_type") == 3
    assert d.get("digital_fuel_sensor_data") == "FUELX|DATA"
    assert d.get("backup_battery_pct") == 100
    assert d.get("backup_battery_pct_raw") == 130.0
    assert d.get("device_status_len_bits") == 80
    assert d.get("device_status_hi") == "0000000000"
    assert d.get("device_status_lo") == "0F0FFFFFFF"
    assert d.get("uart_device_type_label") == "invalid"
    items = d.get("digital_fuel_sensor_data_items") or []
    assert items[:2] == ["FUELX", "DATA"]
    warnings = set(d.get("validation_warnings") or [])
    assert "analog_in_1_mv_clamped" in warnings
    assert "analog_in_2_mv_clamped" in warnings
    assert "analog_in_3_mv_clamped" in warnings
    assert "backup_battery_pct_clamped" in warnings
    assert "uart_device_type_invalid" in warnings
