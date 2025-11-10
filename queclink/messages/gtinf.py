"""Parser para mensajes GTINF homologado por modelo (usando spec YAML)."""

from __future__ import annotations

from typing import Dict, List, Optional
import re

from ..parser import _split, detect_model_from_identifiers, load_spec

_GTINF_HEADERS = {"+RESP:GTINF", "+BUFF:GTINF"}

def _split_header_message(first_token: str) -> Optional[Dict[str, str]]:
    # first_token es "+RESP:GTINF" o "+BUFF:GTINF"
    if first_token not in _GTINF_HEADERS:
        return None
    if first_token.startswith("+RESP:"):
        return {"header": "+RESP:GT", "message": "INF"}
    if first_token.startswith("+BUFF:"):
        return {"header": "+BUFF:GT", "message": "INF"}
    return None

def parse_gtinf(line: str, source: str = "RESP", device: Optional[str] = None) -> Dict[str, Any]:
    """
    Parsea un mensaje +RESP/+BUFF:GTINF y devuelve un dict homologado
    con las columnas EXACTAS definidas en la spec del modelo.
    """
    parts = _split(line)
    if not parts:
        return {}

    first = parts[0].strip()
    if first not in _GTINF_HEADERS:
        return {}

    # Detectar modelo desde el 4° campo si no viene por parámetro
    reported_device_name = (parts[3].strip() if len(parts) > 3 else "").strip()
    model = (device or detect_model_from_identifiers(parts[2] if len(parts) > 2 else None, reported_device_name))
    if not model:
        model = reported_device_name
    if not model:
        return {}

    model = model.strip().upper()
    try:
        spec = load_spec(model, "GTINF")
    except (ValueError, FileNotFoundError):
        fallback = reported_device_name.strip().upper()
        if fallback and fallback != model:
            spec = load_spec(fallback, "GTINF")
            model = fallback
        else:
            raise

    columns = [field.name for field in spec.fields]

    # Reconstruir "header" y "message" de la spec a partir del primer token
    hm = _split_header_message(first)
    if hm is None:
        return {}

    # Ahora mapeamos por posición:
    # spec espera: header, message, full_protocol_version, imei, device_name, ...
    values: List[Optional[str]] = []
    values.append(hm["header"])
    values.append(hm["message"])

    iterator = iter(parts[1:])
    for field in spec.fields[2:]:
        raw_value = next(iterator, None)
        if raw_value is None:
            values.append(None)
            continue

        if raw_value == "" and (field.optional or getattr(field, "nullable", False)):
            values.append(None)
            continue

        values.append(raw_value)

    homologated = dict(zip(columns, values))
    if reported_device_name:
        homologated["device_name"] = reported_device_name

    if len(parts) >= 2:
        homologated["count_hex"] = parts[-1]
    if len(parts) >= 3 and "send_time" in homologated:
        homologated["send_time"] = parts[-2]
    if len(parts) >= 4 and "dst" in homologated:
        homologated["dst"] = parts[-3]
    if len(parts) >= 5 and "timezone_offset" in homologated:
        homologated["timezone_offset"] = parts[-4]

    # Importante: NO añadir aquí campos genéricos (raw, report, spec_path, etc.)
    # Para mantener DB limpia 1:1 con protocolo.

    return homologated

__all__ = ["parse_gtinf"]
