"""Generación de mapas interactivos por IMEI usando bases SQLite de reportes Queclink."""
from __future__ import annotations

import argparse
import json
import sqlite3
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - dependencia opcional en tiempo de ejecución
    import folium
    from folium import Map
    _FOLIUM_IMPORT_ERROR: ModuleNotFoundError | None = None
except ModuleNotFoundError as exc:  # pragma: no cover - entorno sin folium
    folium = None  # type: ignore[assignment]
    Map = None  # type: ignore[assignment]
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
    MCC_CANDIDATES,
    MNC_CANDIDATES,
    NETWORK_TYPE_CANDIDATES,
    NETWORK_TYPE_MAP,
    OPERATOR_CANDIDATES,
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
    report_kind: str = "RESP"
    mcc: Optional[int] = None
    mnc: Optional[int] = None
    raw_payload: Optional[dict] = None
    network_label: str = "Desconocida"
    signal_quality: str = "Desconocida"
    signal_dbm: Optional[float] = None
    csq: Optional[float] = None
    csq_ber: Optional[int] = None
    day_iso: Optional[str] = None


@dataclass
class InfoRecord:
    imei: str
    send_time: datetime
    network_label: str
    raw_network_value: Optional[int]
    csq: Optional[float] = None
    csq_ber: Optional[int] = None
    operator: str = "Desconocido"

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

_ASSOCIATION_MAX_DELTA_SECONDS = 60

# Tipos de reporte -----------------------------------------------------------


def _normalize_text(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:  # pragma: no cover - fallback de decodificación
            return value.decode("latin-1", errors="ignore")
    return str(value)


def _parse_send_time(value: object) -> Optional[datetime]:
    text = _normalize_text(value)
    if not text:
        return None
    if len(text) >= 14 and text[:14].isdigit():
        try:
            return datetime.strptime(text[:14], "%Y%m%d%H%M%S")
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _day_iso(value: Optional[datetime]) -> Optional[str]:
    return value.date().isoformat() if value else None


def _report_kind_from_header(header: object) -> str:
    text = _normalize_text(header).upper()
    if text.startswith("+BUFF:"):
        return "BUFFER"
    if text.startswith("+RESP:"):
        return "RESP"
    return "RESP"


# Utilidades internas --------------------------------------------------------


def _valid_coordinates(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0


def _swap_coordinates_if_needed(
    lat: float, lon: float, mcc: Optional[int]
) -> Tuple[float, float]:
    candidate_lat, candidate_lon = lon, lat
    swap_valid = _valid_coordinates(candidate_lat, candidate_lon)

    if swap_valid:
        if abs(lat) > 90.0 or abs(lon) > 180.0:
            return candidate_lat, candidate_lon
        if abs(lat) > abs(lon):
            return candidate_lat, candidate_lon

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

def _normalized_imei_value(value: object) -> str:
    if value in (None, ""):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    # Algunos archivos SQLite almacenan el IMEI como número en notación
    # científica (por ejemplo ``8.68589060824888e+14``). En esos casos
    # intentamos decodificarlo como entero antes de aplicar una limpieza
    # genérica para mantener la compatibilidad con bases históricas.
    if any(ch in text for ch in ".eE"):
        try:
            number = Decimal(text)
        except (InvalidOperation, ValueError):
            number = None
        else:
            if number == number.to_integral_value():
                return str(int(number))

    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return digits

    return "".join(ch for ch in text if ch.isalnum())


def _normalized_imei_expression(column: str) -> str:
    return f'normalize_imei("{column}")'


def _register_sqlite_helpers(conn: sqlite3.Connection) -> None:
    conn.create_function("normalize_imei", 1, _normalized_imei_value)


# Lectura de datos -----------------------------------------------------------


_LOCATION_COLUMN_CANDIDATES = {
    "imei": IMEI_CANDIDATES,
    "lat": ["lat"],
    "lon": ["lon"],
    "send_time": ["send_time"],
    "header": ["header"],
    "operator": ["operador"],
    "network": ["tecnologia_celular"],
    "signal_quality": ["calidad_senal"],
}


def _resolve_location_table(
    conn: sqlite3.Connection, report: str, model: str, imei: str
) -> tuple[str, dict[str, str]]:
    try:
        primary_table = _detect_table(conn, report, model, imei)
    except Exception:
        primary_table = None

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    table_names = [row[0] for row in rows]
    ordered_tables: List[str] = []
    if primary_table:
        ordered_tables.append(primary_table)
    for name in table_names:
        if name not in ordered_tables:
            ordered_tables.append(name)

    for table in ordered_tables:
        columns = _load_table_schema(conn, table)
        column_map: dict[str, str] = {}
        for key, candidates in _LOCATION_COLUMN_CANDIDATES.items():
            column = _first_existing(candidates, columns)
            if not column:
                column_map = {}
                break
            column_map[key] = column
        if column_map:
            return table, column_map

    raise ValueError(
        "No se encontró una tabla con las columnas requeridas para ubicaciones"
    )


def _load_locations_from_db(
    db_path: Path,
    report: str,
    model: str,
    imei: str,
) -> List[LocationPoint]:
    if not db_path.exists():
        return []

    conn = ensure_db(db_path)
    _register_sqlite_helpers(conn)
    conn.row_factory = sqlite3.Row
    try:
        table, column_map = _resolve_location_table(conn, report, model, imei)

        imei_col = column_map["imei"]
        lat_col = column_map["lat"]
        lon_col = column_map["lon"]
        time_col = column_map["send_time"]
        header_col = column_map["header"]
        operator_col = column_map["operator"]
        network_col = column_map["network"]
        signal_col = column_map["signal_quality"]

        sql = f"""
        SELECT
            "{header_col}" AS header,
            "{lat_col}" AS lat,
            "{lon_col}" AS lon,
            "{time_col}" AS send_time,
            "{operator_col}" AS operador,
            "{network_col}" AS tecnologia_celular,
            "{signal_col}" AS calidad_senal
        FROM "{table}"
        WHERE {_normalized_imei_expression(imei_col)} = :imei
        ORDER BY "{time_col}"
        """

        normalized_imei = _normalized_imei_value(imei)
        rows = conn.execute(sql, {"imei": normalized_imei}).fetchall()

        points: List[LocationPoint] = []
        for row in rows:
            raw_payload = dict(row)

            lat_value = raw_payload.get("latitude")
            if lat_value is None:
                lat_value = raw_payload.get("lat")
            lon_value = raw_payload.get("longitude")
            if lon_value is None:
                lon_value = raw_payload.get("lon")

            if lat_value is None or lon_value is None:
                raise ValueError(f"Fila sin lat/lon: {raw_payload}")

            lat = _safe_float(lat_value)
            lon = _safe_float(lon_value)
            send_dt = _parse_send_time(row["send_time"])
            if lat is None or lon is None or send_dt is None:
                continue

            lat = float(lat)
            lon = float(lon)

            if abs(lat) > 90.0 or abs(lon) > 180.0 or abs(lat) > abs(lon):
                lat, lon = lon, lat

            # Corrige lat/lon intercambiadas cuando aplique
            lat, lon = _swap_coordinates_if_needed(lat, lon, None)
            if not _valid_coordinates(lat, lon):
                continue
            operator_value = _normalize_text(row["operador"]).strip() or "Desconocido"
            network_label = _normalize_text(row["tecnologia_celular"]) or "Desconocida"
            signal_quality = _normalize_text(row["calidad_senal"]) or "Desconocida"
            points.append(
                LocationPoint(
                    lat=float(lat),
                    lon=float(lon),
                    send_time=send_dt,
                    imei=imei,
                    source=report.lower(),
                    operator=operator_value,
                    report_kind=_report_kind_from_header(row["header"]),
                    raw_payload=raw_payload,
                    network_label=network_label or "Desconocida",
                    signal_quality=signal_quality or "Desconocida",
                    day_iso=_day_iso(send_dt),
                )
            )
        return points
    finally:
        conn.close()


def _load_gtinf_records(db_path: Path, model: str, imei: str) -> List[InfoRecord]:
    if not db_path.exists():
        return []

    conn = ensure_db(db_path)
    _register_sqlite_helpers(conn)
    conn.row_factory = sqlite3.Row
    table = _detect_table(conn, "gtinf", model, imei)
    columns = _load_table_schema(conn, table)

    imei_col = _first_existing(IMEI_CANDIDATES, columns)
    time_col = _first_existing(TIME_CANDIDATES, columns)
    network_col = _first_existing(NETWORK_TYPE_CANDIDATES, columns)
    if not imei_col or not time_col or not network_col:
        raise ValueError(f"La tabla {table} no tiene columnas necesarias para GTINF")

    csq_col = _first_existing(CSQ_CANDIDATES, columns)
    ber_col = _first_existing(CSQ_BER_CANDIDATES, columns)
    operator_col = _first_existing(OPERATOR_CANDIDATES, columns)
    mcc_col = _first_existing(MCC_CANDIDATES, columns)
    mnc_col = _first_existing(MNC_CANDIDATES, columns)

    query_cols = {imei_col, time_col, network_col}
    if csq_col:
        query_cols.add(csq_col)
    if ber_col:
        query_cols.add(ber_col)
    if operator_col:
        query_cols.add(operator_col)
    if mcc_col:
        query_cols.add(mcc_col)
    if mnc_col:
        query_cols.add(mnc_col)

    imei_expr = _normalized_imei_expression(imei_col)
    select_clause = ", ".join(f'"{col}"' for col in query_cols)
    sql = (
        f'SELECT {select_clause} FROM "{table}" '
        f"WHERE {imei_expr} = ? ORDER BY \"{time_col}\""
    )

    normalized_imei = _normalized_imei_value(imei)
    info_records: List[InfoRecord] = []
    for row in conn.execute(sql, (normalized_imei,)):
        dt = _parse_datetime(row[time_col])
        if dt is None:
            continue
        raw_network = _safe_int(row[network_col])
        network_label = NETWORK_TYPE_MAP.get(raw_network, "Desconocida")
        csq = _safe_float(row[csq_col]) if csq_col else None
        csq_ber = _safe_int(row[ber_col]) if ber_col else None
        operator_value = "Desconocido"
        if operator_col:
            raw_operator = row[operator_col]
            if raw_operator not in (None, ""):
                operator_value = str(raw_operator).strip() or "Desconocido"
        if operator_value in ("", "Desconocido"):
            mcc_value = _safe_int(row[mcc_col]) if mcc_col else None
            mnc_value = _safe_int(row[mnc_col]) if mnc_col else None
            normalized = _normalize_operator(mcc_value, mnc_value)
            if normalized != "Desconocido" or operator_value == "":
                operator_value = normalized
        info_records.append(
            InfoRecord(
                imei=imei,
                send_time=dt,
                network_label=network_label,
                raw_network_value=raw_network,
                csq=csq,
                csq_ber=csq_ber,
                operator=operator_value or "Desconocido",
            )
        )
    conn.close()
    return info_records


# Sincronización -------------------------------------------------------------


def _associate_info(points: List[LocationPoint], infos: List[InfoRecord]) -> None:
    if not points or not infos:
        return
    infos_sorted = sorted(infos, key=lambda r: r.send_time)
    info_times = [record.send_time for record in infos_sorted]
    for point in sorted(points, key=lambda p: p.send_time):
        index = bisect_left(info_times, point.send_time)
        candidates: List[InfoRecord] = []
        if 0 <= index < len(infos_sorted):
            candidates.append(infos_sorted[index])
        if index > 0:
            candidates.append(infos_sorted[index - 1])

        chosen: Optional[InfoRecord] = None
        best_delta = float("inf")
        for candidate in candidates:
            delta = abs((candidate.send_time - point.send_time).total_seconds())
            if delta > _ASSOCIATION_MAX_DELTA_SECONDS:
                continue
            if chosen is None or delta < best_delta:
                chosen = candidate
                best_delta = delta
            elif delta == best_delta:
                if chosen.send_time > point.send_time >= candidate.send_time:
                    chosen = candidate

        if chosen is None:
            continue

        point.network_label = chosen.network_label
        point.csq = chosen.csq
        point.csq_ber = chosen.csq_ber
        quality, dbm = _classify_signal(
            chosen.network_label, chosen.csq, chosen.csq_ber
        )
        point.signal_quality = quality
        point.signal_dbm = dbm
        if chosen.operator and chosen.operator not in {"", "Desconocido"}:
            point.operator = chosen.operator


# Filtros --------------------------------------------------------------------


def _filter_points(
    points: List[LocationPoint],
    day: Optional[str] = None,
    report_types: Optional[Sequence[str]] = None,
    operators: Optional[Sequence[str]] = None,
    networks: Optional[Sequence[str]] = None,
) -> List[LocationPoint]:
    """Filtra puntos aplicando prioridad Día → Tipo → Operador/Tecnología."""

    normalized_ops = (
        {op.strip().lower() for op in operators if op is not None}
        if operators
        else None
    )
    normalized_networks = (
        {nt.strip().lower() for nt in networks if nt is not None}
        if networks
        else None
    )
    normalized_reports = (
        {rp.strip().lower() for rp in report_types if rp is not None}
        if report_types
        else None
    )

    day_value: Optional[datetime] = None
    if day:
        day_clean = day.strip()
        if day_clean.lower() not in {"all", "todos"}:
            try:
                day_value = datetime.strptime(day_clean, "%Y-%m-%d")
            except ValueError as exc:  # pragma: no cover - validación de CLI
                raise ValueError("El día debe tener formato YYYY-MM-DD") from exc

    if day_value is None:
        base_points = list(points)
    else:
        base_points = [
            point for point in points if point.send_time.date() == day_value.date()
        ]

    if normalized_reports and "all" not in normalized_reports and "ambos" not in normalized_reports:
        base_points = [
            point
            for point in base_points
            if (point.report_kind or "").lower() in normalized_reports
        ]

    operator_set = (
        None if not normalized_ops or "all" in normalized_ops else normalized_ops
    )
    network_set = (
        None if not normalized_networks or "all" in normalized_networks else normalized_networks
    )

    result: List[LocationPoint] = []
    for point in base_points:
        if operator_set and (point.operator or "").lower() not in operator_set:
            continue
        if network_set and (point.network_label or "").lower() not in network_set:
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
        f"Tipo de reporte: {point.report_kind}",
        f"Fecha envío: {point.send_time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Coordenadas: {point.lat:.5f}, {point.lon:.5f}",
        f"Operador: {point.operator}",
        f"Tecnología: {point.network_label}",
        f"Calidad de señal: {point.signal_quality}",
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


class FilterPanel(MacroElement):
    """Panel de filtros jerárquicos Día → Tipo → Operador/Tecnología."""

    def __init__(
        self,
        *,
        points_data: List[dict],
        day_options: List[str],
        report_options: List[str],
        operator_options: List[str],
        network_options: List[str],
        operator_colors: Dict[str, str],
        initial_day: str,
    ) -> None:
        if Template is None:  # pragma: no cover - dependencia opcional
            raise RuntimeError(
                "jinja2 es requerida para generar el panel de filtros interactivo"
            )
        super().__init__()
        self._name = "FilterPanel"
        self.points_json = json.dumps(points_data, ensure_ascii=False)
        self.operator_colors_json = json.dumps(operator_colors, ensure_ascii=False)
        self.day_options = day_options
        self.report_options = report_options
        self.operator_options = operator_options
        self.network_options = network_options
        self.initial_day = initial_day
        self._template = Template(
            """
            {% macro html(this, kwargs) %}
            <div id="{{ this.get_name() }}" class="filter-panel" data-filter-panel="interactive-filters"
                 style="position: fixed; top: 20px; left: 20px; z-index: 9999; background-color: white;"
                 >
                <div style="border: 1px solid #bbb; padding: 12px 14px; box-shadow: 0 2px 6px rgba(0,0,0,0.3); border-radius: 6px; width: 220px;">
                    <div style="font-weight: bold; margin-bottom: 8px; font-size: 14px;">Filtros</div>
                    <label for="{{ this.get_name() }}_day" style="display:block; font-weight:bold; margin-bottom:4px;">Día</label>
                    <select id="{{ this.get_name() }}_day" style="width:100%; margin-bottom:10px; padding:4px;">
                        <option value="All" {% if this.initial_day == "All" %}selected{% endif %}>Todos</option>
                        {% for day in this.day_options %}
                        <option value="{{ day }}" {% if day == this.initial_day %}selected{% endif %}>{{ day }}</option>
                        {% endfor %}
                    </select>
                    <label for="{{ this.get_name() }}_report" style="display:block; font-weight:bold; margin-bottom:4px;">Tipo de reporte</label>
                    <select id="{{ this.get_name() }}_report" style="width:100%; margin-bottom:10px; padding:4px;">
                        <option value="AMBOS" selected>AMBOS</option>
                        <option value="BUFFER">BUFFER</option>
                        <option value="RESP">RESP</option>
                    </select>
                    <label for="{{ this.get_name() }}_operator" style="display:block; font-weight:bold; margin-bottom:4px;">Operador</label>
                    <select id="{{ this.get_name() }}_operator" style="width:100%; margin-bottom:10px; padding:4px;">
                        <option value="All" selected>Todos</option>
                        {% for operator in this.operator_options %}
                        <option value="{{ operator }}">{{ operator }}</option>
                        {% endfor %}
                    </select>
                    <label for="{{ this.get_name() }}_network" style="display:block; font-weight:bold; margin-bottom:4px;">Tecnología</label>
                    <select id="{{ this.get_name() }}_network" style="width:100%; padding:4px;">
                        <option value="All" selected>Todos</option>
                        {% for network in this.network_options %}
                        <option value="{{ network }}">{{ network }}</option>
                        {% endfor %}
                    </select>
                </div>
            </div>
            {% endmacro %}

            {% macro script(this, kwargs) %}
            (function(){
              // --- utilidades para resolver map_/figure_ creados por Folium ---
              function _findFoliumMapKey() {
                for (var k in window) {
                  if (Object.prototype.hasOwnProperty.call(window, k) &&
                      /^map_[a-f0-9]+$/i.test(k) &&
                      window[k] && typeof window[k].fitBounds === "function") {
                    return k;
                  }
                }
                return null;
              }

              function _findFoliumFigureKey() {
                for (var k in window) {
                  if (Object.prototype.hasOwnProperty.call(window, k) &&
                      /^figure_[a-f0-9]+$/i.test(k) && window[k]) {
                    return k;
                  }
                }
                return null;
              }

              function _initFilterPanel() {
                var figKey = _findFoliumFigureKey();
                var mapKey = _findFoliumMapKey();
                if (!figKey || !mapKey) return setTimeout(_initFilterPanel, 50);
                var mapObj = window[mapKey];

                // Datos inyectados desde Python:
                const pointsData = {{ this.points_json | safe }};
                const operatorColors = {{ this.operator_colors_json | safe }};

                // Referencias a selects del panel de filtros
                const selDay = document.getElementById("{{ this.get_name() }}_day");
                const selReport = document.getElementById("{{ this.get_name() }}_report");
                const selOp = document.getElementById("{{ this.get_name() }}_operator");
                const selNet = document.getElementById("{{ this.get_name() }}_network");

                if (!selDay || !selReport || !selOp || !selNet) {
                  console.warn("[FilterPanel] No se encontraron los elementos select esperados");
                  return;
                }

                // Capa de trabajo que se repinta con cada cambio de filtros
                const layer = L.layerGroup().addTo(mapObj);

                function isAll(value) {
                  if (value == null) return true;
                  const normalized = String(value).trim().toLowerCase();
                  return normalized === "all" || normalized === "todos" || normalized === "ambos";
                }

                function repopulateDependent(dayValue) {
                  const base = isAll(dayValue)
                    ? pointsData
                    : pointsData.filter(function(point) { return point.day === dayValue; });

                  const operators = Array.from(new Set(
                    base.map(function(point) { return point.operator; }).filter(Boolean)
                  )).sort();
                  const networks = Array.from(new Set(
                    base.map(function(point) { return point.network; }).filter(Boolean)
                  )).sort();

                  function resetSelect(selectEl) {
                    if (!selectEl || !selectEl.options.length) return;
                    const first = selectEl.options[0];
                    selectEl.innerHTML = "";
                    selectEl.appendChild(first);
                  }

                  const previousOp = selOp.value;
                  const previousNet = selNet.value;

                  resetSelect(selOp);
                  resetSelect(selNet);

                  operators.forEach(function(operator) {
                    selOp.appendChild(new Option(operator, operator));
                  });
                  networks.forEach(function(network) {
                    selNet.appendChild(new Option(network, network));
                  });

                  // Intentar conservar la selección previa si sigue disponible
                  if (previousOp && selOp.querySelector('option[value="' + previousOp + '"]')) {
                    selOp.value = previousOp;
                  }
                  if (previousNet && selNet.querySelector('option[value="' + previousNet + '"]')) {
                    selNet.value = previousNet;
                  }
                }

                function applyFilters() {
                  const dayValue = selDay.value;
                  const reportValue = selReport.value;
                  const operatorValue = selOp.value;
                  const networkValue = selNet.value;

                  let filtered = pointsData.slice();
                  console.debug("[FilterPanel] total registros:", filtered.length);

                  if (!isAll(dayValue)) {
                    filtered = filtered.filter(function(point) {
                      return point.day === dayValue;
                    });
                  }
                  console.debug("[FilterPanel] tras día:", filtered.length);

                  if (!isAll(reportValue)) {
                    const reportNorm = String(reportValue).trim().toUpperCase();
                    filtered = filtered.filter(function(point) {
                      const value = point.report || "RESP";
                      return String(value).trim().toUpperCase() === reportNorm;
                    });
                  }
                  console.debug("[FilterPanel] tras tipo:", filtered.length);

                  if (!isAll(operatorValue)) {
                    const operatorNorm = String(operatorValue).trim().toLowerCase();
                    filtered = filtered.filter(function(point) {
                      const value = point.operator || "Desconocido";
                      return String(value).trim().toLowerCase() === operatorNorm;
                    });
                  }

                  if (!isAll(networkValue)) {
                    const networkNorm = String(networkValue).trim().toLowerCase();
                    filtered = filtered.filter(function(point) {
                      const value = point.network || "Desconocida";
                      return String(value).trim().toLowerCase() === networkNorm;
                    });
                  }
                  console.debug("[FilterPanel] final filtrado:", filtered.length);

                  layer.clearLayers();

                  if (!filtered.length) {
                    return;
                  }

                  const latlngs = [];
                  filtered.forEach(function(point) {
                    const latlng = [point.lat, point.lon];
                    latlngs.push(latlng);

                    const operatorColor = operatorColors[point.operator] || "#7f7f7f";
                    const marker = L.circleMarker(latlng, {
                      radius: 4,
                      color: operatorColor,
                      weight: 2,
                      fillOpacity: 0.7
                    });
                    if (point.tooltip) {
                      marker.bindTooltip(point.tooltip);
                    }
                    marker.addTo(layer);
                  });

                  if (latlngs.length === 1) {
                    mapObj.setView(latlngs[0], 13);
                  } else {
                    mapObj.fitBounds(latlngs, { padding: [24, 24] });
                  }
                }

                selDay.addEventListener("change", function() {
                  repopulateDependent(selDay.value);
                  applyFilters();
                });
                selReport.addEventListener("change", applyFilters);
                selOp.addEventListener("change", applyFilters);
                selNet.addEventListener("change", applyFilters);

                repopulateDependent(selDay.value);
                applyFilters();
              }

              if (document.readyState === "loading") {
                document.addEventListener("DOMContentLoaded", _initFilterPanel);
              } else {
                _initFilterPanel();
              }
            })();
            {% endmacro %}

            """
        )

    def render(self, **kwargs):  # type: ignore[override]
        """Renderiza el panel y reubica el bloque de scripts al final del body.

        Folium/Branca inserta por defecto los scripts de los MacroElement en el
        contenedor ``figure.script`` inmediatamente después de renderizar el
        elemento.  Para garantizar que el script del panel se ejecute una vez
        que ``figure_*`` y el mapa base ya han sido definidos, volvemos a
        insertar el bloque asociado al panel al final del contenedor de
        scripts.
        """

        parent_render = getattr(super(), "render", None)
        if parent_render is None:
            return

        parent_render(**kwargs)

        figure = getattr(self, "_parent", None)
        if figure is None:
            figure = self.get_root()

        script_container = getattr(figure, "script", None)
        if script_container is None:
            return

        children = getattr(script_container, "_children", None)
        if not isinstance(children, dict) or not children:
            return

        name_getter = getattr(self, "get_name", None)
        if name_getter is None:
            return

        script_key = None
        panel_name = name_getter()
        if panel_name in children:
            script_key = panel_name
        else:
            for key in children:
                if key.endswith(panel_name):
                    script_key = key
                    break

        if script_key is None:
            return

        script_element = children.pop(script_key)
        children[script_key] = script_element


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
    days = sorted({p.send_time.date().isoformat() for p in points_sorted})
    report_kinds = sorted({(p.report_kind or "RESP") for p in points_sorted})
    operators = sorted({(p.operator or "Desconocido") for p in points_sorted})
    networks = sorted({(p.network_label or "Desconocida") for p in points_sorted})

    points_payload = [
        {
            "lat": point.lat,
            "lon": point.lon,
            "day": point.day_iso or point.send_time.date().isoformat(),
            "report": point.report_kind,
            "operator": point.operator or "Desconocido",
            "network": point.network_label or "Desconocida",
            "signal_quality": point.signal_quality or "Desconocida",
            "tooltip": _point_to_tooltip(point),
            "timestamp": point.send_time.isoformat(),
        }
        for point in points_sorted
    ]

    initial_day = "All"

    fmap.get_root().add_child(
        FilterPanel(
            points_data=points_payload,
            day_options=days,
            report_options=report_kinds,
            operator_options=operators,
            network_options=networks,
            operator_colors=OPERATOR_COLORS,
            initial_day=initial_day,
        )
    )

    fmap.get_root().add_child(OperatorLegend(OPERATOR_COLORS))
    fmap.fit_bounds([[p.lat, p.lon] for p in points_sorted])

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

    # Mantén el comportamiento actual: por defecto solo GTERI.
    # (Si más adelante quieres soportar GTFRI por defecto, usa: ["gteri", "gtfri"])
    reports_to_use = [r.lower() for r in (reports or ["gteri"])]

    all_points: List[LocationPoint] = []
    searched_paths: List[Path] = []
    for report in reports_to_use:
        map_path = base_dir / f"{report}_{model_clean}_map.db"

        # 1) Si ya existe la base enriquecida *_map.db, leerla directamente.
        if map_path.exists():
            searched_paths.append(map_path)
            points = _load_locations_from_db(map_path, report, model_clean, imei)
            all_points.extend(points)
            continue

        # 2) Si no existe, intenta generar/ubicar la ruta con ensure_enriched_database
        try:
            enriched_path = ensure_enriched_database(
                report=report,
                model=model_clean,
                base_dir=base_dir,
                imei=imei,
            )
            searched_paths.append(enriched_path)
            points = _load_locations_from_db(enriched_path, report, model_clean, imei)
            all_points.extend(points)
        except FileNotFoundError:
            # Registrar la ruta buscada para un mensaje de error claro más adelante.
            searched_paths.append(map_path)
            # Continuar con el siguiente reporte sin abortar.
            pass

    if not all_points:
        existing_paths = list({path: None for path in searched_paths if path.exists()}.keys())
        if existing_paths:
            bases_detalle = ", ".join(path.name for path in existing_paths)
            raise FileNotFoundError(
                "No se encontraron registros de recorrido para el IMEI "
                f"{imei} en las bases consultadas ({bases_detalle})."
            )

        all_candidates = list({path: None for path in searched_paths}.keys())
        bases_detalle = ", ".join(path.name for path in all_candidates) or "(ninguna)"
        raise FileNotFoundError(
            "No se encontraron bases de datos de recorrido para el modelo "
            f"'{model_clean}'. Se buscaron: {bases_detalle}."
        )

    info_candidates = [
        base_dir / f"gtinf_{model_clean}_map.db",
        base_dir / f"gtinf_{model_clean}.db",
    ]
    info_path = next((path for path in info_candidates if path.exists()), info_candidates[0])
    info_records = _load_gtinf_records(info_path, model_clean, imei)
    if info_records:
        _associate_info(all_points, info_records)

    return sorted(all_points, key=lambda p: p.send_time)


def generate_map(
    *,
    model: str,
    imei: str,
    base_dir: Path | str = Path("bases_sqlite"),
    output_dir: Path | str = Path("."),
    day: Optional[str] = None,
    report_types: Optional[Sequence[str]] = None,
    operators: Optional[Sequence[str]] = None,
    networks: Optional[Sequence[str]] = None,
    reports: Optional[Sequence[str]] = None,
    tiles: str = "OpenStreetMap",
) -> Path:
    base_path = Path(base_dir)
    output_path = Path(output_dir)

    points = build_points(model=model, imei=imei, base_dir=base_path, reports=reports)
    filtered = _filter_points(
        points,
        day=day,
        report_types=report_types,
        operators=operators,
        networks=networks,
    )
    if not filtered:
        raise ValueError("Los filtros aplicados no devolvieron puntos para el mapa")

    html_name = f"mapa_{model.lower()}_{imei}.html"
    output_file = output_path / html_name
    render_interactive_map(filtered, output_file, tiles=tiles)
    return output_file


# CLI ------------------------------------------------------------------------


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un mapa interactivo por IMEI utilizando las bases gteri_map y gtinf_map",
    )
    parser.add_argument("--model", required=True, help="Modelo del equipo (ej. gv350ceu)")
    parser.add_argument("--imei", required=True, help="IMEI a consultar")
    parser.add_argument(
        "--db-dir",
        default="bases_sqlite",
        help="Directorio que contiene los archivos SQLite (por defecto bases_sqlite)",
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
        choices=["gteri"],
        help="Limita los reportes de posición a usar (solo se admite gteri)",
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
