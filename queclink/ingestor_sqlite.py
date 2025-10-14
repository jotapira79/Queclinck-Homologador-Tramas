"""SQLite ingestion utilities constrained by the YAML specs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

_GTERI_COLUMN_ORDER = [
    "header",
    "message",
    "full_protocol_version",
    "imei",
    "device_name",
    "eri_mask",
    "external_power_mv",
    "report_type",
    "number",
    "gnss_accuracy",
    "speed_kmh",
    "azimuth_deg",
    "altitude_m",
    "lon",
    "lat",
    "gnss_utc_time",
    "mcc",
    "mnc",
    "lac_hex",
    "cell_id_hex",
    "position_append_mask",
    "satellites_in_use",
    "hdop",
    "vdop",
    "pdop",
    "gnss_trigger_type",
    "gnss_jamming_state",
    "mileage_km",
    "hour_meter",
    "analog_in_1",
    "analog_in_2",
    "analog_in_3",
    "backup_batt_percent",
    "device_status",
    "uart_device_type",
    "ble_count",
    "ble_accessories",
    "rat",
    "band",
    "send_time",
    "count_hex",
]


def _order_fields(message: str, fields: Sequence[FieldSpec]) -> Sequence[FieldSpec]:
    if message.upper() != "GTERI":
        return fields

    field_map = {field.name: field for field in fields}
    ordered: list[FieldSpec] = []
    for name in _GTERI_COLUMN_ORDER:
        field = field_map.get(name)
        if field:
            ordered.append(field)
    if "lon" not in {field.name for field in ordered}:
        original = field_map.get("lon") or field_map.get("longitude") or field_map.get("longitude_deg")
        if original:
            ordered.append(FieldSpec(
                name="lon",
                type=original.type,
                optional=True,
                const=original.const,
                const_any=original.const_any,
                present_if=original.present_if,
                present_if_any=original.present_if_any,
                enabled_if_any=original.enabled_if_any,
                repeat=original.repeat,
                fields=original.fields,
            ))
    if "lat" not in {field.name for field in ordered}:
        original = field_map.get("lat") or field_map.get("latitude") or field_map.get("latitude_deg")
        if original:
            ordered.append(FieldSpec(
                name="lat",
                type=original.type,
                optional=True,
                const=original.const,
                const_any=original.const_any,
                present_if=original.present_if,
                present_if_any=original.present_if_any,
                enabled_if_any=original.enabled_if_any,
                repeat=original.repeat,
                fields=original.fields,
            ))
    return ordered

from .parser import FieldSpec, Spec, load_spec, parse_line


def _type_to_sql(field: FieldSpec) -> str:
    field_type = field.type.lower()
    if field_type in {"int", "integer", "enum", "bool", "boolean"}:
        return "INTEGER"
    if field_type in {"float", "double", "decimal"}:
        return "REAL"
    return "TEXT"


def _normalize_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return int(value)
    return value


def _prepare_record(message: str, record: dict) -> dict:
    normalized = dict(record)
    core = record.get("message_core")
    if message.upper() in {"GTINF", "GTERI"} and isinstance(core, str):
        normalized["message"] = core
    if "lon" not in normalized:
        lon_value = normalized.get("longitude") or normalized.get("longitude_deg")
        if lon_value is not None:
            normalized["lon"] = lon_value
    if "lat" not in normalized:
        lat_value = normalized.get("latitude") or normalized.get("latitude_deg")
        if lat_value is not None:
            normalized["lat"] = lat_value
    return normalized


def _relaxed_gtinf_parse(line: str, spec: Spec) -> Optional[dict[str, object]]:
    tokens = line.strip().rstrip("$").split(",")
    if not tokens or not tokens[0].startswith(("+RESP:GTINF", "+BUFF:GTINF")):
        return None
    record: dict[str, object] = {}
    token_iter = iter(tokens)
    for field in spec.fields:
        raw = next(token_iter, None)
        value = raw if raw not in (None, "") else None
        record[field.name] = value
    record.setdefault("raw_line", line)
    return record


@dataclass
class SQLiteIngestor:
    db_path: Path

    def __post_init__(self) -> None:
        self.connection = sqlite3.connect(str(self.db_path))

    def close(self) -> None:
        self.connection.close()

    def ensure_table(self, model: str, message: str, spec: Optional[Spec] = None) -> Sequence[FieldSpec]:
        spec = spec or load_spec(model, message)
        fields = tuple(_order_fields(message, spec.fields))
        table = spec.table_name
        conn = self.connection

        existing = self._table_columns(table)
        if not existing:
            columns_sql = ", ".join(f'"{field.name}" {_type_to_sql(field)}' for field in fields)
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns_sql})")
        else:
            for field in fields:
                if field.name not in existing:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN \"{field.name}\" {_type_to_sql(field)}"
                    )
        conn.commit()
        return fields

    def insert(self, model: str, message: str, record: dict, spec: Optional[Spec] = None) -> None:
        spec = spec or load_spec(model, message)
        fields = self.ensure_table(model, message, spec)
        table = spec.table_name
        columns = [field.name for field in fields]
        placeholders = ", ".join(["?"] * len(columns))
        prepared = _prepare_record(message, record)
        values = [_normalize_value(prepared.get(column)) for column in columns]
        column_names = ", ".join(f'"{col}"' for col in columns)
        sql = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"
        self.connection.execute(sql, values)
        self.connection.commit()

    def _table_columns(self, table: str) -> set[str]:
        cursor = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cursor.fetchone():
            return set()
        info = self.connection.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in info.fetchall()}



def init_db(path: Path | str) -> sqlite3.Connection:
    """Create (or connect to) a SQLite database for ingestion tests."""

    return sqlite3.connect(str(path))


def _ensure_table(conn: sqlite3.Connection, spec: Spec) -> Sequence[FieldSpec]:
    fields = tuple(_order_fields(spec.message, spec.fields))
    table = spec.table_name
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    exists = cursor.fetchone()
    if not exists:
        columns_sql = ", ".join(
            f'"{field.name}" {_type_to_sql(field)}' for field in fields
        )
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({columns_sql})")
    else:
        info = conn.execute(f"PRAGMA table_info({table})")
        existing_columns = {row[1] for row in info.fetchall()}
        for field in fields:
            if field.name not in existing_columns:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN \"{field.name}\" {_type_to_sql(field)}"
                )
    conn.commit()
    return fields


def _ensure_alias_table(conn: sqlite3.Connection, source: str, alias: str) -> None:
    if source == alias:
        return
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (alias,),
    ).fetchone()
    if exists:
        return
    conn.execute(f"CREATE VIEW {alias} AS SELECT * FROM {source}")
    conn.commit()


def _iter_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield stripped


def bulk_ingest_from_file(
    conn: sqlite3.Connection,
    model: str,
    message: str,
    path: Path,
) -> int:
    spec = load_spec(model, message)
    fields = _ensure_table(conn, spec)
    table = spec.table_name
    alias_table = f"{model.lower()}_{message.lower()}"
    _ensure_alias_table(conn, table, alias_table)
    inserted = 0

    placeholders = ", ".join(["?"] * len(fields))
    column_names = ", ".join(f'"{field.name}"' for field in fields)
    sql = f"INSERT INTO {table} ({column_names}) VALUES ({placeholders})"

    for raw_line in _iter_lines(path):
        try:
            record = parse_line(raw_line, model=model, message=message, spec=spec)
        except Exception:
            if message.upper() == "GTERI":
                try:
                    from .messages.gteri import parse_gteri as _parse_gteri

                    record = _parse_gteri(raw_line, device=model)
                except Exception:
                    continue
                if not record:
                    continue
            elif message.upper() == "GTINF":
                record = _relaxed_gtinf_parse(raw_line, spec)
                if not record:
                    continue
            else:
                continue

        prepared = _prepare_record(message, record)
        values = [_normalize_value(prepared.get(field.name)) for field in fields]
        conn.execute(sql, values)
        inserted += 1

    conn.commit()
    return inserted


__all__ = ["SQLiteIngestor", "bulk_ingest_from_file", "init_db"]

