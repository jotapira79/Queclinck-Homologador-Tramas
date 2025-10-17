#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generación de mapas interactivos por IMEI usando reportes Queclink."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import folium
import pandas as pd
from folium.plugins import MarkerCluster

OPERATOR_BY_MNC: Dict[str, str] = {
    "1": "Entel",
    "2": "Movistar",
    "3": "Claro",
}

NETWORK_COLORS = {
    "2G": "#1f77b4",
    "3G": "#ff7f0e",
    "4G": "#2ca02c",
}

QUALITY_COLORS = {
    "Pésima": "#d73027",
    "Regular": "#fc8d59",
    "Buena": "#fee08b",
    "Excelente": "#1a9850",
    "Desconocida": "#888888",
}


@dataclass
class TrackPoint:
    lat: float
    lon: float
    send_time: dt.datetime
    imei: str
    model: Optional[str]
    report: str
    operator: str
    network_type: Optional[str]
    signal_quality: str
    extra: Dict[str, Optional[str]]


class SQLiteLoader:
    """Utilidad para extraer DataFrames desde archivos SQLite."""

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise FileNotFoundError(db_path)
        self.db_path = db_path

    def fetch_table(self, table_name: str) -> pd.DataFrame:
        with sqlite3.connect(self.db_path) as conn:
            try:
                return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            except Exception as exc:  # pragma: no cover - sql error report
                available = pd.read_sql_query(
                    "SELECT name FROM sqlite_master WHERE type='table'", conn
                )
                raise RuntimeError(
                    f"No se pudo leer la tabla {table_name} en {self.db_path}. "
                    f"Tablas disponibles: {available['name'].tolist()}"
                ) from exc

    def autodetect_table(self, prefix: str) -> str:
        with sqlite3.connect(self.db_path) as conn:
            available = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table'", conn
            )["name"].tolist()
        candidates = [name for name in available if name.startswith(prefix)]
        if not candidates:
            raise RuntimeError(
                f"No se encontró una tabla que inicie con '{prefix}' en {self.db_path}."
            )
        if len(candidates) > 1:
            raise RuntimeError(
                f"Varias tablas coinciden con el prefijo '{prefix}' en {self.db_path}: {candidates}. "
                "Use --table si desea especificar una en particular."
            )
        return candidates[0]


def parse_day(value: Optional[str]) -> Optional[dt.date]:
    if not value:
        return None
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def ensure_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def detect_operator(mcc: Optional[str], mnc: Optional[str]) -> str:
    if mcc != "730" or not mnc:
        return "Desconocido"
    return OPERATOR_BY_MNC.get(str(mnc), "Desconocido")


def classify_signal(row: pd.Series) -> str:
    tech = (row.get("network_type") or "").upper()
    rssi = row.get("csq_rssi")
    ber = row.get("csq_ber")
    rsrp = row.get("rsrp")
    try:
        if pd.isna(rssi):
            rssi = None
        if pd.isna(ber):
            ber = None
        if pd.isna(rsrp):
            rsrp = None
    except Exception:
        pass

    if tech == "2G":
        if rssi is None:
            return "Desconocida"
        rssi = float(rssi)
        if rssi < 10:
            return "Pésima"
        if rssi < 15:
            return "Regular"
        if rssi < 20:
            return "Buena"
        return "Excelente"
    if tech == "3G":
        if rssi is None:
            return "Desconocida"
        rssi = float(rssi)
        if ber is not None:
            ber = float(ber)
        if rssi < 10 or (ber is not None and ber > 4):
            return "Pésima"
        if rssi < 15 or (ber is not None and ber > 3):
            return "Regular"
        if rssi < 20 or (ber is not None and ber > 1):
            return "Buena"
        return "Excelente"
    if tech == "4G":
        if rsrp is None:
            return "Desconocida"
        rsrp = float(rsrp)
        if rsrp <= -120:
            return "Pésima"
        if rsrp <= -110:
            return "Regular"
        if rsrp <= -95:
            return "Buena"
        return "Excelente"
    return "Desconocida"


def merge_with_info(track_df: pd.DataFrame, info_df: pd.DataFrame) -> pd.DataFrame:
    if info_df.empty:
        track_df["network_type"] = None
        track_df["csq_rssi"] = None
        track_df["csq_ber"] = None
        track_df["rsrp"] = None
        track_df["signal_quality"] = "Desconocida"
        return track_df

    info_df = info_df.copy()
    info_df["send_time_dt"] = ensure_datetime(info_df["send_time"])
    info_df = info_df.sort_values("send_time_dt")

    if "network_type" in info_df.columns:
        info_df["network_type"] = info_df["network_type"].str.upper()

    track_df = track_df.copy()
    track_df["send_time_dt"] = ensure_datetime(track_df["send_time"])
    track_df = track_df.sort_values("send_time_dt")

    merged = pd.merge_asof(
        track_df,
        info_df[
            [
                "send_time_dt",
                "network_type",
                "csq_rssi",
                "csq_ber",
                "rsrp",
                "send_time",
            ]
        ].rename(columns={"send_time": "gtinf_send_time"}),
        on="send_time_dt",
        direction="nearest",
    )
    merged["signal_quality"] = merged.apply(classify_signal, axis=1)
    return merged


def build_track_points(rows: pd.DataFrame, report: str) -> List[TrackPoint]:
    points: List[TrackPoint] = []
    for row in rows.itertuples(index=False):
        if pd.isna(row.lat) or pd.isna(row.lon):
            continue
        send_time_dt = getattr(row, "send_time_dt", None)
        if pd.isna(send_time_dt):
            continue
        operator = detect_operator(getattr(row, "mcc", None), getattr(row, "mnc", None))
        extra = {
            "speed_kmh": getattr(row, "speed_kmh", None),
            "mileage_km": getattr(row, "mileage_km", None),
            "operator": operator,
            "report": report,
            "gtinf_send_time": getattr(row, "gtinf_send_time", None),
            "csq_rssi": getattr(row, "csq_rssi", None),
            "csq_ber": getattr(row, "csq_ber", None),
            "rsrp": getattr(row, "rsrp", None),
        }
        points.append(
            TrackPoint(
                lat=float(row.lat),
                lon=float(row.lon),
                send_time=send_time_dt.to_pydatetime(),
                imei=str(getattr(row, "imei", "")),
                model=getattr(row, "model", None),
                report=report,
                operator=operator,
                network_type=getattr(row, "network_type", None),
                signal_quality=getattr(row, "signal_quality", "Desconocida"),
                extra=extra,
            )
        )
    return points


def load_track_points(
    base_dir: Path,
    model: str,
    imei: str,
    reports: Iterable[str],
    day: Optional[dt.date],
    gteri_table: Optional[str] = None,
    gtfri_table: Optional[str] = None,
    gtinf_table: Optional[str] = None,
) -> List[TrackPoint]:
    track_points: List[TrackPoint] = []
    info_df = pd.DataFrame()

    gtinf_db = base_dir / f"gtinf_{model}.db"
    if gtinf_db.exists():
        info_loader = SQLiteLoader(gtinf_db)
        table = gtinf_table or info_loader.autodetect_table("gtinf")
        info_df = info_loader.fetch_table(table)
        if "imei" in info_df.columns:
            info_df = info_df[info_df["imei"].astype(str) == str(imei)]

    for report in reports:
        db_path = base_dir / f"{report}_{model}.db"
        if not db_path.exists():
            continue
        loader = SQLiteLoader(db_path)
        table_hint = {
            "gteri": gteri_table,
            "gtfri": gtfri_table,
        }.get(report)
        table = table_hint or loader.autodetect_table(report)
        df = loader.fetch_table(table)
        if "imei" in df.columns:
            df = df[df["imei"].astype(str) == str(imei)]
        if "model" in df.columns:
            df = df[df["model"].astype(str) == str(model)]
        if df.empty:
            continue
        df["send_time_dt"] = ensure_datetime(df["send_time"])
        if day is not None:
            mask = df["send_time_dt"].dt.date == day
            df = df[mask]
        if df.empty:
            continue
        df = merge_with_info(df, info_df)
        track_points.extend(build_track_points(df, report))

    track_points.sort(key=lambda x: x.send_time)
    return track_points


def create_map(points: List[TrackPoint], output_path: Path) -> None:
    if not points:
        raise ValueError("No se encontraron puntos para el mapa.")
    center_lat = sum(p.lat for p in points) / len(points)
    center_lon = sum(p.lon for p in points) / len(points)
    fmap = folium.Map(location=(center_lat, center_lon), zoom_start=13)

    operator_groups: Dict[str, folium.map.FeatureGroup] = {}
    network_groups: Dict[str, folium.map.FeatureGroup] = {}
    cluster_groups: Dict[str, MarkerCluster] = {}

    for operator in sorted({p.operator for p in points}):
        group = folium.FeatureGroup(name=f"Operador: {operator}")
        group.add_to(fmap)
        operator_groups[operator] = group
        cluster = MarkerCluster(name=f"Puntos {operator}")
        cluster.add_to(group)
        cluster_groups[operator] = cluster

    for network in sorted({p.network_type or "Desconocido" for p in points}):
        group = folium.FeatureGroup(name=f"Red: {network}")
        group.add_to(fmap)
        network_groups[network] = group

    for point in points:
        network = point.network_type or "Desconocido"
        operator_group = operator_groups.get(point.operator)
        network_group = network_groups.get(network)
        cluster = cluster_groups.get(point.operator)

        tooltip_data = {
            "Fecha/Hora": point.send_time.isoformat(sep=" "),
            "Operador": point.operator,
            "Reporte": point.report.upper(),
            "Red": network,
            "Calidad": point.signal_quality,
        }
        tooltip_data.update(
            {
                k: v
                for k, v in point.extra.items()
                if v not in (None, "") and not (isinstance(v, float) and pd.isna(v))
            }
        )
        tooltip = "<br/>".join(f"<strong>{k}:</strong> {v}" for k, v in tooltip_data.items())
        marker_color = QUALITY_COLORS.get(point.signal_quality, QUALITY_COLORS["Desconocida"])
        circle = folium.CircleMarker(
            location=(point.lat, point.lon),
            radius=6,
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=0.9,
            tooltip=folium.Tooltip(tooltip, sticky=True),
        )
        if cluster is not None:
            cluster.add_child(circle)
        elif operator_group is not None:
            operator_group.add_child(circle)
        else:
            fmap.add_child(circle)

        if network_group is not None:
            duplicate = folium.CircleMarker(
                location=(point.lat, point.lon),
                radius=4,
                color=marker_color,
                fill=True,
                fill_color=marker_color,
                fill_opacity=0.8,
                tooltip=folium.Tooltip(tooltip, sticky=True),
            )
            network_group.add_child(duplicate)

    # Polylíneas por red
    sequences: Dict[str, List[List[Tuple[float, float]]]] = {}
    last_network: Optional[str] = None
    current: List[Tuple[float, float]] = []
    for point in points:
        network = point.network_type or "Desconocido"
        coords = (point.lat, point.lon)
        if last_network is None:
            current = [coords]
            last_network = network
            continue
        if network != last_network:
            if len(current) >= 2:
                sequences.setdefault(last_network, []).append(current)
            current = [coords]
            last_network = network
        else:
            current.append(coords)
    if last_network is not None and len(current) >= 2:
        sequences.setdefault(last_network, []).append(current)

    for network, segments in sequences.items():
        color = NETWORK_COLORS.get(network, "#444444")
        layer = network_groups.get(network, fmap)
        for coords in segments:
            polyline = folium.PolyLine(locations=coords, color=color, weight=4, opacity=0.7)
            layer.add_child(polyline)

    folium.LayerControl(collapsed=False).add_to(fmap)
    fmap.save(str(output_path))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera mapas interactivos de recorridos por IMEI a partir de bases SQLite"
    )
    parser.add_argument("--model", required=True, help="Modelo del equipo (ej: gv350ceu)")
    parser.add_argument("--imei", required=True, help="IMEI objetivo")
    parser.add_argument(
        "--reports",
        nargs="*",
        dest="reports",
        help="Reportes a utilizar (gteri, gtfri). Se puede listar varios",
    )
    parser.add_argument(
        "--report",
        action="append",
        dest="reports",
        help="Añade un reporte específico (opción repetible)",
    )
    parser.add_argument("--day", help="Filtrar por día (YYYY-MM-DD)")
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Directorio base donde se encuentran los archivos SQLite",
    )
    parser.add_argument(
        "--output",
        help="Ruta de salida del HTML. Por defecto mapa_<modelo>_<imei>.html en el directorio actual",
    )
    parser.add_argument("--gteri-table", help="Nombre explícito de la tabla GTERI en SQLite")
    parser.add_argument("--gtfri-table", help="Nombre explícito de la tabla GTFRI en SQLite")
    parser.add_argument("--gtinf-table", help="Nombre explícito de la tabla GTINF en SQLite")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    day = parse_day(args.day)
    reports = args.reports or ["gteri", "gtfri"]
    reports = [r.lower() for r in reports]

    points = load_track_points(
        base_dir=base_dir,
        model=args.model,
        imei=str(args.imei),
        reports=reports,
        day=day,
        gteri_table=args.gteri_table,
        gtfri_table=args.gtfri_table,
        gtinf_table=args.gtinf_table,
    )

    output_name = args.output
    if not output_name:
        suffix = f"_{day.isoformat()}" if day else ""
        output_name = f"mapa_{args.model}_{args.imei}{suffix}.html"
    output_path = Path(output_name)
    create_map(points, output_path)
    print(json.dumps({"output": str(output_path), "points": len(points)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
