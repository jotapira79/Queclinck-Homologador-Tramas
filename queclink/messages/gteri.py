"""Parser para mensajes GTERI."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..parser import _common_enrich, _split, _to_iso
from ..specs.loader import get_spec_path

_GTERI_PREFIXES = ("+RESP:GTERI", "+BUFF:GTERI")


def _extract_payload(line: str) -> Optional[str]:
    if not line:
        return None
    matches = [line.find(prefix) for prefix in _GTERI_PREFIXES]
    matches = [idx for idx in matches if idx != -1]
    if not matches:
        return None
    start = min(matches)
    return line[start:]


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value: Any, base: int = 10) -> Optional[int]:
    try:
        if isinstance(value, str) and base == 16:
            value = value.lower().replace("0x", "")
        return int(value, base)
    except Exception:
        return None


def _is_hour_meter(candidate: Optional[str]) -> bool:
    return bool(re.fullmatch(r"\d{1,7}:\d{2}:\d{2}", (candidate or "").strip()))


@dataclass
class _CommonERI:
    prefix: str
    message: str
    is_buff: int
    full_protocol_version: str
    imei: str
    device_name: str
    eri_mask: Optional[str]
    external_power_mv: Optional[int]
    report_type: Optional[str]
    number: Optional[int]
    gnss_accuracy_level: Optional[float]
    speed_kmh: Optional[float]
    azimuth_deg: Optional[int]
    altitude_m: Optional[float]
    longitude_deg: Optional[float]
    latitude_deg: Optional[float]
    gnss_utc_time: Optional[str]
    mcc: Optional[str]
    mnc: Optional[str]
    lac: Optional[str]
    cell_id: Optional[str]
    position_append_mask: Optional[str]
    raw_after_mask: str
    send_time: Optional[str]
    count_hex: Optional[str]


def _parse_common_prefix(fields: List[str]) -> Tuple[_CommonERI, int]:
    prefix = fields[0].strip()
    message = "GTERI"
    is_buff = 1 if prefix.startswith("+BUFF") else 0

    def get(idx: int) -> Optional[str]:
        if idx >= len(fields):
            return None
        value = fields[idx]
        if value == "":
            return None
        return value.strip()

    ce = _CommonERI(
        prefix=prefix,
        message=message,
        is_buff=is_buff,
        full_protocol_version=get(1) or "",
        imei=get(2) or "",
        device_name=(get(3) or "").upper(),
        eri_mask=get(4),
        external_power_mv=_safe_int(get(5)) if get(5) else None,
        report_type=get(6),
        number=_safe_int(get(7)) if get(7) else None,
        gnss_accuracy_level=_safe_float(get(8)) if get(8) else None,
        speed_kmh=_safe_float(get(9)) if get(9) else None,
        azimuth_deg=_safe_int(get(10)) if get(10) else None,
        altitude_m=_safe_float(get(11)) if get(11) else None,
        longitude_deg=_safe_float(get(12)) if get(12) else None,
        latitude_deg=_safe_float(get(13)) if get(13) else None,
        gnss_utc_time=get(14),
        mcc=get(15),
        mnc=get(16),
        lac=get(17),
        cell_id=get(18),
        position_append_mask=get(19),
        raw_after_mask="",
        send_time=None,
        count_hex=None,
    )
    return ce, 20


def _extract_tail(fields: List[str]) -> tuple[Optional[str], Optional[str]]:
    if len(fields) < 2:
        return None, None
    send_time = fields[-2].strip() if fields[-2] else None
    count_hex = fields[-1].strip() if fields[-1] else None
    if count_hex and count_hex.endswith("$"):
        count_hex = count_hex[:-1]
    return send_time, count_hex


def _mask_value(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    try:
        return int(raw, 16)
    except ValueError:
        try:
            return int(raw)
        except ValueError:
            return None


def _ble_append_fields(mask_raw: Optional[str], tokens: Iterable[Optional[str]]) -> Tuple[Dict[str, Any], int]:
    """Parsear campos opcionales de un accesorio BLE según la append mask."""

    mask_value = _mask_value(mask_raw) or 0
    values_iter = iter(tokens)
    consumed = 0
    optional_fields: Dict[str, Any] = {}
    known_names: Dict[int, str] = {
        0: "name",
        1: "mac",
        2: "status",
        3: "battery_mv",
        4: "temp_c",
        5: "humidity_pct",
        6: "reserved",
        7: "accessory_io",
        8: "event",
        9: "tire_pressure_kpa",
        10: "timestamp",
        11: "enhanced_temp_c",
        12: "magnet_data",
        13: "battery_pct",
        14: "relay_state",
    }

    bit_values: List[Dict[str, Any]] = []
    for bit in range(32):
        if mask_value & (1 << bit):
            raw_value = next(values_iter, None)
            consumed += 1 if raw_value is not None else 0
            key = known_names.get(bit, f"bit_{bit}")
            value = raw_value.strip() if isinstance(raw_value, str) else raw_value
            optional_fields[key] = value
            bit_values.append({"bit": bit, "key": key, "value": value})

    if bit_values:
        optional_fields["_raw_fields"] = bit_values

    return optional_fields, consumed


def _parse_ble_block(tokens: List[Optional[str]], cursor: int) -> Tuple[Optional[Dict[str, Any]], int]:
    if cursor >= len(tokens):
        return None, cursor

    accessory_number = _safe_int(tokens[cursor])
    cursor += 1
    if accessory_number is None or accessory_number < 0:
        return None, cursor

    items: List[Dict[str, Any]] = []
    for _ in range(accessory_number):
        if cursor >= len(tokens):
            break
        index = (tokens[cursor] or "").strip()
        cursor += 1
        if cursor >= len(tokens):
            break
        accessory_type = _safe_int(tokens[cursor])
        cursor += 1
        if cursor >= len(tokens):
            break
        model_or_beacon = _safe_int(tokens[cursor])
        cursor += 1
        raw_data = tokens[cursor] if cursor < len(tokens) else None
        cursor += 1
        append_mask = tokens[cursor] if cursor < len(tokens) else None
        cursor += 1

        item: Dict[str, Any] = {
            "index": index,
            "accessory_type": accessory_type,
            "model_or_beacon_id_model": model_or_beacon,
            "raw_data": raw_data.strip() if isinstance(raw_data, str) else raw_data,
            "append_mask": append_mask.strip() if isinstance(append_mask, str) else append_mask,
        }

        remaining = tokens[cursor:]
        optional, consumed = _ble_append_fields(append_mask, remaining)
        if optional:
            item.update(optional)
        cursor += consumed
        items.append(item)

    return {"accessory_number": accessory_number, "items": items}, cursor


def _parse_rf433_block(tokens: List[Optional[str]], cursor: int) -> Tuple[Optional[Dict[str, Any]], int]:
    if cursor >= len(tokens):
        return None, cursor

    accessory_number = _safe_int(tokens[cursor])
    cursor += 1
    if accessory_number is None or accessory_number < 0:
        return None, cursor

    accessories: List[Dict[str, Any]] = []
    for _ in range(accessory_number):
        if cursor >= len(tokens):
            break
        serial = (tokens[cursor] or "").strip()
        cursor += 1
        if cursor >= len(tokens):
            break
        acc_type = _safe_int(tokens[cursor])
        cursor += 1
        temperature = _safe_int(tokens[cursor]) if cursor < len(tokens) else None
        cursor += 1 if cursor < len(tokens) else 0
        humidity: Optional[int] = None
        if acc_type == 2 and cursor < len(tokens):
            humidity = _safe_int(tokens[cursor])
            cursor += 1
        accessories.append(
            {
                "serial": serial or None,
                "type": acc_type,
                "temperature_c": temperature,
                "humidity_pct": humidity,
            }
        )

    return {"accessory_number": accessory_number, "accessories": accessories}, cursor


def _parse_model_specific(device: str, fields: List[str], start_idx: int) -> Dict[str, Any]:
    normalized = (device or "").strip().upper()
    if normalized == "GV58LAU":
        return _parse_model_specific_gv58(fields, start_idx)
    return _parse_model_specific_default(fields, start_idx)


def _parse_model_specific_default(fields: List[str], start_idx: int) -> Dict[str, Any]:
    remaining = fields[start_idx:-2] if len(fields) >= (start_idx + 2) else fields[start_idx:]
    out: Dict[str, Any] = {}

    mask_value = _mask_value(fields[start_idx - 1] if start_idx - 1 < len(fields) else None)
    eri_mask_value = _mask_value(fields[4] if len(fields) > 4 else None)

    def mask_has(bit: int) -> bool:
        return mask_value is not None and (mask_value & bit) != 0

    cursor = 0
    if cursor < len(remaining):
        raw_sat = remaining[cursor]
        if mask_has(0x01):
            out["sats_in_use"] = _safe_int(raw_sat) if (raw_sat or "") != "" else None
            cursor += 1
        elif (raw_sat or "") != "" and re.fullmatch(r"\d{1,2}", raw_sat or ""):
            out["sats_in_use"] = _safe_int(raw_sat)
            cursor += 1

    dop_keys = ["hdop", "vdop", "pdop"]
    dop_values: List[Optional[float]] = []
    dop_pattern = r"\d{1,2}(?:\.\d{1,2})?"
    for idx in range(3):
        if cursor >= len(remaining):
            break
        value = remaining[cursor]
        expected = mask_has(0x02 << idx)
        if (value or "") == "":
            if expected:
                dop_values.append(None)
                cursor += 1
                continue
            break
        if re.fullmatch(dop_pattern, value or ""):
            dop_values.append(_safe_float(value))
            cursor += 1
            continue
        if expected:
            dop_values.append(None)
            cursor += 1
            continue
        break

    for idx, value in enumerate(dop_values):
        if idx < len(dop_keys):
            out[dop_keys[idx]] = value
    else:
        if cursor < len(remaining) and re.fullmatch(r"\d", remaining[cursor] or ""):
            out["gnss_trigger_type"] = _safe_int(remaining[cursor])
            cursor += 1
        if cursor < len(remaining) and re.fullmatch(r"\d", remaining[cursor] or ""):
            out["gnss_jamming_state"] = _safe_int(remaining[cursor])
            cursor += 1

    mileage_set = False
    hour_set = False

    if cursor < len(remaining) and _is_hour_meter(remaining[cursor]):
        out["hour_meter"] = remaining[cursor]
        cursor += 1
        hour_set = True
    if cursor < len(remaining) and re.fullmatch(r"-?\d+(?:\.\d+)?", remaining[cursor] or ""):
        out["mileage_km"] = _safe_float(remaining[cursor])
        cursor += 1
        mileage_set = True
    if not hour_set and cursor < len(remaining) and _is_hour_meter(remaining[cursor]):
        out["hour_meter"] = remaining[cursor]
        cursor += 1
        hour_set = True
    if not mileage_set and cursor < len(remaining) and re.fullmatch(r"-?\d+(?:\.\d+)?", remaining[cursor] or ""):
        out["mileage_km"] = _safe_float(remaining[cursor])
        cursor += 1
        mileage_set = True

    def skip_empty_values() -> None:
        nonlocal cursor
        while cursor < len(remaining) and (remaining[cursor] or "") == "":
            cursor += 1

    analog_pattern = r"-?\d+(?:\.\d+)?|F\d{1,3}"

    def add_warning(code: str) -> None:
        warnings = out.setdefault("validation_warnings", [])
        if code not in warnings:
            warnings.append(code)

    def parse_analog_value(raw_value: Optional[str], index: int) -> None:
        key = f"analog_in_{index}"
        raw_key = f"{key}_raw"
        mv_key = f"{key}_mv"
        pct_key = f"{key}_pct"
        out[key] = None
        out[raw_key] = None
        out[mv_key] = None
        out[pct_key] = None
        if raw_value is None or (raw_value or "") == "":
            return
        value = (raw_value or "").strip()
        out[raw_key] = value
        if not re.fullmatch(analog_pattern, value or ""):
            add_warning(f"{key}_invalid")
            return
        max_mv = 30000 if index == 3 else 16000
        mv_value: Optional[int] = None
        pct_value: Optional[float] = None
        if value.upper().startswith("F"):
            pct_raw = _safe_int(value[1:]) if len(value) > 1 else None
            if pct_raw is None:
                add_warning(f"{key}_invalid")
                return
            pct_clamped = max(0, min(100, pct_raw))
            if pct_clamped != pct_raw:
                add_warning(f"{key}_pct_clamped")
            pct_value = float(pct_clamped)
            mv_value = int(round(max_mv * (pct_value / 100.0)))
        else:
            numeric = _safe_float(value)
            if numeric is None:
                add_warning(f"{key}_invalid")
                return
            mv_candidate = int(round(numeric))
            mv_clamped = max(0, min(max_mv, mv_candidate))
            if mv_clamped != mv_candidate:
                add_warning(f"{key}_mv_clamped")
            mv_value = mv_clamped
            pct_value = round((mv_value / max_mv) * 100.0, 2) if max_mv > 0 else None
        out[key] = mv_value
        out[mv_key] = mv_value
        out[pct_key] = pct_value

    for idx in range(1, 4):
        if cursor >= len(remaining):
            break
        value = remaining[cursor]
        if idx == 3:
            next_val = remaining[cursor + 1] if cursor + 1 < len(remaining) else None
            next_next = remaining[cursor + 2] if cursor + 2 < len(remaining) else None
            if (
                re.fullmatch(r"\d{1,3}", (value or ""))
                and next_val
                and re.fullmatch(r"[0-9A-Fa-f]{6,10}", next_val or "")
                and (next_next is None or re.fullmatch(r"\d{1,2}", next_next or ""))
            ):
                parse_analog_value(None, idx)
                break
        parse_analog_value(value, idx)
        cursor += 1

    skip_empty_values()
    if cursor < len(remaining) and re.fullmatch(r"-?\d+(?:\.\d+)?", remaining[cursor] or ""):
        raw_val = _safe_float(remaining[cursor])
        if raw_val is not None:
            raw_int = int(round(raw_val))
            clamped = max(0, min(100, raw_int))
            out["backup_battery_pct_raw"] = raw_val
            if clamped != raw_int:
                add_warning("backup_battery_pct_clamped")
            out["backup_battery_pct"] = clamped
            cursor += 1

    skip_empty_values()
    if cursor < len(remaining):
        candidate = remaining[cursor] or ""
        upper_candidate = candidate.upper()
        device_status_parsed = False
        if re.fullmatch(r"[0-9A-F]{6}|[0-9A-F]{10}", upper_candidate):
            device_status_parsed = True
            bit_len = 24 if len(upper_candidate) == 6 else 40
            out["device_status"] = upper_candidate
            out["device_status_raw"] = candidate
            out["device_status_len_bits"] = bit_len
        elif re.fullmatch(r"[0-9A-F]{10}-[0-9A-F]{10}", upper_candidate):
            device_status_parsed = True
            hi, lo = upper_candidate.split("-")
            out["device_status"] = upper_candidate
            out["device_status_raw"] = candidate
            out["device_status_len_bits"] = 80
            out["device_status_hi"] = hi
            out["device_status_lo"] = lo
        if device_status_parsed:
            cursor += 1
        elif candidate:
            out["device_status_raw"] = candidate
            add_warning("device_status_invalid")
            cursor += 1

    skip_empty_values()
    if cursor < len(remaining) and re.fullmatch(r"\d{1,2}", remaining[cursor] or ""):
        parsed_uart = _safe_int(remaining[cursor])
        if parsed_uart is not None:
            out["uart_device_type"] = parsed_uart
            label_map = {0: "unknown", 1: "type_1", 7: "type_7"}
            out["uart_device_type_label"] = label_map.get(parsed_uart, "invalid")
            if parsed_uart not in label_map:
                add_warning("uart_device_type_invalid")
        cursor += 1

    skip_empty_values()
    if eri_mask_value is not None and cursor < len(remaining):
        dfs_items: List[str] = []
        if (eri_mask_value & 0x01) != 0:
            while cursor < len(remaining):
                token = remaining[cursor]
                if token is None or token.strip() == "":
                    break
                upper = token.strip().upper()
                if upper in {"TMPS", "RF433", "RF433B", "BLE", "CAN", "1WIRE"}:
                    break
                token_str = token.strip()
                if dfs_items:
                    if token_str.isdigit() and len(token_str) <= 2:
                        break
                    if re.fullmatch(r"\d{4,}", token_str):
                        break
                    if re.fullmatch(r"[0-9A-F]{8,}", upper):
                        break
                dfs_items.append(token)
                cursor += 1
            if dfs_items:
                out["digital_fuel_sensor_data"] = (
                    dfs_items[0] if len(dfs_items) == 1 else "|".join(dfs_items)
                )
                out["digital_fuel_sensor_data_items"] = dfs_items

        skip_empty_values()

    rf433_block: Optional[Dict[str, Any]] = None
    if cursor < len(remaining):
        peek = (remaining[cursor] or "").strip().upper()
        if peek in {"RF433", "RF433B"}:
            cursor += 1
            rf433_block, cursor = _parse_rf433_block(remaining, cursor)
            skip_empty_values()

    ble_block: Optional[Dict[str, Any]] = None
    if cursor < len(remaining):
        peek = (remaining[cursor] or "").strip().upper()
        if peek == "BLE":
            cursor += 1
        ble_block, cursor = _parse_ble_block(remaining, cursor)
        skip_empty_values()

    if rf433_block:
        out["rf433_block"] = rf433_block
    if ble_block:
        out["ble_block"] = ble_block
        out["ble_count"] = ble_block.get("accessory_number")

    skip_empty_values()
    if cursor < len(remaining):
        rat_raw = remaining[cursor]
        rat_value = _safe_int(rat_raw)
        if rat_value is not None:
            cursor += 1
            band_raw = remaining[cursor] if cursor < len(remaining) else None
            band_value = band_raw if band_raw not in (None, "") else None
            if band_raw is not None:
                cursor += 1
            out["rat_band"] = {"rat": rat_value, "band": band_value}
            out["rat"] = rat_value
            if band_value is not None:
                out["band"] = band_value

    out["remaining_blob"] = ",".join(value or "" for value in remaining[cursor:])
    return out


def _parse_model_specific_gv58(fields: List[str], start_idx: int) -> Dict[str, Any]:
    remaining = fields[start_idx:-2] if len(fields) >= (start_idx + 2) else fields[start_idx:]
    out: Dict[str, Any] = {}

    mask_value = _mask_value(fields[start_idx - 1] if start_idx - 1 < len(fields) else None)
    eri_mask_value = _mask_value(fields[4] if len(fields) > 4 else None)

    cursor = 0

    def skip_empty_values() -> None:
        nonlocal cursor
        while cursor < len(remaining) and (remaining[cursor] or "") == "":
            cursor += 1

    def peek(offset: int = 0) -> Optional[str]:
        idx = cursor + offset
        if idx >= len(remaining):
            return None
        return remaining[idx]

    def advance() -> Optional[str]:
        nonlocal cursor
        value = peek()
        cursor += 1
        return value

    # Satélites y DOPs
    skip_empty_values()
    sat_token = peek()
    if sat_token not in (None, ""):
        out["sats_in_use"] = _safe_int(sat_token)
    if sat_token is not None:
        advance()

    dop_keys = ["hdop", "vdop", "pdop"]
    for key in dop_keys:
        if cursor >= len(remaining):
            break
        token = peek()
        if token in (None, ""):
            advance()
            continue
        value = _safe_float(token)
        if value is not None:
            out[key] = value
        advance()

    # Permitir trigger/jamming opcional si llega intercalado
    if cursor < len(remaining):
        candidate = peek()
        if candidate and re.fullmatch(r"\d{1,2}", candidate):
            out["gnss_trigger_type"] = _safe_int(candidate)
            advance()

    # Odómetro y horómetro
    skip_empty_values()
    mileage_token = peek()
    if mileage_token not in (None, ""):
        mileage_val = _safe_float(mileage_token)
        if mileage_val is not None:
            out["mileage_km"] = mileage_val
    if mileage_token is not None:
        advance()

    skip_empty_values()
    hour_token = peek()
    if _is_hour_meter(hour_token):
        out["hour_meter"] = hour_token
        advance()

    # Batería de respaldo (puede venir vacía)
    backup_token = peek()
    if backup_token is not None:
        advance()
    backup_value = _safe_float(backup_token) if backup_token not in (None, "") else None
    if backup_value is not None:
        backup_int = int(round(backup_value))
        out["backup_battery_pct_raw"] = backup_value
        out["backup_battery_pct"] = backup_int
        out["backup_batt_pct"] = backup_int

    # Device status y reservados
    skip_empty_values()
    status_token = peek()
    if status_token not in (None, ""):
        normalized_status = status_token.strip().upper()
        out["device_status_raw"] = status_token.strip()
        out["device_status"] = normalized_status
        advance()

    if cursor < len(remaining):
        res1 = advance()
        out["reserved_1"] = res1 or None

    if cursor < len(remaining):
        res2 = advance()
        out["reserved_2"] = res2 or None

    skip_empty_values()

    def looks_like_ble_start(idx: int) -> bool:
        if idx >= len(remaining):
            return False
        count = _safe_int(remaining[idx])
        if count is None or count < 0:
            return False
        minimal = idx + 1 + count * 5
        return len(remaining) >= minimal

    if not looks_like_ble_start(cursor):
        res3 = peek()
        if res3 is not None:
            out["reserved_3"] = res3 or None
            advance()
        skip_empty_values()
    else:
        out.setdefault("reserved_3", None)

    if eri_mask_value is not None and (eri_mask_value & 0x04):
        if cursor < len(remaining) and not looks_like_ble_start(cursor):
            can_token = advance()
            if can_token not in (None, ""):
                out["can_data"] = can_token
        skip_empty_values()

    ble_block: Optional[Dict[str, Any]] = None
    ble_start = cursor
    if looks_like_ble_start(cursor):
        ble_block, cursor = _parse_ble_block(remaining, cursor)
    if ble_block:
        out["ble_block"] = ble_block
        out["ble_count"] = ble_block.get("accessory_number")
    else:
        cursor = ble_start

    skip_empty_values()
    rat_token = peek()
    if rat_token not in (None, ""):
        rat_val = _safe_int(rat_token)
        if rat_val is not None:
            advance()
            band_token = peek()
            band_val: Optional[str] = None
            if band_token not in (None, ""):
                band_val = band_token
                advance()
            out["rat_band"] = {"rat": rat_val, "band": band_val}
            out["rat"] = rat_val
            if band_val is not None:
                out["band"] = band_val

    out["remaining_blob"] = ",".join(value or "" for value in remaining[cursor:])
    return out


def _parse_line_to_record(line: str) -> Optional[Dict[str, Any]]:
    payload = _extract_payload(line)
    if payload is None:
        return None
    fields = _split(payload)
    if len(fields) < 22:
        return None
    ce, nxt = _parse_common_prefix(fields)
    send_time, count_hex = _extract_tail(fields)
    ce.send_time, ce.count_hex = send_time, count_hex
    model_data = _parse_model_specific(ce.device_name, fields, nxt)
    ce.raw_after_mask = model_data.pop("remaining_blob", "")
    base = asdict(ce)
    base.update(model_data)
    base["version"] = base.pop("full_protocol_version")
    base["count_dec"] = _safe_int(base.get("count_hex"), 16) if base.get("count_hex") else None
    base["model"] = ce.device_name
    warnings = base.get("validation_warnings")
    if warnings:
        if not isinstance(warnings, list):
            warnings = [warnings]
        base["validation_warnings"] = warnings
    elif warnings is None:
        base.pop("validation_warnings", None)
    else:
        base["validation_warnings"] = []

    for key in {
        "remaining_blob",
        "lat_lon_valid",
        "validation_warning",
        "validation_warnings_json",
    }:
        base.pop(key, None)
    return base


def parse_gteri(line: str, source: str = "RESP", device: Optional[str] = None) -> Dict[str, Any]:
    """Parsear un mensaje +RESP/+BUFF:GTERI."""
    base = _parse_line_to_record(line)
    if not base:
        return {}

    data = dict(base)
    header = data.get("prefix")
    data["header"] = header
    data.setdefault("message", "GTERI")

    detected_source: Optional[str] = None
    if isinstance(header, str):
        if header.startswith("+RESP:"):
            detected_source = "RESP"
        elif header.startswith("+BUFF:"):
            detected_source = "BUFF"

    normalized_device: Optional[str] = None
    if device:
        normalized_device = str(device).strip().upper()
        if normalized_device:
            data["model"] = normalized_device

    device_from_record = normalized_device or data.get("model") or data.get("device_name")
    if device_from_record:
        data["device"] = str(device_from_record).upper()

    if data.get("gnss_utc_time"):
        data["gnss_utc"] = data["gnss_utc_time"]
        data["utc"] = _to_iso(data["gnss_utc_time"]) or data["gnss_utc_time"]

    send_time_raw = data.get("send_time")
    if send_time_raw:
        data["send_time_raw"] = send_time_raw
        data["send_time"] = _to_iso(send_time_raw) or send_time_raw

    data["sats"] = data.get("sats_in_use")
    data.setdefault("pos_append_mask", data.get("position_append_mask"))
    data.setdefault("gnss_acc", data.get("gnss_accuracy_level"))
    data.setdefault("lon", data.get("longitude_deg"))
    data.setdefault("lat", data.get("latitude_deg"))
    data.setdefault("backup_batt_pct", data.get("backup_battery_pct"))
    data.setdefault("ext_power_mv", data.get("external_power_mv"))
    if "ble_count" not in data:
        block = data.get("ble_block")
        if isinstance(block, dict):
            data["ble_count"] = block.get("accessory_number")
    if data.get("hdop") is None:
        for candidate_key in ("vdop", "pdop"):
            value = data.get(candidate_key)
            if value is not None:
                data["hdop"] = value
                break
    if data.get("hdop") is not None:
        data.setdefault("dop1", data.get("hdop"))
    if data.get("vdop") is not None:
        data.setdefault("dop2", data.get("vdop"))
    if data.get("pdop") is not None:
        data.setdefault("dop3", data.get("pdop"))

    if isinstance(data.get("device_status"), str):
        data["device_status"] = data["device_status"].upper()

    mask_lower = str(data.get("position_append_mask", "") or data.get("pos_append_mask", "")).lower()
    if mask_lower in {"00", "0"}:
        data.setdefault("gnss_fix", False)
        data.setdefault("is_last_fix", True)

    protocol_version = data.get("version")
    if protocol_version:
        data.setdefault("protocol_version", protocol_version)

    count_hex = data.get("count_hex")

    if device_from_record:
        try:
            data["spec_path"] = get_spec_path("GTERI", str(device_from_record))
        except ValueError:
            data["spec_path"] = None

    enriched = _common_enrich(data, detected_source or source, protocol_version, count_hex)
    for meta in ("prefix", "is_buff", "raw_line", "raw_after_mask"):
        enriched.pop(meta, None)
    return enriched


__all__ = ["parse_gteri"]
