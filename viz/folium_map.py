"""Renderizado de mapas diarios con Folium."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

import folium
from folium import FeatureGroup, Map, Marker, PolyLine
from folium.features import DivIcon
from folium.plugins import PolyLineTextPath

BUFFER_COLOR = "red"
NON_BUFFER_COLOR = "blue"
ARROW_SYMBOL = "➤"


def _ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _tooltip(point: dict) -> str:
    dt_local = point["dt_local"]
    time_label = _point_time_label(point)
    if time_label:
        dt_display = time_label
    else:
        dt_display = dt_local.strftime("%Y-%m-%d %H:%M:%S %Z")
    coords = f"({point['lat']:.5f}, {point['lon']:.5f})"
    report = point.get("report_type") or "?"
    source = "Buffer" if point.get("is_buffer") else "Directo"
    return f"{dt_display} | {coords} | {source} RT:{report}"


def _point_time_label(point: dict) -> str:
    dt_local = point.get("dt_local")
    if dt_local is None:
        return ""
    try:
        time_display = dt_local.strftime("%H:%M:%S")
    except Exception:
        return ""
    tz_name = getattr(dt_local, "tzname", lambda: None)()
    if tz_name and tz_name.strip():
        tz_display = "Chile" if tz_name.upper() in {"CLT", "CLST"} else tz_name
    else:
        tz_display = "Chile"
    return f"{time_display} {tz_display}".strip()


def _segment_color(is_buffer: bool) -> str:
    return BUFFER_COLOR if is_buffer else NON_BUFFER_COLOR


def _add_polyline(map_obj: Map, segment: List[dict]) -> None:
    if len(segment) < 2:
        return

    color = _segment_color(segment[0].get("is_buffer"))
    coords = [(p["lat"], p["lon"]) for p in segment]
    line = PolyLine(coords, color=color, weight=4, opacity=0.8)
    line.add_to(map_obj)
    try:
        PolyLineTextPath(
            line,
            ARROW_SYMBOL,
            repeat=True,
            offset=10,
            attributes={"fill": color, "font-weight": "bold", "font-size": "16"},
        ).add_to(map_obj)
    except Exception:
        pass


def render_map(
    points: Iterable[dict],
    out_html: str,
    out_geojson: str,
    tiles: str = "OpenStreetMap",
    zoom_start: int = 13,
) -> None:
    """Renderiza un mapa interactivo Folium con los puntos provistos."""

    points_list = [p for p in points]
    if not points_list:
        raise ValueError("Se requieren puntos para generar el mapa")

    points_list.sort(key=lambda p: p["dt_local"])

    start_lat = points_list[0]["lat"]
    start_lon = points_list[0]["lon"]
    fmap = Map(location=(start_lat, start_lon), tiles=tiles, zoom_start=zoom_start)

    buffer_group = FeatureGroup(name="Buffer", overlay=True)
    direct_group = FeatureGroup(name="Directo", overlay=True)

    last_point = None
    current_segment: List[dict] = []
    for point in points_list:
        tooltip = _tooltip(point)
        marker_group = buffer_group if point.get("is_buffer") else direct_group
        folium.CircleMarker(
            location=(point["lat"], point["lon"]),
            radius=5,
            color=_segment_color(point.get("is_buffer")),
            fill=True,
            fill_color=_segment_color(point.get("is_buffer")),
            fill_opacity=0.7,
            tooltip=tooltip,
        ).add_to(marker_group)

        if last_point is not None:
            time_label = _point_time_label(point)
            if time_label:
                Marker(
                    location=((last_point["lat"] + point["lat"]) / 2, (last_point["lon"] + point["lon"]) / 2),
                    icon=DivIcon(
                        icon_size=(150, 36),
                        icon_anchor=(0, 0),
                        html=f'<div style="font-size: 10px; color: {_segment_color(point.get("is_buffer"))};">{time_label}</div>',
                    ),
                ).add_to(fmap)

        if current_segment and point.get("is_buffer") != current_segment[-1].get("is_buffer"):
            _add_polyline(buffer_group if current_segment[-1].get("is_buffer") else direct_group, current_segment)
            current_segment = []
        current_segment.append(point)
        last_point = point

    if current_segment:
        _add_polyline(buffer_group if current_segment[-1].get("is_buffer") else direct_group, current_segment)

    buffer_group.add_to(fmap)
    direct_group.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    folium.Marker(
        location=(points_list[0]["lat"], points_list[0]["lon"]),
        popup="Inicio",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(fmap)
    folium.Marker(
        location=(points_list[-1]["lat"], points_list[-1]["lon"]),
        popup="Fin",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(fmap)

    fmap.fit_bounds([(p["lat"], p["lon"]) for p in points_list])

    html_path = Path(out_html)
    geojson_path = Path(out_geojson)
    _ensure_parent(html_path)
    _ensure_parent(geojson_path)
    fmap.save(str(html_path))

    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [point["lon"], point["lat"]],
                },
                "properties": {
                    "dt_local": point["dt_local"].isoformat(),
                    "report_type": point.get("report_type"),
                    "is_buffer": bool(point.get("is_buffer")),
                },
            }
            for point in points_list
        ],
    }
    with geojson_path.open("w", encoding="utf-8") as fh:
        json.dump(feature_collection, fh, ensure_ascii=False, indent=2)


__all__ = ["render_map"]
