import sqlite3
from pathlib import Path

import pytest

from viz.query import fetch_points_by_day


def build_temp_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE gteri_records (
                lon REAL,
                lat REAL,
                gnss_utc TEXT,
                is_buff INTEGER,
                report_type TEXT,
                imei TEXT
            );
            """
        )
        rows = [
            ( -70.6500, -33.4372, "20230801060000", 0, "10", "123"),  # 02:00 local (UTC-4)
            ( -70.6510, -33.4380, "20230801130000", 1, "10", "123"),
            ( -70.6520, -33.4390, "20230731230000", 0, "10", "123"),  # 19:00 local previous day
            ( -70.6530, -33.4400, "20230802030000", 0, "10", "999"),
        ]
        conn.executemany(
            "INSERT INTO gteri_records(lon, lat, gnss_utc, is_buff, report_type, imei) VALUES(?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def test_fetch_points_by_day_filters_local_date(tmp_path):
    db_path = build_temp_db(tmp_path)
    points = fetch_points_by_day(str(db_path), "123", "2023-08-01")
    assert len(points) == 2
    for p in points:
        tzinfo = p["dt_local"].tzinfo
        zone_name = getattr(tzinfo, "zone", None) or getattr(tzinfo, "key", None)
        assert zone_name == "America/Santiago"
        assert p["dt_local"].date().isoformat() == "2023-08-01"
    assert points[0]["is_buffer"] is False
    assert points[1]["is_buffer"] is True


def test_fetch_points_by_day_orden(tmp_path):
    db_path = build_temp_db(tmp_path)
    points = fetch_points_by_day(str(db_path), "123", "2023-08-01")
    times = [p["dt_local"] for p in points]
    assert times == sorted(times)


def test_fetch_points_by_day_detects_alt_table(tmp_path):
    db_path = tmp_path / "alt.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE records (
                lon REAL,
                lat REAL,
                gnss_utc TEXT,
                is_buff INTEGER,
                report_type TEXT,
                imei TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO records(lon, lat, gnss_utc, is_buff, report_type, imei) VALUES(?,?,?,?,?,?)",
            (-70.7, -33.4, "20230801060000", 0, "10", "456"),
        )
        conn.commit()
    finally:
        conn.close()

    points = fetch_points_by_day(str(db_path), "456", "2023-08-01")
    assert len(points) == 1


def test_fetch_points_by_day_missing_table(tmp_path):
    db_path = tmp_path / "missing.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE foo (
                lon REAL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(RuntimeError) as excinfo:
        fetch_points_by_day(str(db_path), "123", "2023-08-01")

    assert "Tablas disponibles: foo" in str(excinfo.value)
