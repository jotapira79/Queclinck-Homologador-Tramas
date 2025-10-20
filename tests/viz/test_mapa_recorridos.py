from datetime import datetime, timedelta

import pytest

pytest.importorskip("folium")

from viz.mapa_recorridos import (
    InfoRecord,
    LocationPoint,
    _associate_info,
    _filter_points,
    _normalize_operator,
    _safe_int,
)


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


def _make_info(offset_seconds: int, *, label: str, csq: float, csq_ber: int | None = None) -> InfoRecord:
    base = datetime(2025, 10, 10, 0, 0, 0)
    return InfoRecord(
        imei="123456789012345",
        send_time=base + timedelta(seconds=offset_seconds),
        network_label=label,
        raw_network_value=None,
        csq=csq,
        csq_ber=csq_ber,
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

    assert [point.network_label for point in points] == ["3G", "3G", "3G", "4G"]
    assert [point.signal_quality for point in points] == [
        "Buena",
        "Buena",
        "Buena",
        "Excelente",
    ]


def test_associate_info_leaves_points_without_prior_info():
    points = [_make_point(-30), _make_point(10)]
    infos = [_make_info(20, label="2G", csq=25)]

    _associate_info(points, infos)

    assert points[0].network_label == "Desconocida"
    assert points[0].signal_quality == "Desconocida"
    assert points[1].network_label == "Desconocida"
    assert points[1].signal_quality == "Desconocida"


def test_filter_points_accepts_all_keyword_for_every_filter():
    points = [
        _make_point(0, operator="Claro", network="2G"),
        _make_point(60, operator="Entel", network="3G"),
        _make_point(120, operator="Movistar", network="4G"),
    ]

    assert _filter_points(points, operators=["All"]) == points
    assert _filter_points(points, networks=["ALL"]) == points
    assert _filter_points(points, day="all") == points
