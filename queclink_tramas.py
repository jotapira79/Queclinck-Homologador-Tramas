"""CLI para homologar tramas Queclink usando las especificaciones YAML."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Iterable, Optional

from queclink.ingestor_sqlite import SQLiteIngestor
from queclink.parser import (
    HeadInfo,
    Spec,
    detect_model_from_identifiers,
    identify_head,
    load_spec,
    normalize_line_for_spec,
    parse_line,
)

_LOGGER = logging.getLogger(__name__)


def _split_fields(line: str) -> list[str]:
    payload = line.strip()
    if payload.endswith("$"):
        payload = payload[:-1]
    if not payload:
        return []
    return [part.strip() for part in payload.split(",")]


def _normalize_report_name(message: str) -> str:
    normalized = (message or "").strip().upper()
    if not normalized:
        return normalized
    if not normalized.startswith("GT"):
        normalized = f"GT{normalized}"
    return normalized


def _process_line(
    raw_line: str,
    ingestor: SQLiteIngestor,
    *,
    line_number: int,
    expected_report: Optional[str] = None,
) -> bool:
    head = identify_head(raw_line)
    if not head:
        _LOGGER.warning("Línea %s: encabezado no reconocido", line_number)
        return False

    if expected_report:
        normalized = _normalize_report_name(expected_report)
        if head.report.upper() != normalized:
            _LOGGER.debug(
                "Línea %s: se omitió trama %s por no coincidir con --message=%s",
                line_number,
                head.report,
                normalized,
            )
            return False

    fields = _split_fields(raw_line)
    if len(fields) < 3:
        _LOGGER.warning("Línea %s: trama sin IMEI", line_number)
        return False

    imei = fields[2]
    device_name = fields[3] if len(fields) > 3 else None
    model = detect_model_from_identifiers(imei, device_name)
    if not model:
        _LOGGER.warning(
            "Línea %s: identificadores de modelo no homologados (IMEI=%s, device_name=%s)",
            line_number,
            imei,
            device_name or "",
        )
        return False

    try:
        spec = load_spec(model, head.report)
    except FileNotFoundError:
        _LOGGER.warning(
            "Línea %s: no se encontró la spec para %s/%s", line_number, model, head.report
        )
        return False

    normalized_line = normalize_line_for_spec(raw_line, head.report, spec)

    try:
        record = parse_line(
            normalized_line,
            head.source,
            model,
            head.report,
            spec=spec,
            enrich=True,
        )
    except Exception as exc:  # pragma: no cover - errores de parsing específicos
        if head.report.upper() == "GTINF":
            record = _relaxed_gtinf_parse(normalized_line, spec)
            if record is None:
                _LOGGER.warning("Línea %s: error al parsear la trama (%s)", line_number, exc)
                return False
            _LOGGER.debug(
                "Línea %s: se aplicó parsing relajado para GTINF (%s)", line_number, exc
            )
        else:
            _LOGGER.warning("Línea %s: error al parsear la trama (%s)", line_number, exc)
            return False

    ingestor.insert(model, head.report, record, spec=spec)
    return True


def _relaxed_gtinf_parse(line: str, spec: Spec) -> Optional[dict[str, object]]:
    tokens = _split_fields(line)
    if len(tokens) < len(spec.fields):
        return None
    record: dict[str, object] = {}
    for field, token in zip(spec.fields, tokens):
        value: Optional[str] = token if token != "" else None
        record[field.name] = value
    record.setdefault("raw_line", line)
    return record


def _iter_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                yield stripped


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Homologador de tramas Queclink controlado por especificaciones YAML",
    )
    parser.add_argument("--in", dest="input", required=True, help="Archivo de tramas")
    parser.add_argument(
        "--out",
        dest="output",
        required=True,
        help="Ruta al archivo SQLite donde se guardarán los resultados",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Nivel de log a utilizar",
    )
    parser.add_argument(
        "--message",
        dest="message",
        help="Tipo de mensaje a homologar (por ejemplo GTINF, GTERI)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="[%(levelname)s] %(message)s")

    input_path = Path(args.input)
    output_path = Path(args.output)
    expected_report = _normalize_report_name(args.message) if args.message else None

    if not input_path.exists():
        print(f"[ERROR] No se encontró el archivo de entrada: {input_path}", file=sys.stderr)
        return 1

    ingestor = SQLiteIngestor(output_path)
    inserted = 0
    try:
        for line_number, line in enumerate(_iter_lines(input_path), start=1):
            if _process_line(
                line,
                ingestor,
                line_number=line_number,
                expected_report=expected_report,
            ):
                inserted += 1
    finally:
        ingestor.close()

    print(f"[OK] {inserted} tramas homologadas en {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

