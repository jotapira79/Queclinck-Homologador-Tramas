"""Parsing helpers that rely on the YAML specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import logging
import re
from pathlib import Path
from typing import List, Optional, Sequence

from .utils.simple_yaml import load_file

_LOGGER = logging.getLogger(__name__)

_HEADER_RE = re.compile(r"^\+(RESP|BUFF):(GT[A-Z0-9]+)$")

_MODEL_PREFIXES = {
    "86631406": "gv58lau",
    "86858906": "gv310lau",
    "86252406": "gv350ceu",
}


_EQUALS_SENTINEL = object()


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
    def from_mapping(mapping: Optional[dict]) -> Optional["Condition"]:
        if not mapping or not isinstance(mapping, dict):
            return None

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


def _spec_path(model: str, message: str) -> Path:
    return Path("spec") / model.lower() / f"{message.lower()}.yml"


def _ensure_sequence(value) -> Sequence[str]:
    if not value:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _build_field(entry: dict) -> FieldSpec:
    name = str(entry.get("name"))
    field_type = str(entry.get("type", "string"))
    optional = bool(entry.get("optional", False))
    const = entry.get("const")
    const_any = _ensure_sequence(entry.get("const_any"))

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


def parse_line(
    line: str,
    source: Optional[str] = None,
    model: Optional[str] = None,
    message: Optional[str] = None,
    *,
    spec: Optional[Spec] = None,
) -> dict:
    head = identify_head(line) if source is None or message is None else None
    if head:
        source = source or head.source
        message = message or head.report
    if message is None:
        raise ValueError("No se pudo determinar el tipo de mensaje")
    message = _normalize_message_name(message)
    tokens = _tokenize(line)
    if model is None:
        if len(tokens) < 3:
            raise ValueError("No se pudo inferir el modelo por falta de campos")
        model = model_from_imei(tokens[2])
    if model is None and spec is None:
        raise ValueError("No se pudo determinar el modelo de la trama")
    if spec is None:
        spec = load_spec(model or "", message)
    model = model or spec.model
    tokens = _tokenize(line, delimiter=spec.delimiter, terminator=spec.terminator)
    stream = _TokenStream(tokens)
    context = _ParseContext(features=spec.config)
    result: dict[str, object] = {}
    for field in spec.fields:
        value = _parse_field(field, stream, context)
        if value is not _SKIP:
            result[field.name] = value
    return result


def _parse_field(field: FieldSpec, stream: _TokenStream, context: _ParseContext):
    if not _should_parse(field, context):
        return _SKIP

    if field.type == "group_repeated":
        return _parse_group(field, stream, context)

    if stream.remaining() <= 0:
        if field.optional:
            return _SKIP
        raise ValueError(f"Faltan campos para {field.name}")

    raw = stream.next()
    if raw == "" and field.optional:
        context.set(field.name, None, raw)
        return None

    if field.const is not None and raw != field.const:
        raise ValueError(f"El campo {field.name} no coincide con el valor esperado")
    if field.const_any:
        if not any(raw.startswith(prefix) for prefix in field.const_any):
            raise ValueError(f"El campo {field.name} no coincide con los prefijos permitidos")

    value = _convert_value(raw, field.type)
    context.set(field.name, value, raw)
    return value


def _parse_group(field: FieldSpec, stream: _TokenStream, context: _ParseContext):
    repeat_field = field.repeat
    count = _to_int(context.get(repeat_field)) if repeat_field else 0
    if count is None or count < 0:
        count = 0
    items: List[dict] = []
    for _ in range(count):
        child_context = _ParseContext(parent=context)
        item: dict[str, object] = {}
        for nested in field.fields:
            value = _parse_field(nested, stream, child_context)
            if value is not _SKIP:
                item[nested.name] = value
        items.append(item)
    context.set(field.name, items, str(len(items)) if items else None)
    return items


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

    numeric = _to_int(value)
    if numeric is not None and (numeric & (1 << bit)):
        return True

    if isinstance(value, str):
        text = value.strip()
        if text:
            try:
                numeric_hex = int(text, 16)
            except ValueError:
                numeric_hex = None
            else:
                return bool(numeric_hex & (1 << bit))

    return False


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


def _tokenize(line: str, delimiter: str = ",", terminator: str = "$") -> List[str]:
    payload = line.strip()
    if terminator and payload.endswith(terminator):
        payload = payload[: -len(terminator)]
    if not payload:
        return []
    return [part.strip() for part in payload.split(delimiter)]


__all__ = [
    "Condition",
    "FieldSpec",
    "Spec",
    "HeadInfo",
    "identify_head",
    "model_from_imei",
    "load_spec",
    "parse_line",
]

