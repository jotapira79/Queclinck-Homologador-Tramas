"""Mantenimiento de bases SQLite enriquecidas para recorridos por IMEI."""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from .enriched_db import ensure_enriched_database

_DEFAULT_REPORTS: tuple[str, ...] = ("gteri", "gtfri")


def _normalize_report(report: str) -> str:
    value = report.strip().lower()
    if not value:
        raise ValueError("El nombre del reporte no puede estar vacío")
    return value


def ensure_map_databases(
    *,
    model: str,
    base_dir: Path | str = Path("bases_sqlite"),
    reports: Optional[Sequence[str]] = None,
    strict: bool = False,
) -> Dict[str, Path]:
    """Garantiza que existan las bases enriquecidas para los reportes solicitados.

    Retorna un diccionario ``{reporte: ruta}`` con las bases _map actualizadas.
    Si ``strict`` es ``False`` (por defecto) se omiten los reportes cuyo origen
    no esté disponible y se emite una advertencia. Cuando es ``True`` la
    función propaga la excepción ``FileNotFoundError`` correspondiente.
    """

    model_clean = model.strip().lower()
    if not model_clean:
        raise ValueError("El modelo no puede estar vacío")

    base_path = Path(base_dir)
    report_names: Iterable[str]
    if reports is None:
        report_names = _DEFAULT_REPORTS
    else:
        report_names = [_normalize_report(name) for name in reports]

    results: Dict[str, Path] = {}
    missing: list[str] = []

    for report in report_names:
        try:
            results[report] = ensure_enriched_database(
                report=report, model=model_clean, base_dir=base_path
            )
        except FileNotFoundError as exc:
            if strict:
                raise
            warnings.warn(
                (
                    f"No se encontró la base origen para el reporte '{report}' "
                    f"del modelo '{model_clean}': {exc}"
                ),
                RuntimeWarning,
                stacklevel=2,
            )
            missing.append(report)

    if not results:
        if missing:
            missing_list = ", ".join(sorted(missing))
            raise FileNotFoundError(
                "No se encontraron bases disponibles para los reportes solicitados "
                f"({missing_list})."
            )
        raise FileNotFoundError(
            "No se pudieron generar bases enriquecidas con los parámetros dados"
        )

    return results


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Genera o actualiza las bases SQLite enriquecidas (gteri/gtfri) "
            "cruzadas con GTINF para un modelo e IMEIs dados."
        )
    )
    parser.add_argument("--model", required=True, help="Modelo del equipo (ej. gv350ceu)")
    parser.add_argument(
        "--db-dir",
        default="bases_sqlite",
        help="Directorio que contiene las bases SQLite originales",
    )
    parser.add_argument(
        "--report",
        dest="reports",
        action="append",
        help="Reportes a procesar (por defecto gteri y gtfri)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Falla si alguno de los reportes solicitados no está disponible",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    try:
        results = ensure_map_databases(
            model=args.model,
            base_dir=Path(args.db_dir),
            reports=args.reports,
            strict=args.strict,
        )
    except FileNotFoundError as exc:  # pragma: no cover - errores de ejecución
        raise SystemExit(str(exc)) from exc

    for report, path in sorted(results.items()):
        print(f"[{report}] Base enriquecida lista en: {path}")


__all__ = ["ensure_map_databases", "main"]


if __name__ == "__main__":  # pragma: no cover - punto de entrada CLI
    main()
