"""Funciones geoespaciales para apoyar la visualización."""
from __future__ import annotations

import math
from typing import Mapping, Sequence, Tuple


def _get_coords(point: Mapping[str, float] | Sequence[float] | Tuple[float, float]) -> Tuple[float, float]:
    if isinstance(point, Mapping):
        lat = point.get("lat") or point.get("latitude")
        lon = point.get("lon") or point.get("lng") or point.get("longitude")
        if lat is None or lon is None:
            raise ValueError("El punto no contiene lat/lon")
        return float(lat), float(lon)
    if isinstance(point, (tuple, list)) and len(point) >= 2:
        return float(point[0]), float(point[1])
    raise TypeError("Formato de punto no soportado")


def bearing(p1, p2) -> float:
    """Calcula el azimut (0°=Norte) entre dos puntos geográficos."""

    lat1, lon1 = _get_coords(p1)
    lat2, lon2 = _get_coords(p2)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    diff_lon = math.radians(lon2 - lon1)
    x = math.sin(diff_lon) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(diff_lon)
    angle = math.degrees(math.atan2(x, y))
    return (angle + 360.0) % 360.0


def bearing_to_cardinal(angle: float, precision: int = 16) -> str:
    """Convierte un azimut en grados a un punto cardinal (por defecto 16 rumbos)."""

    if precision not in {4, 8, 16}:
        raise ValueError("precision debe ser 4, 8 o 16")
    directions = {
        4: ["N", "E", "S", "O"],
        8: ["N", "NE", "E", "SE", "S", "SO", "O", "NO"],
        16: [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSO",
            "SO",
            "OSO",
            "O",
            "ONO",
            "NO",
            "NNO",
        ],
    }[precision]
    sector = 360.0 / len(directions)
    index = int((angle + sector / 2) // sector) % len(directions)
    return directions[index]


__all__ = ["bearing", "bearing_to_cardinal"]
