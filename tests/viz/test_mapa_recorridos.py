from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from viz.mapa_recorridos import ensure_map_databases


def _setup_sources(tmp_path: Path) -> tuple[Path, str, str]:
    base_dir = tmp_path
    model = "gv350ceu"
    imei = "123456789012345"

    gteri_source = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_source)
    table_name = f"gteri_{model}"
    conn.execute(
        f"""
        CREATE TABLE "{table_name}" (
            imei TEXT,
            send_time TEXT,
            lat REAL,
            lon REAL,
            header TEXT,
            operador TEXT,
            tecnologia_celular TEXT,
            calidad_senal TEXT
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, send_time, lat, lon, header, operador, tecnologia_celular, calidad_senal) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (imei, "20251016080000", -33.45, -70.66, "+RESP:GTERI", "", "", ""),
            (imei, "20251016083000", -33.46, -70.65, "+BUFF:GTERI", "", "", ""),
            (imei, "20251017090000", -33.47, -70.64, "+RESP:GTERI", "", "", ""),
        ],
    )
    conn.commit()
    conn.close()

    gtinf_source = base_dir / f"gtinf_{model}.db"
    conn = sqlite3.connect(gtinf_source)
    table_name = f"gtinf_{model}"
    conn.execute(
        f"""
        CREATE TABLE "{table_name}" (
            imei TEXT,
            send_time TEXT,
            network_type INTEGER,
            csq REAL,
            csq_ber INTEGER,
            operador TEXT
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, send_time, network_type, csq, csq_ber, operador) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        [
            (imei, "20251016080000", 3, 160, None, "Claro"),
            (imei, "20251016083000", 3, 55, None, "Claro"),
            (imei, "20251017090000", 2, 10, 3, "Movistar"),
        ],
    )
    conn.commit()
    conn.close()

    return base_dir, model, imei


def test_ensure_map_databases_generates_enriched_copy(tmp_path: Path) -> None:
    base_dir, model, _ = _setup_sources(tmp_path)

    results = ensure_map_databases(model=model, base_dir=base_dir, reports=["gteri"])

    assert set(results) == {"gteri"}
    db_path = results["gteri"]
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        f'SELECT send_time, tecnologia_celular, calidad_senal, operador '
        f'FROM "gteri_{model}" ORDER BY send_time'
    ).fetchall()
    conn.close()

    summary = [tuple(row) for row in rows]
    assert summary == [
        ("20251016080000", "4G", "Excelente", "Claro"),
        ("20251016083000", "4G", "Buena", "Claro"),
        ("20251017090000", "3G", "Regular", "Movistar"),
    ]


def test_ensure_map_databases_warns_when_report_missing(tmp_path: Path) -> None:
    base_dir, model, _ = _setup_sources(tmp_path)

    with pytest.warns(RuntimeWarning):
        results = ensure_map_databases(model=model, base_dir=base_dir)

    assert "gteri" in results
    assert "gtfri" not in results


def test_ensure_map_databases_strict_raises_on_missing(tmp_path: Path) -> None:
    base_dir, model, _ = _setup_sources(tmp_path)

    with pytest.raises(FileNotFoundError):
        ensure_map_databases(model=model, base_dir=base_dir, reports=["gtfri"], strict=True)
