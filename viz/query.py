"""Consultas sobre la base SQLite para recorridos diarios."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional

try:
    import pytz  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - entorno sin pytz
    from zoneinfo import ZoneInfo

    class _ZoneInfoProxy:
        UTC = ZoneInfo("UTC")

        @staticmethod
        def timezone(name: str):
            return ZoneInfo(name)

    pytz = _ZoneInfoProxy()  # type: ignore

try:
    from dateutil import parser  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - entorno sin dateutil
    parser = None

UTC = pytz.UTC


def _localize_utc(dt: datetime) -> datetime:
    if hasattr(UTC, "localize"):
        return UTC.localize(dt)  # type: ignore[attr-defined]
    return dt.replace(tzinfo=UTC)


def _has_required_columns(conn: sqlite3.Connection, table: str) -> bool:
    required = {"lon", "lat", "gnss_utc", "is_buff", "report_type", "imei"}
    cur = conn.execute(f"PRAGMA table_info('{table}')")
    columns = {row[1] for row in cur.fetchall()}
    return required.issubset(columns)


def _resolve_table(conn: sqlite3.Connection) -> str:
    preferred = ["gteri_records", "records", "queclink_records"]
    for name in preferred:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (name,)
        )
        if cur.fetchone() and _has_required_columns(conn, name):
            return name

    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    candidates = [row[0] for row in cur.fetchall()]
    for name in candidates:
        if _has_required_columns(conn, name):
            return name

    tables = ", ".join(sorted(candidates)) or "<sin tablas>"
    raise RuntimeError(
        "No se encontró una tabla con columnas lon/lat/gnss_utc/is_buff/report_type/imei. "
        f"Tablas disponibles: {tables}"
    )


@dataclass
class TrackPoint:
    lon: float
    lat: float
    dt_local: datetime
    report_type: Optional[str]
    is_buffer: bool
    raw: dict

    def as_dict(self) -> dict:
        return {
            "lon": self.lon,
            "lat": self.lat,
            "dt_local": self.dt_local,
            "report_type": self.report_type,
            "is_buffer": self.is_buffer,
        }


def _normalize_date(local_date: date | datetime | str) -> date:
    if isinstance(local_date, date) and not isinstance(local_date, datetime):
        return local_date
    if isinstance(local_date, datetime):
        return local_date.date()
    if isinstance(local_date, str):
        try:
            if parser:
                return parser.parse(local_date).date()
            return datetime.fromisoformat(local_date).date()
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Fecha inválida: {local_date}") from exc
    raise TypeError("local_date debe ser date, datetime o str parseable")


def _parse_utc(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    candidates = ["%Y%m%d%H%M%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"]
    for fmt in candidates:
        try:
            dt = datetime.strptime(ts, fmt)
            return _localize_utc(dt)
        except ValueError:
            continue
    if parser:
        dt = parser.parse(ts)
        if dt.tzinfo is None:
            dt = _localize_utc(dt)
        else:
            dt = dt.astimezone(UTC)
        return dt
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            dt = datetime.strptime(ts, fmt)
            return _localize_utc(dt)
        except ValueError:
            continue
    raise ValueError(f"Timestamp inválido: {ts}")


def fetch_points_by_day(
    db_path: str,
    imei: str,
    local_date: date | datetime | str,
    tz: str = "America/Santiago",
) -> List[dict]:
    """Obtiene puntos para un día local específico ordenados por hora local."""

    target_date = _normalize_date(local_date)
    timezone = pytz.timezone(tz)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table = _resolve_table(conn)
        cur = conn.execute(
            f"""
            SELECT lon, lat, gnss_utc, is_buff, report_type
            FROM {table}
            WHERE imei = ? AND lon IS NOT NULL AND lat IS NOT NULL AND gnss_utc IS NOT NULL
            ORDER BY gnss_utc ASC
            """,
            (imei,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    points: List[TrackPoint] = []
    for row in rows:
        utc_dt = _parse_utc(str(row["gnss_utc"]))
        if not utc_dt:
            continue
        local_dt = utc_dt.astimezone(timezone)
        if local_dt.date() != target_date:
            continue
        lon_val = row["lon"]
        lat_val = row["lat"]
        try:
            lon_f = float(lon_val)
            lat_f = float(lat_val)
        except (TypeError, ValueError):
            continue
        track_point = TrackPoint(
            lon=lon_f,
            lat=lat_f,
            dt_local=local_dt,
            report_type=row["report_type"],
            is_buffer=bool(row["is_buff"]),
            raw=dict(row),
        )
        points.append(track_point)

    points.sort(key=lambda p: p.dt_local)
    return [p.as_dict() for p in points]


__all__ = ["fetch_points_by_day", "TrackPoint"]
