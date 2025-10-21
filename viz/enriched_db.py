"""Generación de bases SQLite enriquecidas con información GTINF."""
from __future__ import annotations

import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.ingestors.sqlite_records import ensure_db

from .utils import (
    CSQ_BER_CANDIDATES,
    CSQ_CANDIDATES,
    IMEI_CANDIDATES,
    MCC_CANDIDATES,
    MNC_CANDIDATES,
    NETWORK_TYPE_CANDIDATES,
    NETWORK_TYPE_MAP,
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


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    existing = {row[1] for row in info}
    if column not in existing:
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}')


def _load_gtinf_lookup(
    gtinf_path: Path, model: str, imei: str | None = None
) -> Dict[str, List[Tuple[datetime, str, str, Optional[float]]]]:
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

        query_cols = {imei_col, time_col, network_col}
        if csq_col:
            query_cols.add(csq_col)
        if ber_col:
            query_cols.add(ber_col)
        select_clause = ", ".join(f'"{col}"' for col in query_cols)
        sql = f'SELECT {select_clause} FROM "{table}" ORDER BY "{time_col}"'

        lookup: Dict[str, List[Tuple[datetime, str, str, Optional[float]]]] = defaultdict(list)
        for row in conn.execute(sql):
            imei_raw = row[imei_col]
            imei = str(imei_raw).strip() if imei_raw not in (None, "") else None
            if not imei:
                continue
            send_dt = parse_datetime(row[time_col])
            if send_dt is None:
                continue
            raw_network = safe_int(row[network_col])
            network_label = NETWORK_TYPE_MAP.get(raw_network, "Desconocida")
            csq = safe_float(row[csq_col]) if csq_col else None
            csq_ber = safe_int(row[ber_col]) if ber_col else None
            quality, dbm = classify_signal(network_label, csq, csq_ber)
            lookup[imei].append((send_dt, network_label, quality, dbm))
        return {key: sorted(values, key=lambda item: item[0]) for key, values in lookup.items()}
    finally:
        conn.close()


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
    source_path = base_path / f"{report_clean}_{model_clean}.db"
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    output_path = _resolve_output_path(base_path, report_clean, model_clean)
    gtinf_path = base_path / f"gtinf_{model_clean}.db"

    needs_regen = True
    if output_path.exists():
        src_mtime = source_path.stat().st_mtime
        out_mtime = output_path.stat().st_mtime
        gtinf_mtime = gtinf_path.stat().st_mtime if gtinf_path.exists() else None
        if out_mtime >= src_mtime and (gtinf_mtime is None or out_mtime >= gtinf_mtime):
            needs_regen = False

    if needs_regen:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
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
            if not gtinf_lookup:
                conn.commit()
            else:
                select_sql = (
                    f'SELECT ROWID as __rowid__, "{imei_col}" as imei_value, '
                    f'"{time_col}" as send_value FROM "{table}" ORDER BY "{time_col}"'
                )
                updates: List[Tuple[str, str, Optional[float], int]] = []
                positions: Dict[str, int] = defaultdict(int)

                for row in conn.execute(select_sql):
                    imei_val = row["imei_value"]
                    imei = str(imei_val).strip() if imei_val not in (None, "") else None
                    if not imei:
                        continue
                    send_dt = parse_datetime(row["send_value"])
                    if send_dt is None:
                        continue
                    infos = gtinf_lookup.get(imei)
                    if not infos:
                        continue
                    idx = positions.get(imei, 0)
                    while idx < len(infos) and infos[idx][0] <= send_dt:
                        idx += 1
                    positions[imei] = idx
                    if idx == 0:
                        continue
                    latest = infos[idx - 1]
                    network_label = latest[1]
                    signal_quality = latest[2]
                    signal_dbm = latest[3]
                    updates.append((network_label, signal_quality, signal_dbm, row["__rowid__"]))

                if updates:
                    conn.executemany(
                        f'UPDATE "{table}" SET "tecnologia_celular" = ?, '
                        f'"calidad_senal" = ?, "nivel_senal_dbm" = ? WHERE ROWID = ?',
                        updates,
                    )

            # Actualizamos el operador utilizando MCC/MNC
            columns = load_table_schema(conn, table)
            mcc_col = first_existing(MCC_CANDIDATES, columns)
            mnc_col = first_existing(MNC_CANDIDATES, columns)
            if mnc_col:
                select_sql = (
                    f'SELECT ROWID as __rowid__, '
                    f'"{mcc_col}" as mcc_value, "{mnc_col}" as mnc_value '
                    f'FROM "{table}"'
                )
                operator_updates: List[Tuple[str, int]] = []
                for row in conn.execute(select_sql):
                    mcc = safe_int(row["mcc_value"]) if mcc_col else None
                    mnc = safe_int(row["mnc_value"])
                    operator = normalize_operator(mcc, mnc)
                    operator_updates.append((operator, row["__rowid__"]))
                if operator_updates:
                    conn.executemany(
                        f'UPDATE "{table}" SET "operador" = ? WHERE ROWID = ?',
                        operator_updates,
                    )
            conn.commit()
        finally:
            conn.close()

    return output_path


__all__ = ["ensure_enriched_database"]
