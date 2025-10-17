import pytest

pytest.importorskip("folium")

from viz.mapa_recorridos import _normalize_operator, _safe_int


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
