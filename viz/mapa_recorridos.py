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
    _FOLIUM_IMPORT_ERROR: ModuleNotFoundError | None = None
except ModuleNotFoundError as exc:  # pragma: no cover - entorno sin folium
    folium = None  # type: ignore[assignment]
    FeatureGroup = Map = GroupedLayerControl = None  # type: ignore[assignment]
    _FOLIUM_IMPORT_ERROR = ModuleNotFoundError(
        "folium no está instalado. Ejecuta 'pip install folium pytz python-dateutil'"
    )

try:  # pragma: no cover - dependencia opcional
    from branca.element import MacroElement
except ModuleNotFoundError:  # pragma: no cover - entorno sin branca
    MacroElement = object  # type: ignore[assignment]
    if '_FOLIUM_IMPORT_ERROR' in globals() and _FOLIUM_IMPORT_ERROR is None:
        _FOLIUM_IMPORT_ERROR = ModuleNotFoundError(
            "branca no está instalado. Ejecuta 'pip install folium pytz python-dateutil'"
        )

try:  # pragma: no cover - dependencia opcional
    from jinja2 import Template
except ModuleNotFoundError:  # pragma: no cover - entorno sin jinja2
    Template = None  # type: ignore[assignment]
    if '_FOLIUM_IMPORT_ERROR' in globals() and _FOLIUM_IMPORT_ERROR is None:
        _FOLIUM_IMPORT_ERROR = ModuleNotFoundError(
            "jinja2 no está instalado. Ejecuta 'pip install folium pytz python-dateutil'"
        )

from src.ingestors.sqlite_records import ensure_db

from .enriched_db import ensure_enriched_database
from .utils import (
    CSQ_BER_CANDIDATES,
    CSQ_CANDIDATES,
    IMEI_CANDIDATES,
    LAT_CANDIDATES,
    LON_CANDIDATES,
    MCC_CANDIDATES,
    MNC_CANDIDATES,
    NETWORK_TYPE_CANDIDATES,
    NETWORK_TYPE_MAP,
    TIME_CANDIDATES,
    classify_signal as _classify_signal,
    detect_table as _detect_table,
    first_existing as _first_existing,
    load_table_schema as _load_table_schema,
    normalize_operator as _normalize_operator,
    parse_datetime as _parse_datetime,
    safe_float as _safe_float,
    safe_int as _safe_int,
)

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

# Utilidades internas --------------------------------------------------------


def _valid_coordinates(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _swap_coordinates_if_needed(
    lat: float, lon: float, mcc: Optional[int]
) -> Tuple[float, float]:
    candidate_lat, candidate_lon = lon, lat
    swap_valid = _valid_coordinates(candidate_lat, candidate_lon)

    if abs(lat) > 90.0 and abs(lon) <= 90.0 and swap_valid:
        return candidate_lat, candidate_lon

    if mcc == 730 and abs(lat) > 60.0 and abs(lon) < 80.0 and swap_valid:
        return candidate_lat, candidate_lon

    if abs(lat) > 60.0 and swap_valid and not (-60.0 <= lat <= 60.0):
        if -60.0 <= candidate_lat <= 60.0:
            return candidate_lat, candidate_lon

    return lat, lon


def _require_folium() -> None:
    if _FOLIUM_IMPORT_ERROR is not None:
        raise _FOLIUM_IMPORT_ERROR

# Lectura de datos -----------------------------------------------------------

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
    try:
        table = _detect_table(conn, report, model)
        columns = _load_table_schema(conn, table)

        imei_col = _first_existing(IMEI_CANDIDATES, columns)
        if not imei_col:
            raise ValueError(f"La tabla {table} no contiene columna IMEI reconocida")

        lat_col = _first_existing(LAT_CANDIDATES, columns)
        lon_col = _first_existing(LON_CANDIDATES, columns)
        if not lat_col or not lon_col:
            return []

        time_col = _first_existing(TIME_CANDIDATES, columns)
        if not time_col:
            raise ValueError(f"La tabla {table} no contiene columna send_time")

        mcc_col = _first_existing(MCC_CANDIDATES, columns)
        mnc_col = _first_existing(MNC_CANDIDATES, columns)
        csq_col = _first_existing(CSQ_CANDIDATES, columns)
        ber_col = _first_existing(CSQ_BER_CANDIDATES, columns)
        tech_col = "tecnologia_celular" if "tecnologia_celular" in columns else None
        quality_col = "calidad_senal" if "calidad_senal" in columns else None
        dbm_col = "nivel_senal_dbm" if "nivel_senal_dbm" in columns else None
        operator_col = "operador" if "operador" in columns else None

        query_cols = {lat_col, lon_col, time_col, imei_col}
        if mcc_col:
            query_cols.add(mcc_col)
        if mnc_col:
            query_cols.add(mnc_col)
        if csq_col:
            query_cols.add(csq_col)
        if ber_col:
            query_cols.add(ber_col)
        if tech_col:
            query_cols.add(tech_col)
        if quality_col:
            query_cols.add(quality_col)
        if dbm_col:
            query_cols.add(dbm_col)
        if operator_col:
            query_cols.add(operator_col)
        query_cols.add("report_type") if "report_type" in columns else None

        select_clause = ", ".join(f'"{col}"' for col in query_cols)
        sql = f'SELECT {select_clause} FROM "{table}" WHERE "{imei_col}" = ? ORDER BY "{time_col}"'

        points: List[LocationPoint] = []
        for row in conn.execute(sql, (imei,)):
            raw_lat = _safe_float(row[lat_col])
            raw_lon = _safe_float(row[lon_col])
            dt = _parse_datetime(row[time_col])
            if raw_lat is None or raw_lon is None or dt is None:
                continue
            mcc = _safe_int(row[mcc_col]) if mcc_col else None
            mnc = _safe_int(row[mnc_col]) if mnc_col else None
            lat, lon = _swap_coordinates_if_needed(raw_lat, raw_lon, mcc)
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue

            operator = ""
            if operator_col:
                raw_operator = row[operator_col]
                if raw_operator not in (None, ""):
                    operator = str(raw_operator).strip()
            if not operator:
                operator = _normalize_operator(mcc, mnc)
            network_label = "Desconocida"
            if tech_col:
                raw_tech = row[tech_col]
                if raw_tech not in (None, ""):
                    network_label = str(raw_tech).strip()
            signal_quality = "Desconocida"
            if quality_col:
                raw_quality = row[quality_col]
                if raw_quality not in (None, ""):
                    signal_quality = str(raw_quality).strip()
            csq = _safe_float(row[csq_col]) if csq_col else None
            csq_ber = _safe_int(row[ber_col]) if ber_col else None
            signal_dbm = _safe_float(row[dbm_col]) if dbm_col else None
            if signal_dbm is None and network_label not in (None, "", "Desconocida"):
                computed_quality, computed_dbm = _classify_signal(
                    network_label, csq, csq_ber
                )
                if signal_quality == "Desconocida":
                    signal_quality = computed_quality
                signal_dbm = computed_dbm
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
                    network_label=network_label or "Desconocida",
                    signal_quality=signal_quality or "Desconocida",
                    signal_dbm=signal_dbm,
                    csq=csq,
                    csq_ber=csq_ber,
                )
            )
        return points
    finally:
        conn.close()


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
    current_info: Optional[InfoRecord] = None
    for point in sorted(points, key=lambda p: p.send_time):
        while idx < len(infos_sorted) and infos_sorted[idx].send_time <= point.send_time:
            current_info = infos_sorted[idx]
            idx += 1
        if current_info is None:
            continue
        if point.network_label not in (None, "", "Desconocida"):
            if point.signal_quality not in (None, "", "Desconocida") and point.signal_dbm is not None:
                continue
        point.network_label = current_info.network_label
        point.csq = current_info.csq
        point.csq_ber = current_info.csq_ber
        quality, dbm = _classify_signal(
            current_info.network_label, current_info.csq, current_info.csq_ber
        )
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

    normalized_ops = (
        {op.strip().lower() for op in operators if op is not None}
        if operators
        else None
    )
    operator_set = None if not normalized_ops or "all" in normalized_ops else normalized_ops

    normalized_networks = (
        {nt.strip().lower() for nt in networks if nt is not None}
        if networks
        else None
    )
    network_set = (
        None if not normalized_networks or "all" in normalized_networks else normalized_networks
    )

    day_value: Optional[datetime] = None
    if day:
        day_clean = day.strip()
        if day_clean.lower() != "all":
            try:
                day_value = datetime.strptime(day_clean, "%Y-%m-%d")
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
        for operator in sorted(
            key for key in colors.keys() if key.lower() != "desconocido"
        ):
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
    _require_folium()
    if not points:
        raise ValueError("No hay puntos para representar en el mapa")

    points_sorted = sorted(points, key=lambda p: p.send_time)
    center_lat = points_sorted[0].lat
    center_lon = points_sorted[0].lon
    fmap = Map(location=(center_lat, center_lon), zoom_start=13, tiles=tiles)

    day_groups: Dict[str, FeatureGroup] = {}
    operator_groups: Dict[str, FeatureGroup] = {}
    network_groups: Dict[str, FeatureGroup] = {}

    all_days_group = FeatureGroup(name="Todos los días", overlay=True, show=True)
    all_days_group.add_to(fmap)
    day_groups["Todos los días"] = all_days_group

    for operator_label, color in OPERATOR_COLORS.items():
        group = FeatureGroup(name=f"Operador {operator_label}", overlay=True, show=True)
        group.add_to(fmap)
        operator_groups[operator_label] = group

    for network_label, color in NETWORK_COLORS.items():
        group = FeatureGroup(name=f"Tecnología {network_label}", overlay=True, show=True)
        group.add_to(fmap)
        network_groups[network_label] = group

    day_coords: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    operator_coords: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    network_coords: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    day_operator_counts: Dict[str, Counter] = defaultdict(Counter)
    all_coords: List[Tuple[float, float]] = []
    all_operator_counts: Counter = Counter()

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

        folium.CircleMarker(
            location=(point.lat, point.lon),
            radius=6,
            color=operator_color,
            weight=2,
            fill=True,
            fill_color=operator_color,
            fill_opacity=0.85,
            tooltip=tooltip,
        ).add_to(all_days_group)

        day_coords[day_label].append((point.lat, point.lon))
        operator_coords[operator_label].append((point.lat, point.lon))
        network_coords[network_label].append((point.lat, point.lon))
        day_operator_counts[day_label][operator_label] += 1
        all_coords.append((point.lat, point.lon))
        all_operator_counts[operator_label] += 1

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

    if len(all_coords) >= 2:
        dominant_operator, _ = max(
            all_operator_counts.items(), key=lambda item: item[1]
        )
        color = OPERATOR_COLORS.get(dominant_operator, OPERATOR_COLORS["Desconocido"])
        folium.PolyLine(all_coords, color=color, weight=4, opacity=0.6).add_to(
            all_days_group
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

    sorted_day_layers = [day_groups["Todos los días"]] + [
        day_groups[key] for key in sorted(day_groups.keys()) if key != "Todos los días"
    ]
    sorted_operator_layers = [
        operator_groups[key]
        for key in OPERATOR_COLORS.keys()
        if key in operator_groups
    ] + [
        operator_groups[key]
        for key in sorted(operator_groups.keys())
        if key not in OPERATOR_COLORS
    ]
    sorted_network_layers = [
        network_groups[key]
        for key in NETWORK_COLORS.keys()
        if key in network_groups
    ] + [
        network_groups[key]
        for key in sorted(network_groups.keys())
        if key not in NETWORK_COLORS
    ]

    grouped_layers = {
        "Días": sorted_day_layers,
        "Operadores": sorted_operator_layers,
        "Tecnologías": sorted_network_layers,
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
    searched_paths: List[Path] = []
    for report in reports_to_use:
        db_path = base_dir / f"{report}_{model_clean}.db"
        try:
            enriched_path = ensure_enriched_database(
                report=report,
                model=model_clean,
                base_dir=base_dir,
            )
        except FileNotFoundError:
            searched_paths.append(db_path)
            continue

        searched_paths.append(enriched_path)
        points = _load_locations_from_db(enriched_path, report, model_clean, imei)
        all_points.extend(points)

    if not all_points:
        existing_paths = [path for path in searched_paths if path.exists()]
        if existing_paths:
            bases_detalle = ", ".join(path.name for path in existing_paths)
            raise FileNotFoundError(
                "No se encontraron registros de recorrido para el IMEI "
                f"{imei} en las bases consultadas ({bases_detalle})."
            )

        bases_detalle = ", ".join(path.name for path in searched_paths) or "(ninguna)"
        raise FileNotFoundError(
            "No se encontraron bases de datos de recorrido para el modelo "
            f"'{model_clean}'. Se buscaron: {bases_detalle}."
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
        help="Filtra por fecha local (YYYY-MM-DD) usando send_time. Usa 'All' para no filtrar",
    )
    parser.add_argument(
        "--operator",
        dest="operators",
        action="append",
        help="Filtra por operador (puede repetirse). Usa 'All' para incluir todos",
    )
    parser.add_argument(
        "--network",
        dest="networks",
        action="append",
        help="Filtra por tecnología de red (2G, 3G, 4G). Usa 'All' para incluir todas",
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
