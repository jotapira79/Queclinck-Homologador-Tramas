import json
from datetime import datetime

import pytest

try:  # pragma: no cover - compatibilidad con stdlib
    import pytz
except ModuleNotFoundError:  # pragma: no cover - fallback sin pytz
    from zoneinfo import ZoneInfo

    class _Zone:
        @staticmethod
        def timezone(name: str):
            return ZoneInfo(name)

    pytz = _Zone()  # type: ignore

pytest.importorskip("folium")

import viz.folium_map
from viz.folium_map import render_map


def _aware(dt: datetime, tz):
    """Crea un datetime con zona horaria compatible con pytz o ZoneInfo."""
    if hasattr(tz, "localize"):
        return tz.localize(dt)
    return dt.replace(tzinfo=tz)


def sample_points():
    tz = pytz.timezone("America/Santiago")
    return [
        {
            "lat": -33.45,
            "lon": -70.66,
            "dt_local": _aware(datetime(2023, 8, 1, 8, 0, 0), tz),
            "report_type": "10",
            "is_buffer": False,
        },
        {
            "lat": -33.451,
            "lon": -70.661,
            "dt_local": _aware(datetime(2023, 8, 1, 8, 10, 0), tz),
            "report_type": "10",
            "is_buffer": False,
        },
        {
            "lat": -33.452,
            "lon": -70.662,
            "dt_local": _aware(datetime(2023, 8, 1, 8, 20, 0), tz),
            "report_type": "10",
            "is_buffer": True,
        },
    ]


def test_render_map_creates_files(tmp_path):
    html_path = tmp_path / "map.html"
    geojson_path = tmp_path / "map.geojson"

    render_map(sample_points(), str(html_path), str(geojson_path))
    assert html_path.exists()
    assert geojson_path.exists()

    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 3

    html_content = html_path.read_text(encoding="utf-8")
    assert "Directo" in html_content
    assert "Buffer" in html_content

    import re

    # Acepta "Chile", "CLT", "CLST", "GMT-03", "UTC-03", etc.
    assert re.search(
        r"08:10:00(?:\s|&nbsp;)?(?:Chile|CLT|CLST|[-+A-Z0-9:]{1,6})",
        html_content,
    ), "No se encontró la etiqueta de hora esperada en el HTML del mapa"


def test_render_map_allows_single_point_segments(monkeypatch, tmp_path):
    html_path = tmp_path / "single.html"
    geojson_path = tmp_path / "single.geojson"

    original_polyline = viz.folium_map.PolyLine

    def _guarded_polyline(coords, *args, **kwargs):
        assert len(coords) >= 2, "PolyLine should receive at least two coordinates"
        return original_polyline(coords, *args, **kwargs)

    monkeypatch.setattr(viz.folium_map, "PolyLine", _guarded_polyline)

    render_map(sample_points()[:2], str(html_path), str(geojson_path))
    assert html_path.exists()
    assert geojson_path.exists()
