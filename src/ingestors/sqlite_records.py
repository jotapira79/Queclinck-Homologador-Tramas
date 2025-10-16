"""Generic SQLite ingestor that stores Queclink reports by spec."""

from __future__ import annotations

import json
import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from queclink.parser import load_spec as load_parser_spec
from queclink.parser import parse_line

_LOGGER = logging.getLogger(__name__)

def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_db(path: str | Path) -> sqlite3.Connection:
    """Create a SQLite database (if needed) and return an open connection."""

    db_path = Path(path)
    if db_path != Path(":memory:"):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


@lru_cache(maxsize=64)
def resolve_spec(report: str, model: str) -> dict:
    """Load a YAML spec for the given report/model pair."""

    report_norm = report.strip().lower()
    model_norm = model.strip().lower()
    spec_path = _repository_root() / "spec" / model_norm / f"{report_norm}.yml"
    if not spec_path.exists():
        raise FileNotFoundError(spec_path)
    spec_obj = load_parser_spec(model.strip().upper(), report.strip().upper())
    return {"path": spec_path, "fields": spec_obj.fields, "spec": spec_obj}


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    result_chars = []
    for char in line:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == "#" and not in_single and not in_double:
            break
        result_chars.append(char)
    return "".join(result_chars).rstrip()


def _parse_inline_mapping(text: str) -> dict[str, str]:
    text = text.strip()
    if text.startswith("-"):
        text = text[1:].strip()
    if text.startswith("{") and text.endswith("}"):
        text = text[1:-1]
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "," and depth == 0:
            segment = "".join(current).strip()
            if segment:
                parts.append(segment)
            current = []
            continue
        current.append(char)
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth = max(depth - 1, 0)
    segment = "".join(current).strip()
    if segment:
        parts.append(segment)
    mapping: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        mapping[key.strip()] = value.strip().strip('"\'')
    return mapping


def _extract_spec_fields(spec_path: Path) -> list[dict[str, Optional[str]]]:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    fields: list[dict[str, Optional[str]]] = []
    stack: list[tuple[int, Optional[str]]] = []
    current_entry: dict[str, Optional[str]] | None = None

    for raw_line in lines:
        line = _strip_comment(raw_line)
        if not line:
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
            if current_entry and indent <= current_entry.get("indent", -1):
                current_entry = None

        if stripped.endswith(":") and not stripped.startswith("-"):
            key = stripped[:-1].strip()
            stack.append((indent, key))
            continue

        if stripped.startswith("-"):
            parents = [key for _, key in stack if key]
            if any(key in ("format", "fields") for key in parents):
                entry: dict[str, Optional[str]] = {"name": None, "type": None, "indent": indent}
                content = stripped[1:].strip()
                if content:
                    if content.startswith("{") and content.endswith("}"):
                        mapping = _parse_inline_mapping(content)
                        entry["name"] = mapping.get("name")
                        entry["type"] = mapping.get("type")
                    elif ":" in content:
                        key, value = content.split(":", 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        if key == "name":
                            entry["name"] = value
                        elif key == "type":
                            entry["type"] = value
                fields.append(entry)
                current_entry = entry
                stack.append((indent, None))
            else:
                current_entry = None
                stack.append((indent, None))
            continue

        if current_entry and indent > int(current_entry.get("indent", -1)):
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if not value:
                stack.append((indent, key))
                current_entry = None
                continue
            value = value.strip().split("#", 1)[0].strip().strip('"\'')
            if key == "name" and not current_entry.get("name"):
                current_entry["name"] = value
            elif key == "type" and not current_entry.get("type"):
                current_entry["type"] = value
            continue

        current_entry = None

    ordered: list[dict[str, Optional[str]]] = []
    seen: set[str] = set()
    for entry in fields:
        name = entry.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        ordered.append({"name": name, "type": entry.get("type")})
    return ordered


def spec_to_sql_columns(spec: dict) -> list[tuple[str, str]]:
    type_map = {
        "int": "INTEGER",
        "integer": "INTEGER",
        "enum": "INTEGER",
        "float": "REAL",
        "double": "REAL",
        "decimal": "REAL",
        "string": "TEXT",
        "hex": "TEXT",
        "imei": "TEXT",
        "datetime": "TEXT",
        "date": "TEXT",
        "time": "TEXT",
        "bool": "INTEGER",
        "boolean": "INTEGER",
        "group": "TEXT",
        "object": "TEXT",
        "list": "TEXT",
        "array": "TEXT",
    }
    spec_obj = spec.get("spec")
    if spec_obj is not None:
        columns: list[tuple[str, str]] = []
        for field in getattr(spec_obj, "fields", []):
            if not getattr(field, "name", None):
                continue
            type_name = str(getattr(field, "type", "") or "").strip().lower()
            sql_type = type_map.get(type_name, "TEXT")
            columns.append((field.name, sql_type))
        return columns

    columns: list[tuple[str, str]] = []
    for field in spec.get("fields", []):
        name = field.get("name")
        if not name:
            continue
        type_name = (field.get("type") or "").strip().lower()
        sql_type = type_map.get(type_name, "TEXT")
        columns.append((name, sql_type))
    return columns


def ensure_table(conn, report: str, model: str, spec: dict) -> None:
    report_lower = report.strip().lower()
    table = f"{report_lower}_records"
    columns = spec_to_sql_columns(spec)
    column_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    seen: set[str] = set()
    for name, sql_type in columns:
        if name in seen:
            continue
        seen.add(name)
        column_defs.append(f"\"{name}\" {sql_type}")
    unique_candidates = ("imei", "send_time", "count_hex")
    if all(field in seen for field in unique_candidates):
        column_defs.append("UNIQUE(imei, send_time, count_hex)")
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(column_defs)})"
    )
    if {"imei", "send_time"}.issubset(seen):
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_imei_send_time ON {table} (imei, send_time)"
        )
    if {"model", "send_time"}.issubset(seen):
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_model_send_time ON {table} (model, send_time)"
        )
    conn.commit()


def _safe_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str) and value.lower().startswith("0x"):
            return int(value, 16)
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)





def normalize_for_sql(spec: dict, parsed: dict) -> dict:
    report = parsed.get("report") or parsed.get("message")
    row: dict[str, Optional[object]] = {}
    column_types = spec_to_sql_columns(spec)
    for column, sql_type in column_types:
        raw_value = parsed.get(column)
        if raw_value in ("", None):
            value = None
        else:
            if column in {"lon", "lon_deg", "lon_decimal", "longitude", "longitude_deg", "lat", "latitude", "latitude_deg", "lat_deg", "mileage", "mileage_km"}:
                value = _safe_float(raw_value)
            elif sql_type == "INTEGER":
                value = _safe_int(raw_value)
            elif sql_type == "REAL":
                value = _safe_float(raw_value)
            else:
                value = _as_text(raw_value)
        if value is None and column not in parsed:
            _LOGGER.warning("[WARN] missing field %s for report %s", column, report)
        row[column] = value
    return row


def insert_record(conn, report: str, row: dict) -> None:
    report_lower = report.strip().lower()
    table = f"{report_lower}_records"
    columns = list(row.keys())
    escaped_columns = [f'"{col}"' for col in columns]
    placeholders = ", ".join(f":{col}" for col in columns)
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(escaped_columns)}) VALUES ({placeholders})"
    conn.execute(sql, row)
    conn.commit()


def ingest_lines(
    conn: sqlite3.Connection,
    lines: Iterable[str],
    *,
    message: Optional[str] = None,
) -> int:
    expected_report = message.upper() if message else None
    inserted = 0

    for raw_line in lines:
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("$"):
            line = line
        parsed = parse_line(line)
        if not parsed:
            continue
        report = str(parsed.get("report") or parsed.get("message") or "").upper()
        if not report:
            continue
        if expected_report and report != expected_report:
            continue
        model = parsed.get("model") or parsed.get("device") or parsed.get("device_name")
        if not model:
            continue
        model = str(model).upper()
        try:
            spec = resolve_spec(report, model)
        except FileNotFoundError:
            _LOGGER.warning("[WARN] spec not found for %s/%s", model, report)
            continue
        ensure_table(conn, report, model, spec)
        row = normalize_for_sql(spec, parsed)
        insert_record(conn, report, row)
        inserted += 1

    return inserted


__all__ = ["ensure_db", "ingest_lines", "resolve_spec", "spec_to_sql_columns", "ensure_table", "normalize_for_sql", "insert_record"]
