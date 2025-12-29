"""Funciones utilitarias compartidas entre los módulos de visualización."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence


NETWORK_TYPE_MAP = {
    0: "Sin servicio",
    1: "2G",
    2: "3G",
    3: "4G",
}

IMEI_CANDIDATES = ["imei", "unique_id", "uniqueid", "device_imei"]
LAT_CANDIDATES = [
    # Formatos genéricos
    "lat",
    "latitude",
    # Variantes en grados usadas por bases históricas (p.ej. ``latitude_deg``)
    "latitude_deg",
    "lat_deg",
    "latitude_degrees",
    "lat_degrees",
    # Variantes con sufijo ``_decimal`` que hemos encontrado en bases nuevas
    "lat_decimal",
    "latitude_decimal",
]
LON_CANDIDATES = [
    "lon",
    "longitude",
    "longitude_deg",
    "lon_deg",
    "longitude_degrees",
    "lon_degrees",
    "lon_decimal",
    "longitude_decimal",
    "lng",
    "lng_decimal",
    "lng_deg",
]
TIME_CANDIDATES = ["send_time", "gnss_utc_time", "timestamp", "created_at"]
MCC_CANDIDATES = ["mcc", "mobile_country_code"]
MNC_CANDIDATES = ["mnc", "mobile_network_code"]
OPERATOR_CANDIDATES = [
    "operador",
    "operator",
    "carrier",
    "operador_celular",
    "network_operator",
]
CSQ_CANDIDATES = ["csq", "csq_rssi", "csq_rsrp", "csq_rssi_rsrp", "lte_csq"]
CSQ_BER_CANDIDATES = ["csq_ber", "ber"]
NETWORK_TYPE_CANDIDATES = ["network_type", "rat", "network"]


def parse_datetime(value: object) -> Optional[datetime]:
    """Convierte representaciones comunes de fecha/hora en ``datetime``.

    Acepta cadenas en formatos típicos utilizados por los reportes Queclink,
    como ``YYYYMMDDHHMMSS`` o ISO 8601. Devuelve ``None`` si el valor está
    vacío o no puede interpretarse.
    """

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


def safe_float(value: object) -> Optional[float]:
    """Convierte un valor en ``float`` manejando nulos y errores."""

    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: object) -> Optional[int]:
    """Convierte un valor en ``int`` aceptando distintos formatos."""

    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        return int(value)

    text = str(value).strip()
    if not text:
        return None

    try:
        return int(text, 10)
    except ValueError:
        try:
            return int(text, 0)
        except ValueError:
            cleaned = text.lstrip("0").strip() or "0"
            try:
                return int(cleaned, 10)
            except ValueError:
                return None


def normalize_operator(mcc: Optional[int], mnc: Optional[int]) -> str:
    """Retorna el nombre del operador a partir de MCC/MNC."""

    if mnc is None:
        return "Desconocido"
    if mcc is not None and mcc != 730:
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


def csq_to_dbm(network_label: str, csq: Optional[float]) -> Optional[float]:
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


def classify_signal(
    network_label: str, csq: Optional[float], csq_ber: Optional[int]
) -> tuple[str, Optional[float]]:
    """Clasifica la calidad de señal y devuelve el valor en dBm."""

    dbm = csq_to_dbm(network_label, csq)
    if dbm is None:
        return "Desconocida", None
    if dbm >= -80:
        quality = "Excelente"
    elif dbm >= -90:
        quality = "Buena"
    elif dbm >= -100:
        quality = "Regular"
    else:
        quality = "Pésima"

    if network_label == "3G" and csq_ber is not None:
        if csq_ber >= 7:
            quality = "Pésima"
        elif csq_ber >= 5 and quality == "Excelente":
            quality = "Buena"

    return quality, dbm


def first_existing(
    candidates: Sequence[str], available: Iterable[str]
) -> Optional[str]:
    """Busca la primera columna candidata presente en ``available``."""

    available_lower = {name.lower(): name for name in available}
    for candidate in candidates:
        if candidate.lower() in available_lower:
            return available_lower[candidate.lower()]
    return None


def detect_table(conn, report: str, model: str, imei: str | None = None) -> str:
    """Detecta el nombre de tabla apropiado para un reporte/modelo/IMEI.

    Cuando ``imei`` se especifica, se priorizan nombres de tabla que la
    incluyan para soportar bases con particiones por dispositivo
    (``gteri_<modelo>_<imei>`` o ``gtinf_<modelo>_<imei>``). Si no se
    encuentra coincidencia exacta, se mantiene la heurística previa basada en
    ``reporte`` y ``modelo`` solamente.
    """

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = [row[0] for row in cursor.fetchall()]
    if not names:
        raise ValueError("La base de datos no tiene tablas")
    model_lower = model.lower()
    report_lower = report.lower()
    imei_candidates: list[str] = []
    if imei:
        imei_text = "".join(ch for ch in str(imei).strip() if ch.isalnum())
        if imei_text:
            imei_candidates = [
                f"{report_lower}_{model_lower}_{imei_text}",
                f"{report_lower}_{model}_{imei_text}",
                f"{report}_{model_lower}_{imei_text}",
                f"{report}_{model}_{imei_text}",
                f"{model_lower}_{report_lower}_{imei_text}",
                f"{model}_{report}_{imei_text}",
                f"{report_lower}_{imei_text}",
                f"{report}_{imei_text}",
            ]

    candidates = imei_candidates + [
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
    raise ValueError(
        f"No se encontró una tabla para {report}/{model}. Tablas: {', '.join(names)}"
    )


def load_table_schema(conn, table: str) -> list[str]:
    """Devuelve la lista de columnas definidas en ``table``."""

    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [row[1] for row in info]


__all__ = [
    "NETWORK_TYPE_MAP",
    "IMEI_CANDIDATES",
    "LAT_CANDIDATES",
    "LON_CANDIDATES",
    "TIME_CANDIDATES",
    "MCC_CANDIDATES",
    "MNC_CANDIDATES",
    "OPERATOR_CANDIDATES",
    "CSQ_CANDIDATES",
    "CSQ_BER_CANDIDATES",
    "NETWORK_TYPE_CANDIDATES",
    "classify_signal",
    "csq_to_dbm",
    "detect_table",
    "first_existing",
    "load_table_schema",
    "normalize_operator",
    "parse_datetime",
    "safe_float",
    "safe_int",
]
