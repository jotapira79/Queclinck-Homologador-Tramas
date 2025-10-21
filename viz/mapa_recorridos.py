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
    LAT_CANDIDATES,
    LON_CANDIDATES,
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


REPORT_HEADER_CANDIDATES = [
    "header",
    "message_header",
    "msg_header",
    "message_type",
    "report_header",
]

REPORT_PAYLOAD_CANDIDATES = [
    "payload",
    "raw_payload",
    "raw_message",
    "message",
    "full_message",
    "raw",
]


def _normalize_text(value: object) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:  # pragma: no cover - fallback de decodificación
            return value.decode("latin-1", errors="ignore")
    return str(value)


def _detect_report_kind(raw_payload: Optional[dict]) -> str:
    """Intenta clasificar el mensaje como BUFFER o RESP."""

    if not raw_payload:
        return "RESP"

    def _match(text: str) -> Optional[str]:
        if not text:
            return None
        upper_text = text.upper()
        if "+BUFF:" in upper_text:
            return "BUFFER"
        if "+RESP:" in upper_text:
            return "RESP"
        return None

    for key in REPORT_HEADER_CANDIDATES:
        if key in raw_payload:
            kind = _match(_normalize_text(raw_payload.get(key)))
            if kind:
                return kind

    for key in REPORT_PAYLOAD_CANDIDATES:
        if key in raw_payload:
            kind = _match(_normalize_text(raw_payload.get(key)))
            if kind:
                return kind

    for value in raw_payload.values():
        kind = _match(_normalize_text(value))
        if kind:
            return kind

    return "RESP"


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
        table = _detect_table(conn, report, model, imei)
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

        imei_expr = _normalized_imei_expression(imei_col)
        select_clause = ", ".join(f'"{col}"' for col in query_cols)
        sql = (
            f'SELECT {select_clause} FROM "{table}" '
            f"WHERE {imei_expr} = ? ORDER BY \"{time_col}\""
        )

        points: List[LocationPoint] = []
        normalized_imei = _normalized_imei_value(imei)
        for row in conn.execute(sql, (normalized_imei,)):
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
                    report_kind=_detect_report_kind(raw_payload),
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
        if day_clean.lower() != "all":
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
                        <option value="All">Todos</option>
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
            (function() {
                var mapObj = {{ this._parent.get_name() }};
                var pointsData = {{ this.points_json | safe }};
                var operatorColors = {{ this.operator_colors_json | safe }};
                var panelId = "{{ this.get_name() }}";
                var daySelect = document.getElementById(panelId + "_day");
                var reportSelect = document.getElementById(panelId + "_report");
                var operatorSelect = document.getElementById(panelId + "_operator");
                var networkSelect = document.getElementById(panelId + "_network");
                var markersLayer = L.layerGroup().addTo(mapObj);
                var routeLayer = L.layerGroup().addTo(mapObj);
                var lastSelections = {
                    day: null,
                    report: null,
                    operator: null,
                    network: null
                };

                function colorForOperator(operator) {
                    if (operatorColors.hasOwnProperty(operator)) {
                        return operatorColors[operator];
                    }
                    if (operatorColors.hasOwnProperty("Desconocido")) {
                        return operatorColors["Desconocido"];
                    }
                    return "#7f7f7f";
                }

                function dominantOperator(points) {
                    var counts = {};
                    for (var idx = 0; idx < points.length; idx += 1) {
                        var current = points[idx].operator;
                        counts[current] = (counts[current] || 0) + 1;
                    }
                    var chosen = null;
                    var maxCount = -1;
                    for (var key in counts) {
                        if (!counts.hasOwnProperty(key)) {
                            continue;
                        }
                        if (counts[key] > maxCount) {
                            chosen = key;
                            maxCount = counts[key];
                        }
                    }
                    return chosen;
                }

                function collectUnique(points, key) {
                    var seen = {};
                    for (var i = 0; i < points.length; i += 1) {
                        var value = points[i][key];
                        if (value && !seen.hasOwnProperty(value)) {
                            seen[value] = true;
                        }
                    }
                    var values = [];
                    for (var candidate in seen) {
                        if (seen.hasOwnProperty(candidate)) {
                            values.push(candidate);
                        }
                    }
                    values.sort();
                    return values;
                }

                function populateSelect(selectElement, values, preserveSelection, extraOptions) {
                    var previousValue = preserveSelection ? selectElement.value : "All";
                    selectElement.innerHTML = "";
                    var allOption = document.createElement("option");
                    allOption.value = "All";
                    allOption.textContent = "Todos";
                    selectElement.appendChild(allOption);
                    if (extraOptions && extraOptions.length) {
                        for (var eo = 0; eo < extraOptions.length; eo += 1) {
                            var extra = extraOptions[eo];
                            var extraOption = document.createElement("option");
                            extraOption.value = extra.value;
                            extraOption.textContent = extra.label;
                            selectElement.appendChild(extraOption);
                        }
                    }
                    for (var i = 0; i < values.length; i += 1) {
                        var option = document.createElement("option");
                        option.value = values[i];
                        option.textContent = values[i];
                        selectElement.appendChild(option);
                    }
                    var normalizedPrevious = previousValue === "AMBOS" ? "All" : previousValue;
                    if (
                        preserveSelection &&
                        (
                            previousValue === "AMBOS" ||
                            values.indexOf(normalizedPrevious) !== -1
                        )
                    ) {
                        selectElement.value = previousValue;
                    } else {
                        selectElement.value = "All";
                    }
                    if (
                        selectElement.value !== "All" &&
                        values.indexOf(selectElement.value) === -1
                    ) {
                        selectElement.value = "All";
                    }
                }

                function populateReportSelect(points, preserveSelection) {
                    var availableValues = collectUnique(points, "report");
                    var availableSet = {};
                    for (var idx = 0; idx < availableValues.length; idx += 1) {
                        availableSet[availableValues[idx]] = true;
                    }
                    var previousValue = preserveSelection ? reportSelect.value : "AMBOS";
                    if (previousValue !== "BUFFER" && previousValue !== "RESP") {
                        previousValue = "AMBOS";
                    } else if (!availableSet[previousValue]) {
                        previousValue = "AMBOS";
                    }
                    var order = ["AMBOS", "BUFFER", "RESP"];
                    reportSelect.innerHTML = "";
                    for (var i = 0; i < order.length; i += 1) {
                        var option = document.createElement("option");
                        option.value = order[i];
                        option.textContent = order[i];
                        if (order[i] !== "AMBOS" && !availableSet[order[i]]) {
                            option.disabled = true;
                        }
                        reportSelect.appendChild(option);
                    }
                    reportSelect.value = previousValue;
                }

                function pointsForDay(dayValue) {
                    var normalizedDay = (dayValue || "").trim();
                    var dayPoints = [];
                    for (var i = 0; i < pointsData.length; i += 1) {
                        var point = pointsData[i];
                        var pointDay = (point.day || "").trim();
                        if (pointDay === normalizedDay) {
                            dayPoints.push(point);
                        }
                    }
                    return dayPoints;
                }

                function filterByReport(points, reportValue) {
                    if (!points.length) {
                        return [];
                    }
                    var normalizedReport = (reportValue || "").trim().toUpperCase();
                    if (!normalizedReport || normalizedReport === "AMBOS" || normalizedReport === "ALL") {
                        return points.slice();
                    }
                    var normalizedValue = normalizedReport;
                    var filtered = [];
                    for (var i = 0; i < points.length; i += 1) {
                        var pointReport = ((points[i].report || "").trim().toUpperCase());
                        if (pointReport === normalizedValue) {
                            filtered.push(points[i]);
                        }
                    }
                    return filtered;
                }

                function updateFilters() {
                    var selectedDay = daySelect.value;
                    var filtered = [];
                    var basePoints;

                    console.debug('[Filters] total points:', pointsData.length);
                    console.debug('[Filters] selectedDay:', selectedDay);

                    if (selectedDay && selectedDay !== "All") {
                        basePoints = pointsForDay(selectedDay);
                    } else {
                        basePoints = pointsData.slice();
                    }

                    console.debug('[Filters] basePoints:', basePoints.length);

                    var dayChanged = selectedDay !== lastSelections.day;
                    populateReportSelect(basePoints, !dayChanged);

                    var selectedReport = reportSelect.value || "AMBOS";
                    if (selectedReport === "AMBOS") {
                        selectedReport = "All";
                    }
                    console.debug('[Filters] selectedReport:', selectedReport);
                    var reportChanged = dayChanged || selectedReport !== lastSelections.report;

                    var reportFiltered = filterByReport(basePoints, selectedReport);
                    console.debug('[Filters] reportFiltered:', reportFiltered.length);

                    populateSelect(
                        operatorSelect,
                        collectUnique(reportFiltered, "operator"),
                        !reportChanged,
                        []
                    );
                    populateSelect(
                        networkSelect,
                        collectUnique(reportFiltered, "network"),
                        !reportChanged,
                        []
                    );


                    var opValue = operatorSelect.value || "All";
                    var netValue = networkSelect.value || "All";
                    console.debug('[Filters] operator value:', opValue, 'network value:', netValue);

                    for (var i = 0; i < reportFiltered.length; i += 1) {
                        var point = reportFiltered[i];
                        if (opValue !== "All" && point.operator !== opValue) {
                            continue;
                        }
                        if (netValue !== "All" && point.network !== netValue) {
                            continue;
                        }
                        filtered.push(point);
                    }

                    console.debug('[Filters] final filtered:', filtered.length);

                    filtered.sort(function(a, b) {
                        if (a.timestamp < b.timestamp) {
                            return -1;
                        }
                        if (a.timestamp > b.timestamp) {
                            return 1;
                        }
                        return 0;
                    });

                    markersLayer.clearLayers();
                    routeLayer.clearLayers();

                    if (filtered.length === 0) {
                        lastSelections.day = selectedDay || "All";
                        lastSelections.report = selectedReport;
                        lastSelections.operator = opValue;
                        lastSelections.network = netValue;
                        return;
                    }

                    var latLngs = [];
                    for (var j = 0; j < filtered.length; j += 1) {
                        var filteredPoint = filtered[j];
                        var markerColor = colorForOperator(filteredPoint.operator);
                        var markerRadius = filteredPoint.report === "BUFFER" ? 7 : 5;
                        var marker = L.circleMarker([filteredPoint.lat, filteredPoint.lon], {
                            radius: markerRadius,
                            color: markerColor,
                            weight: 2,
                            fillColor: markerColor,
                            fillOpacity: filteredPoint.report === "BUFFER" ? 0.95 : 0.85
                        });
                        if (filteredPoint.tooltip) {
                            marker.bindTooltip(filteredPoint.tooltip);
                        }
                        marker.addTo(markersLayer);
                        latLngs.push([filteredPoint.lat, filteredPoint.lon]);
                    }

                    if (latLngs.length === 1) {
                        mapObj.setView(latLngs[0], 15);
                    } else {
                        mapObj.fitBounds(latLngs, { padding: [30, 30] });
                    }

                    if (latLngs.length >= 2) {
                        var routeColor;
                        if (operatorSelect.value && operatorSelect.value !== "All") {
                            routeColor = colorForOperator(operatorSelect.value);
                        } else {
                            var dominant = dominantOperator(filtered);
                            routeColor = dominant ? colorForOperator(dominant) : "#7f7f7f";
                        }
                        L.polyline(latLngs, { color: routeColor, weight: 4, opacity: 0.6 }).addTo(routeLayer);
                    }

                    lastSelections.day = selectedDay || "All";
                    lastSelections.report = selectedReport;
                    lastSelections.operator = opValue;
                    lastSelections.network = netValue;
                }

                daySelect.addEventListener("change", updateFilters);
                reportSelect.addEventListener("change", updateFilters);
                operatorSelect.addEventListener("change", updateFilters);
                networkSelect.addEventListener("change", updateFilters);

                updateFilters();
            })();
            {% endmacro %}
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
    days = sorted({p.send_time.date().isoformat() for p in points_sorted})
    report_kinds = sorted({(p.report_kind or "RESP") for p in points_sorted})
    operators = sorted({(p.operator or "Desconocido") for p in points_sorted})
    networks = sorted({(p.network_label or "Desconocida") for p in points_sorted})

    points_payload = [
        {
            "lat": point.lat,
            "lon": point.lon,
            "day": point.send_time.date().isoformat(),
            "report": point.report_kind,
            "operator": point.operator or "Desconocido",
            "network": point.network_label or "Desconocida",
            "tooltip": _point_to_tooltip(point),
            "timestamp": point.send_time.isoformat(),
        }
        for point in points_sorted
    ]

    initial_day = days[0] if days else "All"

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

    reports_to_use = [r.lower() for r in (reports or ["gteri"])]
    all_points: List[LocationPoint] = []
    searched_paths: List[Path] = []
    for report in reports_to_use:
        candidate_paths = [
            base_dir / f"{report}_{model_clean}_map.db",
            base_dir / f"{report}_{model_clean}.db",
        ]
        db_path = next((path for path in candidate_paths if path.exists()), candidate_paths[0])
        try:
            enriched_path = ensure_enriched_database(
                report=report,
                model=model_clean,
                base_dir=base_dir,
                imei=imei,
            )
        except FileNotFoundError:
            searched_paths.extend(candidate_paths)
            continue

        searched_paths.append(enriched_path)
        points = _load_locations_from_db(enriched_path, report, model_clean, imei)
        all_points.extend(points)

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
