import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from viz.mapa_recorridos import (
    build_points,
    render_interactive_map,
    InfoRecord,
    LocationPoint,
    _associate_info,
    _detect_report_kind,
    _filter_points,
    _normalize_operator,
    _safe_int,
)
from viz.enriched_db import ensure_enriched_database


def test_safe_int_parses_leading_zero_decimal():
    assert _safe_int("0730") == 730
    assert _safe_int("0009") == 9


def test_safe_int_keeps_base_prefix_support():
    assert _safe_int("0x10") == 16


def test_normalize_operator_known_chile_carriers():
    assert _normalize_operator(730, 2) == "Movistar"
    assert _normalize_operator(730, 9) == "WOM"
    assert _normalize_operator(None, 9) == "WOM"
    assert _normalize_operator(472, 9) == "Desconocido"


def test_normalize_operator_requires_mnc():
    assert _normalize_operator(730, None) == "Desconocido"


def _make_point(offset_seconds: int, *, operator: str = "Entel", network: str = "Desconocida") -> LocationPoint:
    base = datetime(2025, 10, 10, 0, 0, 0)
    return LocationPoint(
        lat=0.0,
        lon=0.0,
        send_time=base + timedelta(seconds=offset_seconds),
        imei="123456789012345",
        source="gteri",
        operator=operator,
        network_label=network,
    )


def _make_info(
    offset_seconds: int,
    *,
    label: str,
    csq: float,
    csq_ber: int | None = None,
    operator: str = "Desconocido",
) -> InfoRecord:
    base = datetime(2025, 10, 10, 0, 0, 0)
    return InfoRecord(
        imei="123456789012345",
        send_time=base + timedelta(seconds=offset_seconds),
        network_label=label,
        raw_network_value=None,
        csq=csq,
        csq_ber=csq_ber,
        operator=operator,
    )


def _prepare_sample_databases(tmp_path: Path) -> Path:
    model = "gv350ceu"
    imei = "123456789012345"
    base_dir = tmp_path

    gteri_path = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_path)
    conn.execute(
        f'CREATE TABLE "gteri_{model}" ('
        'imei TEXT, send_time TEXT, lat REAL, lon REAL, mcc TEXT, mnc TEXT)'
    )
    conn.executemany(
        f'INSERT INTO "gteri_{model}" (imei, send_time, lat, lon, mcc, mnc) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        [
            (imei, "20251010000000", -33.45, -70.66, "0730", "0002"),
            (imei, "20251010000040", -33.46, -70.65, "0730", "0002"),
            (imei, "20251010010130", -33.47, -70.64, "0730", "0002"),
        ],
    )
    conn.commit()
    conn.close()

    gtinf_path = base_dir / f"gtinf_{model}.db"
    conn = sqlite3.connect(gtinf_path)
    conn.execute(
        f'CREATE TABLE "gtinf_{model}" ('
        'imei TEXT, send_time TEXT, network_type INTEGER, csq REAL, csq_ber INTEGER)'
    )
    conn.executemany(
        f'INSERT INTO "gtinf_{model}" (imei, send_time, network_type, csq, csq_ber) '
        'VALUES (?, ?, ?, ?, ?)',
        [
            (imei, "202510100000", 3, 160, None),
            (imei, "202510100120", 1, 12, None),
        ],
    )
    conn.commit()
    conn.close()

    return base_dir


def test_detect_report_kind_identifies_buffer_and_resp():
    assert _detect_report_kind({"payload": "+BUFF:GTERI,..."}) == "BUFFER"
    assert _detect_report_kind({"header": "+RESP:GTFRI"}) == "RESP"
    assert _detect_report_kind({}) == "RESP"


def test_associate_info_uses_latest_previous_record():
    points = [
        _make_point(0),
        _make_point(20),
        _make_point(70),
        _make_point(120),
    ]
    infos = [
        _make_info(0, label="3G", csq=15, csq_ber=3),
        _make_info(100, label="4G", csq=160),
    ]

    _associate_info(points, infos)

    assert [point.network_label for point in points] == ["3G", "3G", "4G", "4G"]
    assert [point.signal_quality for point in points] == [
        "Buena",
        "Buena",
        "Excelente",
        "Excelente",
    ]


def test_associate_info_ignores_info_farther_than_one_minute():
    points = [_make_point(0), _make_point(10)]
    infos = [_make_info(200, label="2G", csq=25)]

    _associate_info(points, infos)

    assert points[0].network_label == "Desconocida"
    assert points[0].signal_quality == "Desconocida"
    assert points[1].network_label == "Desconocida"
    assert points[1].signal_quality == "Desconocida"


def test_associate_info_updates_operator_when_available():
    points = [_make_point(0, operator="Desconocido")]
    infos = [_make_info(0, label="3G", csq=15, operator="Claro")]

    _associate_info(points, infos)

    assert points[0].operator == "Claro"


def test_filter_points_accepts_all_keyword_for_every_filter():
    points = [
        _make_point(0, operator="Claro", network="2G"),
        _make_point(60, operator="Entel", network="3G"),
        _make_point(120, operator="Movistar", network="4G"),
    ]

    assert _filter_points(points, operators=["All"]) == points
    assert _filter_points(points, networks=["ALL"]) == points
    assert _filter_points(points, report_types=["All"]) == points
    assert _filter_points(points, report_types=["AMBOS"]) == points
    assert _filter_points(points, day="all") == points


def test_filter_points_accepts_compact_day_and_todos_alias():
    same_day = _make_point(0, operator="Claro", network="3G")
    next_day = _make_point(86400, operator="Entel", network="2G")
    points = [same_day, next_day]

    assert _filter_points(points, day="20251010") == [same_day]
    assert _filter_points(points, report_types=["todos"]) == points


def test_filter_points_day_filter_has_priority():
    day_one_point = _make_point(0, operator="Claro", network="3G")
    day_two_point = _make_point(86400, operator="Claro", network="3G")
    extra_day_two = _make_point(86400 + 60, operator="Entel", network="2G")

    points = [day_one_point, day_two_point, extra_day_two]

    result = _filter_points(
        points,
        day="2025-10-10",
        operators=["Claro"],
        networks=["3G"],
    )

    assert result == [day_one_point]


def test_filter_points_respects_report_types():
    buffer_point = _make_point(0, operator="Claro", network="3G")
    buffer_point.report_kind = "BUFFER"
    resp_point = _make_point(60, operator="Entel", network="4G")
    resp_point.report_kind = "RESP"

    points = [buffer_point, resp_point]

    assert _filter_points(points, report_types=["BUFFER"]) == [buffer_point]
    assert _filter_points(points, report_types=["RESP"]) == [resp_point]
    assert _filter_points(points, day="2025-10-10", report_types=["BUFFER"], operators=["Claro"]) == [buffer_point]


def test_filter_points_operator_and_network_depend_on_day():
    points = [
        _make_point(0, operator="Claro", network="3G"),
        _make_point(86400, operator="Entel", network="4G"),
    ]

    assert _filter_points(points, operators=["Claro"]) == [points[0]]
    assert _filter_points(points, networks=["3G"]) == [points[0]]


def test_filter_points_returns_empty_when_combination_not_found():
    points = [
        _make_point(0, operator="Claro", network="3G"),
        _make_point(60, operator="Claro", network="3G"),
    ]

    assert _filter_points(
        points,
        day="2025-10-10",
        operators=["Entel"],
        networks=["4G"],
    ) == []


def test_enriched_database_creates_columns_and_values(tmp_path: Path):
    base_dir = _prepare_sample_databases(tmp_path)

    enriched_path = ensure_enriched_database(
        report="gteri", model="gv350ceu", base_dir=base_dir
    )
    assert enriched_path.exists()

    conn = sqlite3.connect(enriched_path)
    try:
        rows = conn.execute(
            'SELECT tecnologia_celular, calidad_senal, nivel_senal_dbm, operador '
            'FROM "gteri_gv350ceu" ORDER BY send_time'
        ).fetchall()
    finally:
        conn.close()

    tecnologias = [row[0] for row in rows]
    calidades = [row[1] for row in rows]
    niveles = [row[2] for row in rows]
    operadores = [row[3] for row in rows]

    assert tecnologias == ["4G", "4G", "2G"]
    assert calidades == ["Excelente", "Excelente", "Buena"]
    assert niveles[0] == pytest.approx(20.0)
    assert niveles[2] == pytest.approx(-89.0)
    assert operadores == ["Movistar", "Movistar", "Movistar"]


def test_build_points_uses_enriched_database(tmp_path: Path):
    base_dir = _prepare_sample_databases(tmp_path)
    # Genera la base enriquecida y asegura reutilización posterior
    ensure_enriched_database(report="gteri", model="gv350ceu", base_dir=base_dir)

    points = build_points(
        model="gv350ceu",
        imei="123456789012345",
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 3
    assert [p.network_label for p in points] == ["4G", "4G", "2G"]
    assert [p.signal_quality for p in points] == ["Excelente", "Excelente", "Buena"]
    assert [p.operator for p in points] == ["Movistar"] * 3
    assert points[0].lat == pytest.approx(-33.45)


def test_build_points_accepts_whitespace_imei(tmp_path: Path):
    base_dir = tmp_path
    model = "gv310lau"
    imei = "868589060824888"

    gteri_path = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_path)
    conn.execute(
        f"""
        CREATE TABLE "gteri_{model}" (
            imei TEXT,
            send_time TEXT,
            lat REAL,
            lon REAL,
            mcc TEXT,
            mnc TEXT,
            report_type TEXT
        )
        """
    )
    conn.execute(
        f'INSERT INTO "gteri_{model}" (imei, send_time, lat, lon, mcc, mnc, report_type) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (f"  {imei}\r\n", "202401020304", -33.45, -70.66, "0730", "0002", "GTERI"),
    )
    conn.commit()
    conn.close()

    gtinf_path = base_dir / f"gtinf_{model}.db"
    conn = sqlite3.connect(gtinf_path)
    conn.execute(
        f"""
        CREATE TABLE "gtinf_{model}" (
            imei TEXT,
            send_time TEXT,
            network_type INTEGER,
            csq REAL,
            csq_ber INTEGER
        )
        """
    )
    conn.execute(
        f'INSERT INTO "gtinf_{model}" (imei, send_time, network_type, csq, csq_ber) '
        'VALUES (?, ?, ?, ?, ?)',
        (f"\t{imei}   ", "202401020304", 3, 160, None),
    )
    conn.commit()
    conn.close()

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 1
    point = points[0]
    assert point.lat == pytest.approx(-33.45)
    assert point.operator == "Movistar"
    assert point.network_label == "4G"
    assert point.signal_quality == "Excelente"
    assert points[0].lon == pytest.approx(-70.66)


def test_build_points_accepts_lng_column(tmp_path: Path):
    base_dir = tmp_path
    model = "gv310lau"
    imei = "868589060824888"

    gteri_path = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_path)
    conn.execute(
        f"""
        CREATE TABLE "gteri_{model}" (
            imei TEXT,
            send_time TEXT,
            latitude REAL,
            lng REAL,
            mnc TEXT
        )
        """
    )
    conn.execute(
        f'INSERT INTO "gteri_{model}" (imei, send_time, latitude, lng, mnc) '
        'VALUES (?, ?, ?, ?, ?)',
        (imei, "202401020304", -33.45, -70.66, "0002"),
    )
    conn.commit()
    conn.close()

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 1
    point = points[0]
    assert point.lat == pytest.approx(-33.45)
    assert point.lon == pytest.approx(-70.66)
    assert point.operator == "Movistar"


def test_build_points_accepts_latitude_decimal_column(tmp_path: Path):
    base_dir = tmp_path
    model = "gv310lau"
    imei = "868589060824888"

    gteri_path = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_path)
    conn.execute(
        f"""
        CREATE TABLE "gteri_{model}" (
            imei TEXT,
            send_time TEXT,
            latitude_decimal REAL,
            longitude_decimal REAL,
            mnc TEXT
        )
        """
    )
    conn.execute(
        f'INSERT INTO "gteri_{model}" (imei, send_time, latitude_decimal, longitude_decimal, mnc) '
        'VALUES (?, ?, ?, ?, ?)',
        (imei, "202401020304", -33.45, -70.66, "0002"),
    )
    conn.commit()
    conn.close()

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 1
    point = points[0]
    assert point.lat == pytest.approx(-33.45)
    assert point.lon == pytest.approx(-70.66)
    assert point.operator == "Movistar"


def test_build_points_swaps_coordinates_without_mcc(tmp_path: Path):
    model = "gv350ceu"
    imei = "987654321098765"
    base_dir = tmp_path

    gteri_path = base_dir / f"gteri_{model}.db"
    conn = sqlite3.connect(gteri_path)
    conn.execute(
        f'CREATE TABLE "gteri_{model}" ('
        'imei TEXT, send_time TEXT, lat REAL, lon REAL, mnc TEXT)'
    )
    conn.executemany(
        f'INSERT INTO "gteri_{model}" (imei, send_time, lat, lon, mnc) '
        'VALUES (?, ?, ?, ?, ?)',
        [
            (imei, "202510100000", -70.66, -33.45, "0002"),
            (imei, "202510100500", -70.65, -33.46, "0002"),
        ],
    )
    conn.commit()
    conn.close()

    ensure_enriched_database(report="gteri", model=model, base_dir=base_dir)

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 2
    assert all(-40.0 < p.lat < -20.0 for p in points)
    assert all(-80.0 < p.lon < -60.0 for p in points)


def test_build_points_uses_existing_map_databases(tmp_path: Path):
    model = "gv350ceu"
    imei = "123456789012345"
    base_dir = tmp_path

    gteri_map_path = base_dir / f"gteri_{model}_map.db"
    conn = sqlite3.connect(gteri_map_path)
    conn.execute(
        f"""
        CREATE TABLE "gteri_{model}" (
            imei TEXT,
            send_time TEXT,
            lat REAL,
            lon REAL,
            mcc TEXT,
            mnc TEXT,
            report_type TEXT,
            tecnologia_celular TEXT,
            calidad_senal TEXT,
            nivel_senal_dbm REAL,
            operador TEXT
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "gteri_{model}" (imei, send_time, lat, lon, mcc, mnc, report_type, tecnologia_celular, calidad_senal, nivel_senal_dbm, operador) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (
                imei,
                "20251010000000",
                -33.45,
                -70.66,
                "0730",
                "0002",
                "+BUFF:GTERI",
                "4G",
                "Excelente",
                18.0,
                "Movistar",
            ),
            (
                imei,
                "20251010010130",
                -33.46,
                -70.65,
                "0730",
                "0002",
                "+RESP:GTERI",
                "3G",
                "Buena",
                -85.0,
                "Movistar",
            ),
        ],
    )
    conn.commit()
    conn.close()

    gtinf_map_path = base_dir / f"gtinf_{model}_map.db"
    conn = sqlite3.connect(gtinf_map_path)
    conn.execute(
        f"""
        CREATE TABLE "gtinf_{model}" (
            imei TEXT,
            send_time TEXT,
            network_type INTEGER,
            csq REAL,
            csq_ber INTEGER
        )
        """
    )
    conn.executemany(
        f'INSERT INTO "gtinf_{model}" (imei, send_time, network_type, csq, csq_ber) '
        'VALUES (?, ?, ?, ?, ?)',
        [
            (imei, "20251010000000", 3, 160, None),
            (imei, "20251010010130", 2, 90, None),
        ],
    )
    conn.commit()
    conn.close()

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 2
    assert {p.report_kind for p in points} == {"BUFFER", "RESP"}
    assert all(p.operator == "Movistar" for p in points)
    assert {p.network_label for p in points} == {"4G", "3G"}


def test_render_interactive_map_includes_all_filters(tmp_path: Path):
    pytest.importorskip("folium")
    base_dir = _prepare_sample_databases(tmp_path)
    ensure_enriched_database(report="gteri", model="gv350ceu", base_dir=base_dir)

    points = build_points(
        model="gv350ceu",
        imei="123456789012345",
        base_dir=base_dir,
        reports=["gteri"],
    )

    output_html = tmp_path / "mapa.html"
    render_interactive_map(points, output_html)

    html = output_html.read_text(encoding="utf-8")
    assert 'data-filter-panel="interactive-filters"' in html
    assert "Filtros" in html
    assert "2025-10-10" in html
    assert ">Operador<" in html
    assert ">Tecnología<" in html
    assert 'id="FilterPanel_operator" style=' in html
    operator_fragment = html.split('id="FilterPanel_operator"', 1)[1].split('>', 1)[0]
    assert "disabled" not in operator_fragment
    report_fragment = html.split('id="FilterPanel_report"', 1)[1].split('</select>', 1)[0]
    assert 'value="AMBOS"' in report_fragment
    assert 'value="BUFFER"' in report_fragment
    assert 'value="RESP"' in report_fragment
    assert 'value="All"' not in report_fragment
