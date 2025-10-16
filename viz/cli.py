"""CLI para generar mapas diarios de recorridos Queclink."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

try:
    from .folium_map import render_map
    _IMPORT_ERROR = None
except ModuleNotFoundError as exc:  # pragma: no cover - entorno sin folium
    render_map = None  # type: ignore
    _IMPORT_ERROR = exc

from .query import fetch_points_by_day


def _resolve_output(out: str) -> Tuple[Path, Path]:
    path = Path(out)
    if path.suffix.lower() == ".html":
        html_path = path
        geojson_path = path.with_suffix(".geojson")
    else:
        html_path = path.with_suffix(".html")
        geojson_path = path.with_suffix(".geojson")
    return html_path, geojson_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera un mapa Folium diario diferenciando reportes buffer/no-buffer",
    )
    parser.add_argument("--db", required=True, help="Ruta a la base SQLite generada por el parser")
    parser.add_argument("--imei", required=True, help="IMEI a consultar")
    parser.add_argument(
        "--date",
        required=True,
        help="Fecha local (America/Santiago) en formato YYYY-MM-DD",
    )
    parser.add_argument(
        "--provider",
        default="OpenStreetMap",
        help="Nombre del proveedor de tiles para Folium (por defecto OpenStreetMap)",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Ruta base de salida (se crearán archivos .html y .geojson)",
    )
    args = parser.parse_args()

    if _IMPORT_ERROR is not None:
        raise SystemExit(
            "folium no está instalado. Ejecuta 'pip install folium pytz python-dateutil'",
        )

    html_path, geojson_path = _resolve_output(args.out)
    points = fetch_points_by_day(args.db, args.imei, args.date)
    if not points:
        raise SystemExit("No se encontraron puntos para los parámetros indicados")

    assert render_map is not None
    render_map(points, str(html_path), str(geojson_path), tiles=args.provider)
    print(f"Mapa generado: {html_path}")
    print(f"GeoJSON generado: {geojson_path}")


if __name__ == "__main__":
    main()
