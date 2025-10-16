"""Utilidades para visualización de recorridos diarios con Folium."""
from .query import fetch_points_by_day
from .geo import bearing, bearing_to_cardinal

__all__ = [
    "fetch_points_by_day",
    "bearing",
    "bearing_to_cardinal",
]

try:  # pragma: no cover - folium opcional en importación
    from .folium_map import render_map
    __all__.append("render_map")
except ModuleNotFoundError:  # pragma: no cover - folium no disponible
    def render_map(*args, **kwargs):  # type: ignore[override]
        raise ModuleNotFoundError(
            "Se requiere instalar folium para usar viz.render_map",
        )
