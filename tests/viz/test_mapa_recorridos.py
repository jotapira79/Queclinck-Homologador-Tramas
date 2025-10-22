import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from viz.mapa_recorridos import (
    InfoRecord,
    LocationPoint,
    _associate_info,
    _filter_points,
    _normalize_operator,
    _report_kind_from_header,
    _safe_int,
    build_points,
    render_interactive_map,
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


def test_report_kind_from_header_detects_buffer_and_resp():
    assert _report_kind_from_header("+BUFF:GTERI") == "BUFFER"
    assert _report_kind_from_header("+RESP:GTFRI") == "RESP"
    assert _report_kind_from_header("other") == "RESP"


def _make_point(
    offset_seconds: int,
    *,
    operator: str = "Entel",
    network: str = "Desconocida",
) -> LocationPoint:
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
    assert _filter_points(points, day="Todos") == points


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
    assert _filter_points(
        points,
        day="2025-10-10",
        report_types=["BUFFER"],
        operators=["Claro"],
    ) == [buffer_point]


def _prepare_map_databases(tmp_path: Path) -> tuple[Path, str, str]:
    base_dir = tmp_path
    model = "gv350ceu"
    imei = "123456789012345"
    map_path = base_dir / f"gteri_{model}_map.db"
    conn = sqlite3.connect(map_path)
    conn.execute(
        f"""
        CREATE TABLE "gteri_{model}" (
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
        f'INSERT INTO "gteri_{model}" (imei, send_time, lat, lon, header, operador, tecnologia_celular, calidad_senal) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (
                imei,
                "20251016080000",
                -33.45,
                -70.66,
                "+RESP:GTERI",
                "",
                "",
                "",
            ),
            (
                imei,
                "20251016083000",
                -33.46,
                -70.65,
                "+BUFF:GTERI",
                "",
                "",
                "",
            ),
            (
                imei,
                "20251017090000",
                -33.47,
                -70.64,
                "+RESP:GTERI",
                "",
                "",
                "",
            ),
        ],
    )
    conn.commit()
    conn.close()

    gtinf_path = base_dir / f"gtinf_{model}_map.db"
    conn = sqlite3.connect(gtinf_path)
    conn.execute(
        f"""
        CREATE TABLE "gtinf_{model}" (
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
        f'INSERT INTO "gtinf_{model}" (imei, send_time, network_type, csq, csq_ber, operador) '
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


def test_build_points_reads_map_database(tmp_path: Path):
    base_dir, model, imei = _prepare_map_databases(tmp_path)

    ensure_enriched_database(report="gteri", model=model, base_dir=base_dir)

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    assert len(points) == 3
    summary = [
        (
            point.send_time.strftime("%Y%m%d%H%M%S"),
            point.report_kind,
            point.operator,
            point.network_label,
            point.signal_quality,
            point.day_iso,
        )
        for point in points
    ]
    assert summary == [
        ("20251016080000", "RESP", "Claro", "4G", "Excelente", "2025-10-16"),
        ("20251016083000", "BUFFER", "Claro", "4G", "Buena", "2025-10-16"),
        ("20251017090000", "RESP", "Movistar", "3G", "Regular", "2025-10-17"),
    ]


def test_build_points_supports_whitespace_imei(tmp_path: Path):
    base_dir, model, imei = _prepare_map_databases(tmp_path)
    map_path = base_dir / f"gteri_{model}_map.db"
    conn = sqlite3.connect(map_path)
    conn.execute(
        f'UPDATE "gteri_{model}" SET imei = ? WHERE send_time = ?',
        (f"  {imei}\r\n", "20251016080000"),
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

    assert len(points) == 3


def test_render_interactive_map_includes_filters(tmp_path: Path):
    pytest.importorskip("folium")
    base_dir, model, imei = _prepare_map_databases(tmp_path)

    ensure_enriched_database(report="gteri", model=model, base_dir=base_dir)

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    output_html = tmp_path / "mapa.html"
    render_interactive_map(points, output_html)

    html = output_html.read_text(encoding="utf-8")
    assert 'data-filter-panel="interactive-filters"' in html
    assert 'value="AMBOS"' in html
    assert 'value="BUFFER"' in html
    assert 'value="RESP"' in html
    assert 'value="All"' in html
    assert 'Calidad de señal' in html


def test_build_points_reads_existing_map_db(tmp_path: Path):
    """
    Si existe bases_sqlite/gteri_<modelo>_map.db con datos válidos,
    build_points debe leerla directamente sin depender de ensure_enriched_database.
    """

    base_dir = tmp_path
    model = "gv350ceu"
    imei = "123456789012345"

    db_path = base_dir / f"gteri_{model}_map.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        f"""
        CREATE TABLE "gteri_{model}" (
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
        f'INSERT INTO "gteri_{model}" (imei, send_time, lat, lon, header, operador, tecnologia_celular, calidad_senal) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        [
            (imei, "20251016080000", -23.65, -70.4, "+RESP:GTERI", "Claro", "4G", "Excelente"),
            (imei, "20251016083000", -23.66, -70.41, "+BUFF:GTERI", "Claro", "4G", "Buena"),
            (imei, "20251017090000", -23.67, -70.42, "+RESP:GTERI", "Movistar", "3G", "Regular"),
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

    assert len(points) == 3
    kinds = {point.report_kind for point in points}
    assert kinds == {"BUFFER", "RESP"}
    assert {point.operator for point in points} == {"Claro", "Movistar"}
    assert {point.network_label for point in points} == {"4G", "3G"}


def test_points_have_valid_lat_lon(tmp_path: Path):
    base_dir, model, imei = _prepare_map_databases(tmp_path)

    ensure_enriched_database(report="gteri", model=model, base_dir=base_dir)

    points = build_points(
        model=model,
        imei=imei,
        base_dir=base_dir,
        reports=["gteri"],
    )

    for point in points:
        assert -90 <= point.lat <= 90
        assert -180 <= point.lon <= 180
