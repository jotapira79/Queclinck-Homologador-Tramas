"""Parsing helpers that rely on the YAML specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .utils.simple_yaml import load_file

_LOGGER = logging.getLogger(__name__)

_HEADER_RE = re.compile(r"^\+(RESP|BUFF):(GT[A-Z0-9]+)$")

_MODEL_PREFIXES = {
    "86631406": "gv58lau",
    "86858906": "gv310lau",
    "86252406": "gv350ceu",
    "86848700": "gv37cau",
}

_DEVICE_NAME_MODELS = {
    "GV58LAU": "gv58lau",
    "GV310LAU": "gv310lau",
    "GV350CEU": "gv350ceu",
    "GV75LAU": "gv75lau",
    "GV37CAU": "gv37cau",
}


_EQUALS_SENTINEL = object()


_COND_MASK_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*&\s*(0x[0-9A-Fa-f]+|\d+)(?:\s*!=?\s*0)?$")


def _condition_from_expression(expression: str) -> Optional["Condition"]:
    if not isinstance(expression, str):
        return None
    text = expression.strip()
    if not text:
        return None
    match = _COND_MASK_RE.match(text)
    if not match:
        return None
    field_name, mask_raw = match.groups()
    try:
        mask_value = int(mask_raw, 0)
    except ValueError:
        return None
    if mask_value <= 0 or (mask_value & (mask_value - 1)) != 0:
        return None
    bit_index = 0
    value = mask_value
    while value > 1:
        value >>= 1
        bit_index += 1
    return Condition(mask_field=field_name, bit=bit_index)


@dataclass(frozen=True)
class Condition:
    mask_field: Optional[str] = None
    bit: Optional[int] = None
    field_present: Optional[str] = None
    field_name: Optional[str] = None
    feature_name: Optional[str] = None
    equals: object = _EQUALS_SENTINEL
    any_of: Sequence["Condition"] = field(default_factory=tuple)
    all_of: Sequence["Condition"] = field(default_factory=tuple)

    @staticmethod
    def from_mapping(mapping: Optional[dict | str]) -> Optional["Condition"]:
        if not mapping or not isinstance(mapping, dict):
            return _condition_from_expression(mapping) if isinstance(mapping, str) else None

        any_of_raw = mapping.get("anyOf") or mapping.get("any_of")
        if isinstance(any_of_raw, (list, tuple)):
            subconditions = [
                Condition.from_mapping(item)
                for item in any_of_raw
                if isinstance(item, dict)
            ]
            subconditions = [cond for cond in subconditions if cond]
            if subconditions:
                return Condition(any_of=tuple(subconditions))
            return None

        all_of_raw = mapping.get("allOf") or mapping.get("all_of")
        if isinstance(all_of_raw, (list, tuple)):
            subconditions = [
                Condition.from_mapping(item)
                for item in all_of_raw
                if isinstance(item, dict)
            ]
            subconditions = [cond for cond in subconditions if cond]
            if subconditions:
                return Condition(all_of=tuple(subconditions))
            return None

        mask_field = mapping.get("mask_field") or mapping.get("mask")
        bit_value = mapping.get("bit")
        try:
            bit = int(bit_value) if bit_value is not None else None
        except (TypeError, ValueError):
            bit = None

        field_present = mapping.get("field_present")
        field_name = mapping.get("field")
        feature_name = mapping.get("feature")
        equals_value = mapping.get("equals", _EQUALS_SENTINEL)

        if not any((mask_field, field_present, field_name, feature_name)):
            return None

        return Condition(
            mask_field=mask_field,
            bit=bit,
            field_present=field_present,
            field_name=field_name,
            feature_name=feature_name,
            equals=equals_value,
        )


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str = "string"
    optional: bool = False
    const: Optional[str] = None
    const_any: Sequence[str] = field(default_factory=tuple)
    present_if: Optional[Condition] = None
    present_if_any: Sequence[Condition] = field(default_factory=tuple)
    enabled_if_any: Sequence[Condition] = field(default_factory=tuple)
    repeat: Optional[str] = None
    fields: Sequence["FieldSpec"] = field(default_factory=tuple)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    default_if_absent: Optional[object] = None


@dataclass(frozen=True)
class Spec:
    model: str
    message: str
    table_name: str
    delimiter: str
    terminator: str
    fields: Sequence[FieldSpec]
    config: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class HeadInfo:
    source: str
    report: str
    message: str


class _TokenStream:
    def __init__(self, tokens: Sequence[str]):
        self._tokens = list(tokens)
        self._index = 0

    def remaining(self) -> int:
        return len(self._tokens) - self._index

    def next(self) -> str:
        if self._index >= len(self._tokens):
            raise ValueError("No hay suficientes campos en la trama")
        value = self._tokens[self._index]
        self._index += 1
        return value

    def peek(self) -> Optional[str]:
        if self._index >= len(self._tokens):
            return None
        return self._tokens[self._index]

    def push_back(self, count: int = 1) -> None:
        if count <= 0:
            return
        self._index = max(0, self._index - count)


class _ParseContext:
    def __init__(
        self,
        parent: Optional["_ParseContext"] = None,
        *,
        features: Optional[dict[str, object]] = None,
    ):
        self.parent = parent
        self.values: dict[str, object] = {}
        self.present: set[str] = set()
        if parent is None:
            self._features = dict(features or {})
        else:
            self._features = parent._features

    def set(self, name: str, value: object, raw: Optional[str]) -> None:
        self.values[name] = value
        if raw not in (None, ""):
            self.present.add(name)

    def get(self, name: str) -> Optional[object]:
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.get(name)
        return None

    def is_present(self, name: str) -> bool:
        if name in self.present:
            return True
        if self.parent:
            return self.parent.is_present(name)
        return False

    def get_feature(self, name: str) -> Optional[object]:
        if name in self._features:
            return self._features[name]
        if self.parent:
            return self.parent.get_feature(name)
        return None


def identify_head(line: str) -> Optional[HeadInfo]:
    tokens = _tokenize(line)
    if not tokens:
        return None
    head = tokens[0].strip()
    match = _HEADER_RE.match(head)
    if not match:
        return None
    source, report = match.group(1), match.group(2)
    message = report[2:] if report.startswith("GT") else report
    return HeadInfo(source=source, report=report, message=message)


def model_from_imei(imei: str) -> Optional[str]:
    if not imei:
        return None
    digits = "".join(ch for ch in str(imei) if ch.isdigit())
    if len(digits) < 8:
        return None
    prefix = digits[:8]
    return _MODEL_PREFIXES.get(prefix)


def _model_from_device_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    normalized = str(name).strip().upper()
    if not normalized:
        return None
    return _DEVICE_NAME_MODELS.get(normalized)


def _spec_path(model: str, message: str) -> Path:
    return Path("spec") / model.lower() / f"{message.lower()}.yml"


def _ensure_sequence(value) -> Sequence[str]:
    if not value:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _normalize_limit(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        if text.lower().startswith("0x"):
            return float(int(text, 16))
        return float(text)
    except (TypeError, ValueError):
        return None


def _build_field(entry: dict) -> FieldSpec:
    name = str(entry.get("name"))
    field_type = str(entry.get("type", "string"))
    optional = bool(entry.get("optional", False))
    const = entry.get("const")
    const_any = _ensure_sequence(entry.get("const_any"))
    min_value = _normalize_limit(entry.get("min"))
    max_value = _normalize_limit(entry.get("max"))
    default_if_absent = entry.get("default_if_absent")

    present_if = Condition.from_mapping(entry.get("present_if"))
    present_if_any_list = [
        cond
        for cond in (
            Condition.from_mapping(item)
            for item in entry.get("present_if_any", []) or []
        )
        if cond
    ]
    enabled_if_any_list = [
        cond
        for cond in (
            Condition.from_mapping(item)
            for item in entry.get("enabled_if_any", []) or []
        )
        if cond
    ]

    when_entry = entry.get("when")
    if isinstance(when_entry, dict):
        when_condition = Condition.from_mapping(when_entry)
        if when_condition:
            if when_condition.any_of:
                present_if_any_list.extend(when_condition.any_of)
            else:
                enabled_if_any_list.append(when_condition)

    repeat = entry.get("repeat")
    nested_fields = tuple(_build_field(child) for child in entry.get("fields", []) or [])
    return FieldSpec(
        name=name,
        type=field_type,
        optional=optional,
        const=const,
        const_any=const_any,
        present_if=present_if,
        present_if_any=tuple(present_if_any_list),
        enabled_if_any=tuple(enabled_if_any_list),
        repeat=repeat,
        fields=nested_fields,
        min_value=min_value,
        max_value=max_value,
        default_if_absent=default_if_absent,
    )


@lru_cache(maxsize=64)
def load_spec(model: str, message: str) -> Spec:
    path = _spec_path(model, message)
    data = load_file(str(path))
    table_name = data.get("table_name") or f"{message.lower()}_{model.lower()}"
    delimiter = data.get("delimiter", ",")
    terminator = data.get("terminator", "$")
    config = data.get("config") or {}
    sections = data.get("schema", {}).get("sections", [])
    fields: List[FieldSpec] = []
    for section in sections or []:
        for entry in section.get("fields", []) or []:
            if isinstance(entry, dict) and entry.get("name"):
                fields.append(_build_field(entry))
    return Spec(
        model=model,
        message=message,
        table_name=table_name,
        delimiter=delimiter,
        terminator=terminator,
        fields=tuple(fields),
        config=dict(config),
    )


_SKIP = object()


def _normalize_message_name(message: str) -> str:
    if not message:
        return message
    message = message.upper()
    if message.startswith("GT"):
        return message
    return f"GT{message}"


def normalize_line_for_spec(raw_line: str, message: str, spec: Optional[Spec]) -> str:
    if spec is None:
        return raw_line

    normalized_message = _normalize_message_name(message or "")
    header_field = next((field for field in spec.fields if field.name == "header"), None)
    if not header_field or not header_field.const_any:
        return raw_line

    allowed_headers = set(header_field.const_any)
    if not allowed_headers:
        return raw_line

    if not normalized_message.startswith("GT"):
        return raw_line

    suffix = normalized_message[2:]
    if not suffix:
        return raw_line

    for prefix in ("+RESP:GT", "+BUFF:GT"):
        matching_headers = [header for header in allowed_headers if header.startswith(prefix)]
        if not matching_headers:
            continue

        if prefix in allowed_headers:
            marker = f"{prefix}{suffix}"
            if marker in allowed_headers:
                continue
            if raw_line.startswith(marker):
                return raw_line.replace(marker, f"{prefix},{suffix}", 1)
            continue

        target = matching_headers[0]
        if raw_line.startswith(target):
            return raw_line
        target_suffix = target[len(prefix) :]
        composite = f"{prefix},{target_suffix}"
        if raw_line.startswith(composite):
            return raw_line.replace(composite, target, 1)
    return raw_line


def parse_line(
    line: str,
    source: Optional[str] = None,
    model: Optional[str] = None,
    message: Optional[str] = None,
    *,
    spec: Optional[Spec] = None,
    enrich: Optional[bool] = None,
) -> dict:
    head = identify_head(line) if source is None or message is None else None
    if head:
        source = source or head.source
        message = message or head.report
    if message is None:
        raise ValueError("No se pudo determinar el tipo de mensaje")
    message = _normalize_message_name(message)
    tokens = _tokenize(line)
    reported_device = tokens[3] if len(tokens) > 3 else None
    if model is None:
        if len(tokens) < 3:
            raise ValueError("No se pudo inferir el modelo por falta de campos")
        model = detect_model_from_identifiers(tokens[2], reported_device)
    if model is None and spec is None:
        raise ValueError("No se pudo determinar el modelo de la trama")
    spec_was_provided = spec is not None
    if spec is None:
        spec = load_spec(model or "", message)
    line = normalize_line_for_spec(line, message, spec)
    model = model or spec.model
    tokens = _tokenize(line, delimiter=spec.delimiter, terminator=spec.terminator)
    stream = _TokenStream(tokens)
    context = _ParseContext(features=spec.config)
    result: dict[str, object] = {}
    for index, field in enumerate(spec.fields):
        remaining = spec.fields[index + 1 :]
        value = _parse_field(
            field,
            stream,
            context,
            remaining_fields=remaining,
            config=spec.config,
        )
        if value is not _SKIP:
            result[field.name] = value

    normalized_report = message
    if normalized_report:
        normalized_report = normalized_report.upper()
    enrich_records = enrich if enrich is not None else not spec_was_provided

    if normalized_report and enrich_records:
        if "report" not in result:
            result["report"] = normalized_report
        result["message"] = normalized_report
    if spec is not None and enrich_records:
        result.setdefault("model", getattr(spec, "model", None))
    if not enrich_records:
        return result
    protocol_version = result.get("full_protocol_version") or result.get("protocol_version")
    count_hex = result.get("count_hex")
    return _common_enrich(result, source, protocol_version, count_hex)


def _should_force_parse(
    field: FieldSpec,
    stream: _TokenStream,
    config: Optional[dict[str, object]],
) -> bool:
    name = getattr(field, "name", None)
    if name == "satellites_used":
        token = stream.peek()
        if token in (None, ""):
            return False
        text = str(token).strip()
        if not text:
            return False
        if re.fullmatch(r"\d{1,2}", text):
            return True

    if not config:
        return False

    if name == "gnss_trigger_type":
        token = stream.peek()
        if token == "":
            return True

    tolerated_raw = config.get("tolerate_unmasked_position_fields")
    if not tolerated_raw:
        return False

    if tolerated_raw is True:
        tolerated = {"sats_in_use", "hdop", "vdop", "pdop"}
    elif isinstance(tolerated_raw, str):
        tolerated = {tolerated_raw}
    elif isinstance(tolerated_raw, (set, tuple, list)):
        tolerated = {str(item) for item in tolerated_raw}
    else:
        return False

    name = getattr(field, "name", None)
    if not name or name not in tolerated:
        return False

    token = stream.peek()
    if token in (None, ""):
        return False

    text = str(token).strip()
    if not text:
        return False

    if name == "sats_in_use":
        pattern = r"\d{1,2}"
    else:
        pattern = r"-?\d+(?:\.\d+)?"

    if re.fullmatch(pattern, text) is None:
        return False

    candidate: object
    try:
        candidate = int(text) if name == "sats_in_use" else float(text)
    except ValueError:
        return False

    if not _value_within_limits(field, candidate):
        return False

    return True


def _parse_field(
    field: FieldSpec,
    stream: _TokenStream,
    context: _ParseContext,
    *,
    remaining_fields: Sequence[FieldSpec] = (),
    config: Optional[dict[str, object]] = None,
):
    if not _should_parse(field, context):
        if not _should_force_parse(field, stream, config):
            return _SKIP

    required_tokens = _minimum_required_tokens(remaining_fields, context)
    if field.optional and stream.remaining() <= required_tokens:
        if field.default_if_absent is not None:
            context.set(field.name, field.default_if_absent, None)
            return field.default_if_absent
        return _SKIP

    if field.type == "group_repeated":
        count = _repeat_count(field, context)
        if (count is None or count <= 0) and field.optional:
            return _SKIP
        return _parse_group(field, stream, context, count=count, config=config)

    if stream.remaining() <= 0:
        if field.optional:
            if field.default_if_absent is not None:
                context.set(field.name, field.default_if_absent, None)
                return field.default_if_absent
            return _SKIP
        raise ValueError(f"Faltan campos para {field.name}")

    raw = stream.next()
    if raw == "" and field.optional:
        context.set(field.name, None, raw)
        return None

    if field.const is not None and raw != field.const:
        if field.name not in {"device_name"}:
            raise ValueError(f"El campo {field.name} no coincide con el valor esperado")
    if field.const_any:
        if not any(raw.startswith(prefix) for prefix in field.const_any):
            raise ValueError(f"El campo {field.name} no coincide con los prefijos permitidos")

    value = _convert_value(raw, field.type)

    if not _value_within_limits(field, value):
        if field.optional:
            stream.push_back()
            if field.default_if_absent is not None:
                context.set(field.name, field.default_if_absent, None)
                return field.default_if_absent
            return _SKIP
        raise ValueError(f"El campo {field.name} está fuera de los rangos permitidos")

    context.set(field.name, value, raw)
    return value


def _parse_group(
    field: FieldSpec,
    stream: _TokenStream,
    context: _ParseContext,
    *,
    count: Optional[int] = None,
    config: Optional[dict[str, object]] = None,
):
    if count is None:
        count = _repeat_count(field, context)
    if count is None or count < 0:
        count = 0
    items: List[dict] = []
    for _ in range(count):
        child_context = _ParseContext(parent=context)
        item: dict[str, object] = {}
        for index, nested in enumerate(field.fields):
            nested_remaining = field.fields[index + 1 :]
            value = _parse_field(
                nested,
                stream,
                child_context,
                remaining_fields=nested_remaining,
                config=config,
            )
            if value is not _SKIP:
                item[nested.name] = value
        items.append(item)
    context.set(field.name, items, str(len(items)) if items else None)
    return items


def _repeat_count(field: FieldSpec, context: _ParseContext) -> Optional[int]:
    repeat_field = field.repeat
    if not repeat_field:
        return None
    return _to_int(context.get(repeat_field))


def _should_parse(field: FieldSpec, context: _ParseContext) -> bool:
    if field.enabled_if_any:
        if not any(_check_condition(cond, context) for cond in field.enabled_if_any):
            return False
    if field.present_if:
        if not _check_condition(field.present_if, context):
            return False
    if field.present_if_any:
        if not any(_check_condition(cond, context) for cond in field.present_if_any):
            return False
    return True


def _check_condition(condition: Condition, context: _ParseContext) -> bool:
    if condition.any_of:
        return any(_check_condition(cond, context) for cond in condition.any_of)
    if condition.all_of:
        return all(_check_condition(cond, context) for cond in condition.all_of)
    if condition.mask_field:
        mask_value = context.get(condition.mask_field)
        if mask_value is None:
            return False
        return _is_bit_set(mask_value, condition.bit or 0)
    if condition.field_present:
        return context.is_present(condition.field_present)
    if condition.field_name is not None and condition.equals is not _EQUALS_SENTINEL:
        value = context.get(condition.field_name)
        return value == condition.equals
    if condition.feature_name:
        value = context.get_feature(condition.feature_name)
        if condition.equals is not _EQUALS_SENTINEL:
            return value == condition.equals
        return bool(value)
    return False


def _is_bit_set(value: object, bit: int) -> bool:
    if bit < 0:
        return False

    numeric: Optional[int] = None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            numeric = int(text, 16)
        except ValueError:
            numeric = _to_int(value)
    else:
        numeric = _to_int(value)

    if numeric is None:
        return False

    return bool(numeric & (1 << bit))


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        base = 10
        if text.lower().startswith("0x"):
            base = 16
            text = text[2:]
        elif any(ch in "abcdefABCDEF" for ch in text):
            base = 16
        return int(text, base)
    except (TypeError, ValueError):
        return None


def _value_within_limits(field: FieldSpec, value: object) -> bool:
    if value is None:
        return True
    if field.min_value is None and field.max_value is None:
        return True

    numeric: Optional[float]
    if isinstance(value, bool):
        numeric = float(int(value))
    elif isinstance(value, (int, float)):
        numeric = float(value)
    else:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False

    if field.min_value is not None and numeric < field.min_value:
        return False
    if field.max_value is not None and numeric > field.max_value:
        return False
    return True


def _minimum_required_tokens(
    fields: Sequence[FieldSpec], context: _ParseContext
) -> int:
    required = 0
    for field in fields:
        if not _should_parse(field, context):
            continue
        if field.type == "group_repeated":
            continue
        if field.optional:
            continue
        required += 1
    return required


def _convert_value(raw: str, field_type: str):
    normalized = field_type.lower()
    if normalized in {"int", "integer", "enum"}:
        try:
            return _to_int(raw)
        except ValueError:
            return None
    if normalized in {"float", "double", "decimal"}:
        try:
            return float(raw)
        except ValueError:
            return None
    if normalized in {"bool", "boolean"}:
        if raw.lower() in {"true", "1"}:
            return True
        if raw.lower() in {"false", "0"}:
            return False
        return bool(_to_int(raw))
    if normalized == "hex":
        return raw.upper()
    if normalized == "group" or normalized == "group_repeated":
        return raw
    return raw


def _strip_bom(text: str) -> str:
    """Remove Unicode byte order marks (BOM) from the beginning of a string."""

    if not text:
        return text

    # Python already strips common whitespace with ``str.strip`` but BOM characters
    # are not considered whitespace. Some Windows editors (e.g. Notepad) may inject a
    # UTF-8 BOM (``\ufeff``) at the beginning of exported log files which makes the
    # first token fail the ``const_any`` validation (e.g. ``+RESP:GTFRI``). By
    # normalising those characters we make the parser resilient to those files while
    # keeping the remaining payload untouched.
    return text.lstrip("\ufeff\ufffe")


def _tokenize(line: str, delimiter: str = ",", terminator: str = "$") -> List[str]:
    payload = _strip_bom(line).strip()
    if terminator and payload.endswith(terminator):
        payload = payload[: -len(terminator)]
    if not payload:
        return []
    parts = [part.strip() for part in payload.split(delimiter)]
    return [_strip_bom(part) for part in parts]


def _split(line: str) -> List[str]:
    """Split a raw Queclink line using the standard delimiter/terminator."""

    return _tokenize(line)


def _to_iso(timestamp: Optional[str]) -> Optional[str]:
    """Convert a Queclink timestamp (YYYYMMDDHHMMSS) to ISO-8601."""

    if not timestamp:
        return None
    ts = str(timestamp).strip()
    if not ts:
        return None

    known_formats = (
        "%Y%m%d%H%M%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    )
    for fmt in known_formats:
        try:
            dt = datetime.strptime(ts, fmt)
        except ValueError:
            continue
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    if re.fullmatch(r"\d{14}", ts):
        try:
            dt = datetime.strptime(ts[:14], "%Y%m%d%H%M%S")
        except ValueError:
            return None
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return None


def detect_model_from_identifiers(imei: Optional[str], reported_device: Optional[str]) -> Optional[str]:
    """Best effort model detection using IMEI prefix and reported device name."""

    imei_model = model_from_imei(imei or "")
    reported_model = _model_from_device_name(reported_device)

    if reported_model and imei_model and reported_model != imei_model:
        return reported_model.upper()
    if reported_model:
        return reported_model.upper()
    if imei_model:
        return imei_model.upper()
    if reported_device:
        normalized = reported_device.strip().upper()
        if normalized:
            return normalized
    return None


def _infer_source(header: Optional[str], fallback: Optional[str]) -> Optional[str]:
    if isinstance(fallback, str) and fallback:
        return fallback.strip().upper()
    if isinstance(header, str):
        if header.startswith("+RESP:"):
            return "RESP"
        if header.startswith("+BUFF:"):
            return "BUFF"
    return None


def _common_enrich(
    data: Dict[str, Any],
    source: Optional[str],
    protocol_version: Optional[str],
    count_hex: Optional[str],
) -> Dict[str, Any]:
    """Apply project-wide normalisations shared by message parsers."""

    enriched: Dict[str, Any] = dict(data)

    header = enriched.get("header")
    inferred_source = _infer_source(header, source)
    if inferred_source:
        enriched["source"] = inferred_source

    message = enriched.get("message")
    if isinstance(message, str):
        enriched["message"] = message.upper()

    if isinstance(header, str) and ":" in header:
        _, report = header.split(":", 1)
        if report:
            enriched.setdefault("report", report)
    enriched.setdefault("report", enriched.get("message"))

    device = enriched.get("device") or enriched.get("model") or enriched.get("device_name")
    if isinstance(device, str) and device.strip():
        enriched["device"] = device.strip().upper()

    imei = enriched.get("imei")
    if imei is not None:
        enriched["imei"] = str(imei)

    if protocol_version:
        enriched.setdefault("protocol_version", protocol_version)
        enriched.setdefault("version", protocol_version)
    else:
        version = enriched.get("version") or enriched.get("full_protocol_version")
        if version:
            enriched.setdefault("protocol_version", version)

    hex_value = count_hex or enriched.get("count_hex")
    if isinstance(hex_value, str) and hex_value:
        normalized_hex = hex_value.strip().upper()
        enriched["count_hex"] = normalized_hex
        try:
            enriched.setdefault("count_dec", int(normalized_hex, 16))
        except ValueError:
            pass

    send_time = enriched.get("send_time")
    if isinstance(send_time, str):
        iso = _to_iso(send_time)
        if iso:
            enriched.setdefault("send_time_iso", iso)

    gnss_time = (
        enriched.get("utc")
        or enriched.get("gnss_utc")
        or enriched.get("gnss_utc_time")
    )
    if isinstance(gnss_time, str):
        iso = _to_iso(gnss_time)
        if iso:
            enriched.setdefault("utc", iso)
            enriched.setdefault("gnss_utc", gnss_time)
            enriched.setdefault("gnss_utc_iso", iso)

    onewire = enriched.get("onewire")
    if isinstance(onewire, dict):
        devices = onewire.get("devices")
        if not isinstance(devices, list):
            devices = []
        count = onewire.get("count")
        if not isinstance(count, int):
            count = len(devices)
        enriched["onewire_device_count"] = count
        enriched["onewire_devices"] = devices

    fuel_sensor = enriched.get("fuel_sensor")
    if isinstance(fuel_sensor, dict):
        sensors = fuel_sensor.get("sensors")
        if not isinstance(sensors, list):
            sensors = []
        count = fuel_sensor.get("count")
        if not isinstance(count, int):
            count = len(sensors)
        enriched["fuel_sensor_count"] = count
        enriched["fuel_sensor_block"] = sensors

    eri_mask_raw = enriched.get("eri_mask")
    mask_value: Optional[int] = None
    if isinstance(eri_mask_raw, str):
        try:
            mask_value = int(eri_mask_raw, 16)
        except ValueError:
            mask_value = None
    if mask_value is not None:
        if (mask_value & (1 << 1)) and "onewire_device_count" not in enriched:
            enriched["onewire_device_count"] = 0
            enriched["onewire_devices"] = []
        if (mask_value & ((1 << 8) | (1 << 12))) and "ble_count" not in enriched:
            enriched["ble_count"] = 0
            enriched.setdefault("ble_block", {"accessory_number": 0, "items": []})
        if (mask_value & (1 << 13)) and "rat" not in enriched:
            enriched["rat"] = None
            enriched.setdefault("rat_band", {"rat": None, "band": None})

    if mask_value == 0:
        if "rat" in enriched and "rat_band" in enriched:
            enriched.pop("rat", None)
            band_info = enriched.pop("rat_band", None)
            if band_info and isinstance(band_info, dict):
                enriched.pop("band", None)
    elif mask_value in {0x00000002, 0x00001000}:
        enriched.pop("rat", None)
        enriched.pop("rat_band", None)
        enriched.pop("band", None)

    return enriched


def parse_gteri(line: str, source: str = "RESP", device: Optional[str] = None) -> Dict[str, Any]:
    """Proxy to the GTERI parser avoiding import cycles."""

    from .messages.gteri import parse_gteri as _parse_gteri_impl

    return _parse_gteri_impl(line, source=source, device=device)


def parse_gtinf(line: str, source: str = "RESP", device: Optional[str] = None) -> Dict[str, Any]:
    """Proxy to the GTINF parser avoiding import cycles."""

    from .messages.gtinf import parse_gtinf as _parse_gtinf_impl

    return _parse_gtinf_impl(line, source=source, device=device)


__all__ = [
    "Condition",
    "FieldSpec",
    "Spec",
    "HeadInfo",
    "identify_head",
    "model_from_imei",
    "detect_model_from_identifiers",
    "normalize_line_for_spec",
    "load_spec",
    "parse_line",
    "parse_gteri",
    "parse_gtinf",
]

