"""Generación de bases SQLite enriquecidas con información GTINF."""
from __future__ import annotations

import shutil
import sqlite3
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from src.ingestors.sqlite_records import ensure_db

from .utils import (
    CSQ_BER_CANDIDATES,
    CSQ_CANDIDATES,
    IMEI_CANDIDATES,
    MCC_CANDIDATES,
    MNC_CANDIDATES,
    NETWORK_TYPE_CANDIDATES,
    NETWORK_TYPE_MAP,
    OPERATOR_CANDIDATES,
    TIME_CANDIDATES,
    classify_signal,
    detect_table,
    first_existing,
    load_table_schema,
    normalize_operator,
    parse_datetime,
    safe_float,
    safe_int,
)


_MAX_TIME_DIFF_SECONDS = 60


@dataclass(frozen=True)
class _GTINFEntry:
    send_time: datetime
    network_label: str
    signal_quality: str
    signal_dbm: Optional[float]
    operator: str


def _best_entry(
    entries: Sequence[_GTINFEntry],
    times: Sequence[datetime],
    target: datetime,
) -> Optional[_GTINFEntry]:
    if not entries:
        return None
    index = bisect_left(times, target)
    candidates: List[_GTINFEntry] = []
    if 0 <= index < len(entries):
        candidates.append(entries[index])
    if index > 0:
        candidates.append(entries[index - 1])
    best: Optional[_GTINFEntry] = None
    best_delta: float = float("inf")
    for candidate in candidates:
        delta = abs((candidate.send_time - target).total_seconds())
        if delta > _MAX_TIME_DIFF_SECONDS:
            continue
        if best is None or delta < best_delta:
            best = candidate
            best_delta = delta
        elif delta == best_delta:
            if best.send_time > target >= candidate.send_time:
                best = candidate
    return best


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    existing = {row[1] for row in info}
    if column not in existing:
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')


def _load_gtinf_lookup(
    gtinf_path: Path, model: str, imei: str | None = None
) -> Dict[str, List[_GTINFEntry]]:
    if not gtinf_path.exists():
        return {}

    conn = ensure_db(gtinf_path)
    conn.row_factory = sqlite3.Row
    try:
        table = detect_table(conn, "gtinf", model, imei)
        columns = load_table_schema(conn, table)
        imei_col = first_existing(IMEI_CANDIDATES, columns)
        time_col = first_existing(TIME_CANDIDATES, columns)
        network_col = first_existing(NETWORK_TYPE_CANDIDATES, columns)
        if not imei_col or not time_col or not network_col:
            return {}

        csq_col = first_existing(CSQ_CANDIDATES, columns)
        ber_col = first_existing(CSQ_BER_CANDIDATES, columns)
        operator_col = first_existing(OPERATOR_CANDIDATES, columns)
        mcc_col = first_existing(MCC_CANDIDATES, columns)
        mnc_col = first_existing(MNC_CANDIDATES, columns)

        query_cols = {imei_col, time_col, network_col}
        if csq_col:
            query_cols.add(csq_col)
        if ber_col:
            query_cols.add(ber_col)
        if operator_col:
            query_cols.add(operator_col)
        if mcc_col:
            query_cols.add(mcc_col)
        if mnc_col:
            query_cols.add(mnc_col)

        select_clause = ", ".join(f'"{col}"' for col in query_cols)
        sql = f'SELECT {select_clause} FROM "{table}" ORDER BY "{time_col}"'

        lookup: Dict[str, List[_GTINFEntry]] = defaultdict(list)
        for row in conn.execute(sql):
            imei_raw = row[imei_col]
            imei_value = str(imei_raw).strip() if imei_raw not in (None, "") else None
            if not imei_value:
                continue
            send_dt = parse_datetime(row[time_col])
            if send_dt is None:
                continue
            raw_network = safe_int(row[network_col])
            network_label = NETWORK_TYPE_MAP.get(raw_network, "Desconocida")
            csq = safe_float(row[csq_col]) if csq_col else None
            csq_ber = safe_int(row[ber_col]) if ber_col else None
            quality, dbm = classify_signal(network_label, csq, csq_ber)
            operator_value = "Desconocido"
            if operator_col:
                raw_operator = row[operator_col]
                if raw_operator not in (None, ""):
                    operator_value = str(raw_operator).strip() or "Desconocido"
            if operator_value in ("", "Desconocido"):
                mcc_value = safe_int(row[mcc_col]) if mcc_col else None
                mnc_value = safe_int(row[mnc_col]) if mnc_col else None
                normalized = normalize_operator(mcc_value, mnc_value)
                if normalized != "Desconocido" or operator_value == "":
                    operator_value = normalized
            entry = _GTINFEntry(
                send_time=send_dt,
                network_label=network_label,
                signal_quality=quality,
                signal_dbm=dbm,
                operator=operator_value or "Desconocido",
            )
            lookup[imei_value].append(entry)
        return {key: sorted(values, key=lambda item: item.send_time) for key, values in lookup.items()}
    finally:
        conn.close()


def _choose_existing_path(base_dir: Path, *names: str) -> Path:
    for name in names:
        candidate = base_dir / name
        if candidate.exists():
            return candidate
    return base_dir / names[0]


def _resolve_output_path(base_dir: Path, report: str, model: str) -> Path:
    name = f"{report}_{model}_map.db"
    return base_dir / name


def ensure_enriched_database(
    *, report: str, model: str, base_dir: Path | str, imei: str | None = None
) -> Path:
    """Genera (si es necesario) una copia enriquecida de la base de recorridos."""

    base_path = Path(base_dir)
    report_clean = report.strip().lower()
    model_clean = model.strip().lower()
    output_path = _resolve_output_path(base_path, report_clean, model_clean)
    source_candidates = [
        output_path,
        base_path / f"{report_clean}_{model_clean}.db",
    ]
    source_path = next((path for path in source_candidates if path.exists()), None)
    if source_path is None:
        raise FileNotFoundError(output_path)

    gtinf_path = _choose_existing_path(
        base_path, f"gtinf_{model_clean}_map.db", f"gtinf_{model_clean}.db"
    )

    needs_copy = source_path != output_path
    needs_regen = needs_copy
    if not needs_regen and output_path.exists():
        src_mtime = source_path.stat().st_mtime
        out_mtime = output_path.stat().st_mtime
        gtinf_mtime = gtinf_path.stat().st_mtime if gtinf_path.exists() else None
        if out_mtime < src_mtime or (gtinf_mtime is not None and out_mtime < gtinf_mtime):
            needs_regen = True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if needs_regen:
        if needs_copy and output_path.exists():
            output_path.unlink()
        if needs_copy:
            shutil.copy2(source_path, output_path)

    conn = ensure_db(output_path)
    conn.row_factory = sqlite3.Row
    try:
        table = detect_table(conn, report_clean, model_clean, imei)
        _ensure_column(conn, table, "tecnologia_celular", "TEXT")
        _ensure_column(conn, table, "calidad_senal", "TEXT")
        _ensure_column(conn, table, "nivel_senal_dbm", "REAL")
        _ensure_column(conn, table, "operador", "TEXT")

        columns = load_table_schema(conn, table)
        imei_col = first_existing(IMEI_CANDIDATES, columns)
        time_col = first_existing(TIME_CANDIDATES, columns)
        if not imei_col or not time_col:
            return output_path
        # Aseguramos valores por defecto para evitar residuos de ejecuciones previas.
        conn.execute(
            f'UPDATE "{table}" SET "tecnologia_celular" = "Desconocida", '
            '"calidad_senal" = "Desconocida", "nivel_senal_dbm" = NULL'
        )
        conn.execute(f'UPDATE "{table}" SET "operador" = "Desconocido"')

        gtinf_lookup = _load_gtinf_lookup(gtinf_path, model_clean, imei)
        if gtinf_lookup:
            select_sql = (
                f'SELECT ROWID as __rowid__, "{imei_col}" as imei_value, '
                f'"{time_col}" as send_value FROM "{table}" ORDER BY "{time_col}"'
            )
            time_lookup: Dict[str, List[datetime]] = {
                key: [entry.send_time for entry in entries]
                for key, entries in gtinf_lookup.items()
            }
            updates: List[Tuple[str, str, Optional[float], int]] = []
            operator_updates: List[Tuple[str, int]] = []

            for row in conn.execute(select_sql):
                imei_val = row["imei_value"]
                imei_value = str(imei_val).strip() if imei_val not in (None, "") else None
                if not imei_value:
                    continue
                send_dt = parse_datetime(row["send_value"])
                if send_dt is None:
                    continue
                entries = gtinf_lookup.get(imei_value)
                times = time_lookup.get(imei_value)
                if not entries or not times:
                    continue
                chosen = _best_entry(entries, times, send_dt)
                if chosen is None:
                    continue
                updates.append(
                    (
                        chosen.network_label,
                        chosen.signal_quality,
                        chosen.signal_dbm,
                        row["__rowid__"],
                    )
                )
                if chosen.operator and chosen.operator not in {"", "Desconocido"}:
                    operator_updates.append((chosen.operator, row["__rowid__"]))

            if updates:
                conn.executemany(
                    f'UPDATE "{table}" SET "tecnologia_celular" = ?, '
                    f'"calidad_senal" = ?, "nivel_senal_dbm" = ? WHERE ROWID = ?',
                    updates,
                )
            if operator_updates:
                conn.executemany(
                    f'UPDATE "{table}" SET "operador" = ? '
                    "WHERE ROWID = ? AND (\"operador\" IS NULL OR TRIM(\"operador\") = '' OR \"operador\" = 'Desconocido')",
                    operator_updates,
                )

        columns = load_table_schema(conn, table)
        mcc_col = first_existing(MCC_CANDIDATES, columns)
        mnc_col = first_existing(MNC_CANDIDATES, columns)
        if mnc_col:
            select_sql = (
                f'SELECT ROWID as __rowid__, '
                f'"{mcc_col}" as mcc_value, "{mnc_col}" as mnc_value '
                f'FROM "{table}"'
            )
            fallback_updates: List[Tuple[str, int]] = []
            for row in conn.execute(select_sql):
                mcc = safe_int(row["mcc_value"]) if mcc_col else None
                mnc = safe_int(row["mnc_value"])
                operator = normalize_operator(mcc, mnc)
                if operator in ("", "Desconocido"):
                    continue
                fallback_updates.append((operator, row["__rowid__"]))
            if fallback_updates:
                conn.executemany(
                    f'UPDATE "{table}" SET "operador" = ? '
                    "WHERE ROWID = ? AND (\"operador\" IS NULL OR TRIM(\"operador\") = '' OR \"operador\" = 'Desconocido')",
                    fallback_updates,
                )
        conn.commit()
    finally:
        conn.close()

    return output_path



__all__ = ["ensure_enriched_database"]
