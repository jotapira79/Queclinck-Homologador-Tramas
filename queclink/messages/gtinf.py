"""Parser para mensajes GTINF homologado por modelo (usando spec YAML)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..parser import (
    _split,
    _tokenize,
    detect_model_from_identifiers,
    load_spec,
    normalize_line_for_spec,
)

_GTINF_HEADERS = {"+RESP:GTINF", "+BUFF:GTINF", "+RESP:GT", "+BUFF:GT"}

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

    # Detectar modelo desde el campo IMEI, considerando si la trama trae el mensaje separado
    imei_token = parts[2] if len(parts) > 2 else None
    if first in {"+RESP:GT", "+BUFF:GT"} and len(parts) > 3:
        imei_token = parts[3]

    reported_device_name = (parts[4] if first in {"+RESP:GT", "+BUFF:GT"} else parts[3] if len(parts) > 3 else "")
    reported_device_name = (reported_device_name or "").strip()

    model = device or detect_model_from_identifiers(imei_token, reported_device_name)
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

    # Normalizar la línea según la spec (p. ej. separar header/message si el header es "+RESP:GTINF")
    normalized_line = normalize_line_for_spec(line, "GTINF", spec)
    parts = _tokenize(normalized_line, delimiter=spec.delimiter, terminator=spec.terminator)

    columns = [field.name for field in spec.fields]

    # Ahora mapeamos por posición respetando el orden exacto de la spec
    values: List[Optional[str]] = []
    values.append(parts[0] if parts else first)

    iterator = iter(parts[1:])
    for field in spec.fields[1:]:
        raw_value = next(iterator, None)
        if raw_value is None:
            values.append(None)
            continue

        if raw_value == "":
            values.append(None)
            continue

        values.append(raw_value)

    homologated = dict(zip(columns, values))

    # Para compatibilidad con el parser general, añadimos "message" derivado del header
    homologated.setdefault("message", "INF")

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
