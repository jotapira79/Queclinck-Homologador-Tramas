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
    detect_model_from_identifiers,
    identify_head,
    load_spec,
    model_from_imei,
    parse_line,
)
from queclink.messages.gteri import _parse_line_to_record as _gteri_parse_line
from queclink.parser import Spec

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


def _prepare_line_for_parsing(raw_line: str, head: HeadInfo) -> str:
    report = head.report or ""
    if not report.startswith("GT"):
        return raw_line
    suffix = report[2:]
    for prefix in ("+RESP:GT", "+BUFF:GT"):
        marker = f"{prefix}{suffix}"
        if raw_line.startswith(marker):
            return raw_line.replace(marker, f"{prefix},{suffix}", 1)
    return raw_line


def parse_line_to_record(raw_line: str) -> Optional[dict[str, object]]:
    record = _gteri_parse_line(raw_line)
    if record is not None:
        return record

    head = identify_head(raw_line)
    if not head:
        return None

    fields = _split_fields(raw_line)
    if len(fields) < 3:
        return None

    imei = fields[2]
    reported_device = fields[3] if len(fields) > 3 else None
    model = detect_model_from_identifiers(imei, reported_device) or model_from_imei(imei)
    if not model and reported_device:
        model = reported_device.strip().upper()
    if not model:
        return None

    try:
        spec = load_spec(model, head.report)
    except FileNotFoundError:
        return None

    normalized_line = _prepare_line_for_parsing(raw_line, head)
    try:
        return parse_line(normalized_line, head.source, model, head.report, spec=spec)
    except Exception:
        return None


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

    normalized_line = _prepare_line_for_parsing(raw_line, head)

    fields = _split_fields(raw_line)
    if len(fields) < 3:
        _LOGGER.warning("Línea %s: trama sin IMEI", line_number)
        return False

    imei = fields[2]
    model = model_from_imei(imei)
    if not model:
        _LOGGER.warning("Línea %s: prefijo IMEI no homologado (%s)", line_number, imei)
        return False

    try:
        spec = load_spec(model, head.report)
    except FileNotFoundError:
        _LOGGER.warning(
            "Línea %s: no se encontró la spec para %s/%s", line_number, model, head.report
        )
        return False

    aggregated_spec = None
    if expected_report:
        table_name = f"{expected_report.lower()}_records"
        aggregated_spec = Spec(
            model=spec.model,
            message=spec.message,
            table_name=table_name,
            delimiter=spec.delimiter,
            terminator=spec.terminator,
            fields=spec.fields,
            config=spec.config,
        )

    try:
        record = parse_line(normalized_line, head.source, model, head.report, spec=spec)
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
            if head.report.upper() == "GTERI":
                record = _gteri_parse_line(raw_line)
                if record is not None:
                    ingestor.insert(model, head.report, record, spec=spec)
                    if aggregated_spec is not None:
                        ingestor.insert(model, head.report, record, spec=aggregated_spec)
                    return True
            _LOGGER.warning("Línea %s: error al parsear la trama (%s)", line_number, exc)
            return False

    ingestor.insert(model, head.report, record, spec=spec)
    if aggregated_spec is not None:
        ingestor.insert(model, head.report, record, spec=aggregated_spec)
    return True


def _relaxed_gtinf_parse(line: str, spec: Spec) -> Optional[dict[str, object]]:
    tokens = _split_fields(line)
    record: dict[str, object] = {}
    token_iter = iter(tokens)
    for field in spec.fields:
        raw = next(token_iter, None)
        value: Optional[str] = raw if raw not in (None, "") else None
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

