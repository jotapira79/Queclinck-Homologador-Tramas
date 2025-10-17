"""Generación de mapas interactivos por IMEI usando bases SQLite de reportes Queclink."""
from __future__ import annotations

import argparse
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - dependencia opcional en tiempo de ejecución
    import folium
    from folium import FeatureGroup, Map
    from folium.plugins import GroupedLayerControl
except ModuleNotFoundError as exc:  # pragma: no cover - entorno sin folium
    raise ModuleNotFoundError(
        "folium no está instalado. Ejecuta 'pip install folium pytz python-dateutil'"
    ) from exc

from branca.element import MacroElement
from jinja2 import Template

from src.ingestors.sqlite_records import ensure_db

# Tipos auxiliares -----------------------------------------------------------


@dataclass
class LocationPoint:
    lat: float
    lon: float
    send_time: datetime
    imei: str
    source: str
    operator: str
    mcc: Optional[int] = None
    mnc: Optional[int] = None
    raw_payload: Optional[dict] = None
    network_label: str = "Desconocida"
    signal_quality: str = "Desconocida"
    signal_dbm: Optional[float] = None
    csq: Optional[float] = None
    csq_ber: Optional[int] = None


@dataclass
class InfoRecord:
    imei: str
    send_time: datetime
    network_label: str
    raw_network_value: Optional[int]
    csq: Optional[float] = None
    csq_ber: Optional[int] = None


NETWORK_TYPE_MAP = {
    0: "Sin servicio",
    1: "2G",
    2: "3G",
    3: "4G",
}

NETWORK_COLORS = {
    "2G": "#1f77b4",
    "3G": "#ff7f0e",
    "4G": "#2ca02c",
    "Sin servicio": "#7f7f7f",
    "Desconocida": "#7f7f7f",
}

OPERATOR_COLORS = {
    "Entel": "#1f77b4",
    "Claro": "#ff7f0e",
    "Movistar": "#2ca02c",
    "WOM": "#9467bd",
    "Desconocido": "#7f7f7f",
}

IMEI_CANDIDATES = ["imei", "unique_id", "uniqueid", "device_imei"]
LAT_CANDIDATES = [
    "lat",
    "latitude",
    "latitude_deg",
    "lat_decimal",
    "lat_deg",
]
LON_CANDIDATES = [
    "lon",
    "longitude",
    "longitude_deg",
    "lon_decimal",
    "lon_deg",
]
TIME_CANDIDATES = ["send_time", "gnss_utc_time", "timestamp", "created_at"]
MCC_CANDIDATES = ["mcc", "mobile_country_code"]
MNC_CANDIDATES = ["mnc", "mobile_network_code"]
CSQ_CANDIDATES = ["csq", "csq_rssi", "csq_rsrp", "lte_csq"]
CSQ_BER_CANDIDATES = ["csq_ber", "ber"]
NETWORK_TYPE_CANDIDATES = ["network_type", "rat", "network"]


# Utilidades de parsing ------------------------------------------------------


def _parse_datetime(value: object) -> Optional[datetime]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _safe_float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        try:
            return int(str(value).lstrip("0") or "0")
        except ValueError:
            return None


def _normalize_operator(mcc: Optional[int], mnc: Optional[int]) -> str:
    if mcc != 730:
        return "Desconocido"
    if mnc == 1:
        return "Entel"
    if mnc == 2:
        return "Movistar"
    if mnc == 3:
        return "Claro"
    if mnc == 9:
        return "WOM"
    return "Desconocido"


def _csq_to_dbm(network_label: str, csq: Optional[float]) -> Optional[float]:
    if csq is None:
        return None
    if network_label in {"2G", "3G"}:
        if csq in {99, 199}:
            return None
        return csq * 2 - 113
    if network_label == "4G":
        if csq in {255, 511}:
            return None
        return csq - 140
    return None


def _classify_signal(network_label: str, csq: Optional[float], csq_ber: Optional[int]) -> Tuple[str, Optional[float]]:
    dbm = _csq_to_dbm(network_label, csq)
    if dbm is None:
        return "Desconocida", None
    quality: str
    if dbm >= -80:
        quality = "Excelente"
    elif dbm >= -90:
        quality = "Buena"
    elif dbm >= -100:
        quality = "Regular"
    else:
        quality = "Pésima"

    if network_label == "3G" and csq_ber is not None:
        # BER 5-7 se considera mala calidad.
        if csq_ber >= 7:
            quality = "Pésima"
        elif csq_ber >= 5 and quality == "Excelente":
            quality = "Buena"
    return quality, dbm


def _first_existing(candidates: Sequence[str], available: Iterable[str]) -> Optional[str]:
    available_lower = {name.lower(): name for name in available}
    for candidate in candidates:
        if candidate.lower() in available_lower:
            return available_lower[candidate.lower()]
    return None


def _detect_table(conn: sqlite3.Connection, report: str, model: str) -> str:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = [row[0] for row in cursor.fetchall()]
    if not names:
        raise ValueError("La base de datos no tiene tablas")
    model_lower = model.lower()
    report_lower = report.lower()
    candidates = [
        f"{report_lower}_{model_lower}",
        f"{report_lower}_{model}",
        f"{report}_{model_lower}",
        f"{report}_{model}",
        f"{report_lower}_records",
        f"{report}_records",
        f"{model_lower}_{report_lower}",
        f"{report_lower}",
    ]
    existing_lower = {name.lower(): name for name in names}
    for candidate in candidates:
        if candidate.lower() in existing_lower:
            return existing_lower[candidate.lower()]
    if len(names) == 1:
        return names[0]
    raise ValueError(f"No se encontró una tabla para {report}/{model}. Tablas: {', '.join(names)}")


# Lectura de datos -----------------------------------------------------------


def _load_table_schema(conn: sqlite3.Connection, table: str) -> List[str]:
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [row[1] for row in info]


def _load_locations_from_db(
    db_path: Path,
    report: str,
    model: str,
    imei: str,
) -> List[LocationPoint]:
    if not db_path.exists():
        return []

    conn = ensure_db(db_path)
    conn.row_factory = sqlite3.Row
    table = _detect_table(conn, report, model)
    columns = _load_table_schema(conn, table)

    imei_col = _first_existing(IMEI_CANDIDATES, columns)
    if not imei_col:
        raise ValueError(f"La tabla {table} no contiene columna IMEI reconocida")

    lat_col = _first_existing(LAT_CANDIDATES, columns)
    lon_col = _first_existing(LON_CANDIDATES, columns)
    if not lat_col or not lon_col:
        raise ValueError(f"La tabla {table} no contiene columnas de latitud/longitud")

    time_col = _first_existing(TIME_CANDIDATES, columns)
    if not time_col:
        raise ValueError(f"La tabla {table} no contiene columna send_time")

    mcc_col = _first_existing(MCC_CANDIDATES, columns)
    mnc_col = _first_existing(MNC_CANDIDATES, columns)

    query_cols = {lat_col, lon_col, time_col, imei_col}
    if mcc_col:
        query_cols.add(mcc_col)
    if mnc_col:
        query_cols.add(mnc_col)
    query_cols.add("report_type") if "report_type" in columns else None

    select_clause = ", ".join(f'"{col}"' for col in query_cols)
    sql = f'SELECT {select_clause} FROM "{table}" WHERE "{imei_col}" = ? ORDER BY "{time_col}"'

    points: List[LocationPoint] = []
    for row in conn.execute(sql, (imei,)):
        raw_lat = _safe_float(row[lat_col])
        raw_lon = _safe_float(row[lon_col])
        lat = raw_lon if raw_lon is not None else raw_lat
        lon = raw_lat if raw_lat is not None else raw_lon
        dt = _parse_datetime(row[time_col])
        if lat is None or lon is None or dt is None:
            continue
        mcc = _safe_int(row[mcc_col]) if mcc_col else None
        mnc = _safe_int(row[mnc_col]) if mnc_col else None
        operator = _normalize_operator(mcc, mnc)
        raw_payload = {col: row[col] for col in row.keys()}
        points.append(
            LocationPoint(
                lat=lat,
                lon=lon,
                send_time=dt,
                imei=imei,
                source=report.lower(),
                operator=operator,
                mcc=mcc,
                mnc=mnc,
                raw_payload=raw_payload,
            )
        )
    conn.close()
    return points


def _load_gtinf_records(db_path: Path, model: str, imei: str) -> List[InfoRecord]:
    if not db_path.exists():
        return []

    conn = ensure_db(db_path)
    conn.row_factory = sqlite3.Row
    table = _detect_table(conn, "gtinf", model)
    columns = _load_table_schema(conn, table)

    imei_col = _first_existing(IMEI_CANDIDATES, columns)
    time_col = _first_existing(TIME_CANDIDATES, columns)
    network_col = _first_existing(NETWORK_TYPE_CANDIDATES, columns)
    if not imei_col or not time_col or not network_col:
        raise ValueError(f"La tabla {table} no tiene columnas necesarias para GTINF")

    csq_col = _first_existing(CSQ_CANDIDATES, columns)
    ber_col = _first_existing(CSQ_BER_CANDIDATES, columns)

    query_cols = {imei_col, time_col, network_col}
    if csq_col:
        query_cols.add(csq_col)
    if ber_col:
        query_cols.add(ber_col)

    select_clause = ", ".join(f'"{col}"' for col in query_cols)
    sql = f'SELECT {select_clause} FROM "{table}" WHERE "{imei_col}" = ? ORDER BY "{time_col}"'

    info_records: List[InfoRecord] = []
    for row in conn.execute(sql, (imei,)):
        dt = _parse_datetime(row[time_col])
        if dt is None:
            continue
        raw_network = _safe_int(row[network_col])
        network_label = NETWORK_TYPE_MAP.get(raw_network, "Desconocida")
        csq = _safe_float(row[csq_col]) if csq_col else None
        csq_ber = _safe_int(row[ber_col]) if ber_col else None
        info_records.append(
            InfoRecord(
                imei=imei,
                send_time=dt,
                network_label=network_label,
                raw_network_value=raw_network,
                csq=csq,
                csq_ber=csq_ber,
            )
        )
    conn.close()
    return info_records


# Sincronización -------------------------------------------------------------


def _associate_info(points: List[LocationPoint], infos: List[InfoRecord]) -> None:
    if not points or not infos:
        return
    infos_sorted = sorted(infos, key=lambda r: r.send_time)
    idx = 0
    for point in sorted(points, key=lambda p: p.send_time):
        while idx + 1 < len(infos_sorted):
            curr = infos_sorted[idx]
            nxt = infos_sorted[idx + 1]
            if abs((nxt.send_time - point.send_time).total_seconds()) <= abs(
                (curr.send_time - point.send_time).total_seconds()
            ):
                idx += 1
            else:
                break
        info = infos_sorted[idx]
        point.network_label = info.network_label
        point.csq = info.csq
        point.csq_ber = info.csq_ber
        quality, dbm = _classify_signal(info.network_label, info.csq, info.csq_ber)
        point.signal_quality = quality
        point.signal_dbm = dbm


# Filtros --------------------------------------------------------------------


def _filter_points(
    points: List[LocationPoint],
    day: Optional[str] = None,
    operators: Optional[Sequence[str]] = None,
    networks: Optional[Sequence[str]] = None,
) -> List[LocationPoint]:
    result = []
    operator_set = {op.lower() for op in operators} if operators else None
    network_set = {nt.lower() for nt in networks} if networks else None
    day_value: Optional[datetime] = None
    if day:
        try:
            day_value = datetime.strptime(day, "%Y-%m-%d")
        except ValueError as exc:  # pragma: no cover - validación de CLI
            raise ValueError("El día debe tener formato YYYY-MM-DD") from exc
    for point in points:
        if day_value and point.send_time.date() != day_value.date():
            continue
        if operator_set and point.operator.lower() not in operator_set:
            continue
        if network_set and point.network_label.lower() not in network_set:
            continue
        result.append(point)
    return result


# Render del mapa ------------------------------------------------------------


def _ensure_output_path(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _point_to_tooltip(point: LocationPoint) -> str:
    parts = [
        f"IMEI: {point.imei}",
        f"Reporte: {point.source.upper()}",
        f"Fecha envío: {point.send_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Coordenadas: {point.lat:.5f}, {point.lon:.5f}",
        f"Operador: {point.operator}",
        f"Tecnología: {point.network_label}",
        f"Señal: {point.signal_quality}",
    ]
    if point.signal_dbm is not None:
        parts.append(f"Nivel: {point.signal_dbm:.1f} dBm")
    if point.csq is not None:
        parts.append(f"CSQ: {point.csq}")
    if point.csq_ber is not None:
        parts.append(f"BER: {point.csq_ber}")
    return "<br>".join(parts)


class OperatorLegend(MacroElement):
    def __init__(self, colors: Dict[str, str]):
        super().__init__()
        entries = []
        for operator in ("Entel", "Claro", "Movistar"):
            color = colors.get(operator)
            if not color:
                continue
            entries.append(
                f'<div style="display:flex; align-items:center; margin-bottom:4px;">'
                f'<span style="background:{color}; width:12px; height:12px; display:inline-block; '
                f'margin-right:6px; border:1px solid #333;"></span>{operator}</div>'
            )
        entries_html = "".join(entries)
        self._template = Template(
            f"""
            {{% macro html(this, kwargs) %}}
            <div style="position: fixed; bottom: 40px; left: 40px; z-index: 9999; background-color: white;
                        border: 1px solid #bbb; padding: 8px 12px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                        border-radius: 4px; font-size: 13px;">
                <div style="font-weight: bold; margin-bottom: 6px;">Operadores</div>
                {entries_html}
            </div>
            {{% endmacro %}}
            """
        )


def render_interactive_map(
    points: List[LocationPoint],
    output_html: Path,
    *,
    tiles: str = "OpenStreetMap",
) -> None:
    if not points:
        raise ValueError("No hay puntos para representar en el mapa")

    points_sorted = sorted(points, key=lambda p: p.send_time)
    center_lat = points_sorted[0].lat
    center_lon = points_sorted[0].lon
    fmap = Map(location=(center_lat, center_lon), zoom_start=13, tiles=tiles)

    day_groups: Dict[str, FeatureGroup] = {}
    operator_groups: Dict[str, FeatureGroup] = {}
    network_groups: Dict[str, FeatureGroup] = {}

    day_coords: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    operator_coords: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    network_coords: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    day_operator_counts: Dict[str, Counter] = defaultdict(Counter)

    for point in points_sorted:
        day_label = point.send_time.date().isoformat()
        operator_label = point.operator or "Desconocido"
        network_label = point.network_label or "Desconocida"
        operator_color = OPERATOR_COLORS.get(operator_label, OPERATOR_COLORS["Desconocido"])

        day_group = day_groups.get(day_label)
        if day_group is None:
            day_group = FeatureGroup(name=f"Día {day_label}", overlay=True, show=True)
            day_group.add_to(fmap)
            day_groups[day_label] = day_group

        operator_group = operator_groups.get(operator_label)
        if operator_group is None:
            operator_group = FeatureGroup(
                name=f"Operador {operator_label}", overlay=True, show=True
            )
            operator_group.add_to(fmap)
            operator_groups[operator_label] = operator_group

        network_group = network_groups.get(network_label)
        if network_group is None:
            network_group = FeatureGroup(
                name=f"Tecnología {network_label}", overlay=True, show=True
            )
            network_group.add_to(fmap)
            network_groups[network_label] = network_group

        tooltip = _point_to_tooltip(point)
        for group in (day_group, operator_group, network_group):
            folium.CircleMarker(
                location=(point.lat, point.lon),
                radius=6,
                color=operator_color,
                weight=2,
                fill=True,
                fill_color=operator_color,
                fill_opacity=0.85,
                tooltip=tooltip,
            ).add_to(group)

        day_coords[day_label].append((point.lat, point.lon))
        operator_coords[operator_label].append((point.lat, point.lon))
        network_coords[network_label].append((point.lat, point.lon))
        day_operator_counts[day_label][operator_label] += 1

    for day_label, coords in day_coords.items():
        if len(coords) < 2:
            continue
        dominant_operator, _ = max(
            day_operator_counts[day_label].items(), key=lambda item: item[1]
        )
        color = OPERATOR_COLORS.get(dominant_operator, OPERATOR_COLORS["Desconocido"])
        folium.PolyLine(coords, color=color, weight=4, opacity=0.6).add_to(
            day_groups[day_label]
        )

    for operator_label, coords in operator_coords.items():
        if len(coords) < 2:
            continue
        color = OPERATOR_COLORS.get(operator_label, OPERATOR_COLORS["Desconocido"])
        folium.PolyLine(coords, color=color, weight=4, opacity=0.6).add_to(
            operator_groups[operator_label]
        )

    for network_label, coords in network_coords.items():
        if len(coords) < 2:
            continue
        color = NETWORK_COLORS.get(network_label, "#7f7f7f")
        folium.PolyLine(coords, color=color, weight=4, opacity=0.6).add_to(
            network_groups[network_label]
        )

    grouped_layers = {
        "Días": [day_groups[key] for key in sorted(day_groups.keys())],
        "Operadores": [operator_groups[key] for key in sorted(operator_groups.keys())],
        "Tecnologías": [network_groups[key] for key in sorted(network_groups.keys())],
    }
    GroupedLayerControl(grouped_layers, collapsed=False).add_to(fmap)

    fmap.get_root().add_child(OperatorLegend(OPERATOR_COLORS))
    fmap.fit_bounds([(p.lat, p.lon) for p in points_sorted])

    _ensure_output_path(output_html)
    fmap.save(str(output_html))


# API pública ----------------------------------------------------------------


def build_points(
    *,
    model: str,
    imei: str,
    base_dir: Path,
    reports: Optional[Sequence[str]] = None,
) -> List[LocationPoint]:
    model_clean = model.strip().lower()
    if not model_clean:
        raise ValueError("El modelo no puede estar vacío")

    reports_to_use = [r.lower() for r in (reports or ["gteri", "gtfri"])]
    all_points: List[LocationPoint] = []
    for report in reports_to_use:
        db_path = base_dir / f"{report}_{model_clean}.db"
        points = _load_locations_from_db(db_path, report, model_clean, imei)
        all_points.extend(points)

    if not all_points:
        raise FileNotFoundError(
            "No se encontraron registros de recorrido en las bases especificadas."
        )

    info_path = base_dir / f"gtinf_{model_clean}.db"
    info_records = _load_gtinf_records(info_path, model_clean, imei)
    if info_records:
        _associate_info(all_points, info_records)

    return sorted(all_points, key=lambda p: p.send_time)


def generate_map(
    *,
    model: str,
    imei: str,
    base_dir: Path | str = Path("."),
    output_dir: Path | str = Path("."),
    day: Optional[str] = None,
    operators: Optional[Sequence[str]] = None,
    networks: Optional[Sequence[str]] = None,
    reports: Optional[Sequence[str]] = None,
    tiles: str = "OpenStreetMap",
) -> Path:
    base_path = Path(base_dir)
    output_path = Path(output_dir)

    points = build_points(model=model, imei=imei, base_dir=base_path, reports=reports)
    filtered = _filter_points(points, day=day, operators=operators, networks=networks)
    if not filtered:
        raise ValueError("Los filtros aplicados no devolvieron puntos para el mapa")

    html_name = f"mapa_{model.lower()}_{imei}.html"
    output_file = output_path / html_name
    render_interactive_map(filtered, output_file, tiles=tiles)
    return output_file


# CLI ------------------------------------------------------------------------


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un mapa interactivo por IMEI utilizando las bases gteri/gtfri/gtinf",
    )
    parser.add_argument("--model", required=True, help="Modelo del equipo (ej. gv350ceu)")
    parser.add_argument("--imei", required=True, help="IMEI a consultar")
    parser.add_argument(
        "--db-dir",
        default=".",
        help="Directorio que contiene los archivos SQLite (por defecto el directorio actual)",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directorio donde se guardará el mapa generado",
    )
    parser.add_argument(
        "--day",
        help="Filtra por fecha local (YYYY-MM-DD) usando send_time",
    )
    parser.add_argument(
        "--operator",
        dest="operators",
        action="append",
        help="Filtra por operador (puede repetirse). Ej: --operator Claro",
    )
    parser.add_argument(
        "--network",
        dest="networks",
        action="append",
        help="Filtra por tecnología de red (2G, 3G, 4G)",
    )
    parser.add_argument(
        "--report",
        dest="reports",
        action="append",
        choices=["gteri", "gtfri"],
        help="Limita los reportes de posición a usar (por defecto gteri y gtfri)",
    )
    parser.add_argument(
        "--tiles",
        default="OpenStreetMap",
        help="Proveedor de tiles para Folium",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    output_path = generate_map(
        model=args.model,
        imei=args.imei,
        base_dir=Path(args.db_dir),
        output_dir=Path(args.out_dir),
        day=args.day,
        operators=args.operators,
        networks=args.networks,
        reports=args.reports,
        tiles=args.tiles,
    )
    print(f"Mapa generado en: {output_path}")


if __name__ == "__main__":  # pragma: no cover - punto de entrada CLI
    main()
