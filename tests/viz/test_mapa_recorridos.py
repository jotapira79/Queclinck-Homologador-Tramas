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


def _setup_gtfri_sources(tmp_path: Path) -> tuple[Path, str, str]:
    base_dir = tmp_path
    model = "gv75lau"
    imei = "866314060583471"

    gtfri_source = base_dir / f"gtfri_{model}.db"
    conn = sqlite3.connect(gtfri_source)
    table_name = f"gtfri_{model}"
    conn.execute(
        f"""
        CREATE TABLE "{table_name}" (
            imei TEXT,
            gnss_utc_time TEXT,
            latitude REAL,
            longitude REAL,
            header TEXT
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, gnss_utc_time, latitude, longitude, header) '
        "VALUES (?, ?, ?, ?, ?)",
        [
            (imei, "20251029091530", -33.437200, -70.650123, "+RESP:GTFRI"),
            (imei, "20251029092000", -33.437100, -70.650100, "+BUFF:GTFRI"),
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
            operador TEXT,
            mcc INTEGER,
            mnc INTEGER
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, send_time, network_type, csq, csq_ber, operador, mcc, mnc) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (imei, "20251029091530", 3, 160.0, None, "WOM", None, None),
            (imei, "20251029092000", 2, 10.0, 6, "", 730, 3),
        ],
    )
    conn.commit()
    conn.close()

    return base_dir, model, imei


def test_ensure_map_databases_enriches_gtfri_gv75lau(tmp_path: Path) -> None:
    base_dir, model, _ = _setup_gtfri_sources(tmp_path)

    results = ensure_map_databases(model=model, base_dir=base_dir, reports=["gtfri"])

    assert set(results) == {"gtfri"}
    db_path = results["gtfri"]
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        f'SELECT gnss_utc_time, tecnologia_celular, calidad_senal, nivel_senal_dbm, operador '
        f'FROM "gtfri_{model}" ORDER BY gnss_utc_time'
    ).fetchall()
    conn.close()

    summary = [tuple(row) for row in rows]
    assert summary == [
        ("20251029091530", "4G", "Excelente", 20.0, "WOM"),
        ("20251029092000", "3G", "Regular", -93.0, "Claro"),
    ]


def _setup_gv37_sources(tmp_path: Path) -> tuple[Path, str, str]:
    base_dir = tmp_path
    model = "gv37cau"
    imei = "868487004398475"

    gteri_source = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_source)
    table_name = f"gteri_{model}"
    conn.execute(
        f"""
        CREATE TABLE "{table_name}" (
            imei TEXT,
            gnss_utc_time TEXT,
            latitude_deg REAL,
            longitude_deg REAL,
            header TEXT
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, gnss_utc_time, latitude_deg, longitude_deg, header) '
        "VALUES (?, ?, ?, ?, ?)",
        [
            (imei, "20251101090000", -33.45, -70.66, "+RESP:GTERI"),
            (imei, "20251101091500", -33.46, -70.65, "+BUFF:GTERI"),
        ],
    )
    conn.commit()
    conn.close()

    gtfri_source = base_dir / f"gtfri_{model}.db"
    conn = sqlite3.connect(gtfri_source)
    table_name = f"gtfri_{model}"
    conn.execute(
        f"""
        CREATE TABLE "{table_name}" (
            imei TEXT,
            gnss_utc_time TEXT,
            latitude_deg REAL,
            longitude_deg REAL,
            header TEXT
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, gnss_utc_time, latitude_deg, longitude_deg, header) '
        "VALUES (?, ?, ?, ?, ?)",
        [
            (imei, "20251101120000", -33.47, -70.64, "+RESP:GTFRI"),
            (imei, "20251101121500", -33.48, -70.63, "+BUFF:GTFRI"),
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
            operador TEXT,
            mcc INTEGER,
            mnc INTEGER
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "{table_name}" (imei, send_time, network_type, csq, csq_ber, operador, mcc, mnc) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (imei, "20251101090000", 3, 160.0, None, "WOM", None, None),
            (imei, "20251101091500", 2, 12.0, 5, "", 730, 3),
            (imei, "20251101120000", 3, 155.0, None, "Entel", None, None),
            (imei, "20251101121500", 1, 24.0, None, "", 730, 2),
        ],
    )
    conn.commit()
    conn.close()

    return base_dir, model, imei


def test_ensure_map_databases_enriches_gv37cau_gteri(tmp_path: Path) -> None:
    base_dir, model, _ = _setup_gv37_sources(tmp_path)

    results = ensure_map_databases(model=model, base_dir=base_dir, reports=["gteri"])

    assert set(results) == {"gteri"}
    db_path = results["gteri"]
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        f'SELECT gnss_utc_time, tecnologia_celular, calidad_senal, nivel_senal_dbm, operador '
        f'FROM "gteri_{model}" ORDER BY gnss_utc_time'
    ).fetchall()
    conn.close()

    summary = [tuple(row) for row in rows]
    assert summary == [
        ("20251101090000", "4G", "Excelente", 20.0, "WOM"),
        ("20251101091500", "3G", "Buena", -89.0, "Claro"),
    ]


def test_ensure_map_databases_enriches_gv37cau_gtfri(tmp_path: Path) -> None:
    base_dir, model, _ = _setup_gv37_sources(tmp_path)

    results = ensure_map_databases(model=model, base_dir=base_dir, reports=["gtfri"])

    assert set(results) == {"gtfri"}
    db_path = results["gtfri"]
    assert db_path.exists()

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        f'SELECT gnss_utc_time, tecnologia_celular, calidad_senal, nivel_senal_dbm, operador '
        f'FROM "gtfri_{model}" ORDER BY gnss_utc_time'
    ).fetchall()
    conn.close()

    summary = [tuple(row) for row in rows]
    assert summary == [
        ("20251101120000", "4G", "Excelente", 15.0, "Entel"),
        ("20251101121500", "2G", "Excelente", -65.0, "Movistar"),
    ]
