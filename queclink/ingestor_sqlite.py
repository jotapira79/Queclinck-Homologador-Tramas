"""SQLite ingestion utilities constrained by the YAML specs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .parser import FieldSpec, Spec, load_spec, parse_line, parse_gteri, parse_gtinf


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


def init_db(path: str | Path) -> sqlite3.Connection:
    """Return a SQLite connection ensuring parent directories exist."""

    db_path = Path(path)
    if db_path != Path(":memory:"):
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))


def _normalize_report_name(message: str) -> str:
    normalized = (message or "").strip().upper()
    if normalized and not normalized.startswith("GT"):
        normalized = f"GT{normalized}"
    return normalized


def _table_name(model: str, message: str) -> str:
    model_norm = (model or "").strip().lower()
    message_norm = (message or "").strip().lower()
    if model_norm and message_norm:
        return f"{model_norm}_{message_norm}"
    if model_norm:
        return f"{model_norm}_records"
    if message_norm:
        return f"{message_norm}_records"
    return "records"


def _ensure_table(conn: sqlite3.Connection, spec: Spec, table: str) -> Sequence[FieldSpec]:
    fields = spec.fields
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()

    if existing is None:
        columns_sql = ", ".join(
            f'"{field.name}" {_type_to_sql(field)}' for field in fields
        )
        conn.execute(
            f'CREATE TABLE IF NOT EXISTS "{table}" ({columns_sql})'
        )
    else:
        info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        existing_columns = {row[1] for row in info}
        for field in fields:
            if field.name not in existing_columns:
                conn.execute(
                    f'ALTER TABLE "{table}" ADD COLUMN "{field.name}" '
                    f"{_type_to_sql(field)}"
                )
    conn.commit()
    return fields


def _iter_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                yield line


def bulk_ingest_from_file(
    conn: sqlite3.Connection,
    model: str,
    message: str,
    input_path: str | Path,
) -> int:
    """Parse Queclink lines from a file and insert them into SQLite."""

    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(path)

    model_clean = (model or "").strip()
    if not model_clean:
        raise ValueError("Model name is required")

    normalized_message = _normalize_report_name(message)
    spec = load_spec(model_clean.upper(), normalized_message)
    model_lower = model_clean.lower()
    if normalized_message == "GTERI":
        table = f"{model_lower}_{normalized_message.lower()}"
    elif normalized_message == "GTINF":
        table = f"{normalized_message.lower()}_{model_lower}"
    else:
        table = _table_name(model_clean, message)
    fields = _ensure_table(conn, spec, table)

    columns = [field.name for field in fields]
    placeholders = ", ".join(["?"] * len(columns))
    column_names = ", ".join(f'"{col}"' for col in columns)

    inserted = 0
    for line in _iter_lines(path):
        try:
            record = parse_line(
                line,
                model=model_clean.upper(),
                message=normalized_message,
                spec=spec,
            )
        except Exception:
            if normalized_message == "GTERI":
                record = parse_gteri(line, device=model_clean)
            elif normalized_message == "GTINF":
                record = parse_gtinf(line, device=model_clean)
            else:
                continue
            if not record:
                continue

        report_value = record.get("report") or record.get("message")
        report = str(report_value or "").strip().upper()
        if normalized_message == "GTINF" and report == "INF":
            report = normalized_message
        if normalized_message and report and report != normalized_message:
            continue

        values = [
            _normalize_value(
                record.get(column)
                if column in record
                else record.get(f"{column}_raw")
            )
            for column in columns
        ]
        conn.execute(
            f'INSERT INTO "{table}" ({column_names}) VALUES ({placeholders})',
            values,
        )
        inserted += 1

    conn.commit()
    return inserted


@dataclass
class SQLiteIngestor:
    db_path: Path

    def __post_init__(self) -> None:
        self.connection = sqlite3.connect(str(self.db_path))

    def close(self) -> None:
        self.connection.close()

    def ensure_table(self, model: str, message: str, spec: Optional[Spec] = None) -> Sequence[FieldSpec]:
        spec = spec or load_spec(model, message)
        fields = spec.fields
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
        values = [_normalize_value(record.get(column)) for column in columns]
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


__all__ = ["SQLiteIngestor", "init_db", "bulk_ingest_from_file"]

