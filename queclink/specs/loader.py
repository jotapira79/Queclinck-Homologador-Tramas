"""Utilidades para localizar especificaciones de mensajes Queclink."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Iterator, List


def get_spec_path(report: str, device: str) -> str:
    """Devolver la ruta relativa al archivo de especificación."""
    if not report or not device:
        raise ValueError("Se requieren el nombre del reporte y del dispositivo")
    report_norm = report.strip().lower()
    device_norm = device.strip().lower()
    if not report_norm or not device_norm:
        raise ValueError("Los parámetros report y device no pueden ser vacíos")
    return str(Path("spec") / device_norm / f"{report_norm}.yml")


_INLINE_FIELD_RE = re.compile(r"name\s*:\s*([^,}]+)")


def _iter_field_lines(lines: Iterable[str]) -> Iterator[str]:
    inside_fields = False
    fields_indent = 0
    for raw_line in lines:
        line = raw_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())
        if stripped.startswith("fields:"):
            inside_fields = True
            fields_indent = indent
            continue

        if inside_fields:
            if indent <= fields_indent:
                inside_fields = False
                continue
            if indent > fields_indent and stripped.startswith("-"):
                yield stripped
            continue


def _extract_field_name(entry: str) -> str | None:
    if entry.startswith("- {"):
        match = _INLINE_FIELD_RE.search(entry)
        if not match:
            return None
        value = match.group(1)
    elif entry.startswith("-"):
        parts = entry.split(":", 1)
        if len(parts) != 2:
            return None
        value = parts[1]
    else:
        return None
    value = value.split("#", 1)[0].strip()
    return value.strip('"\'') or None


def load_spec_columns_from_path(spec_path: str | Path) -> List[str]:
    """Leer un archivo de spec y devolver sus columnas en orden."""

    spec_file = Path(spec_path)
    if not spec_file.exists():
        raise FileNotFoundError(spec_file)

    columns: List[str] = []
    for entry in _iter_field_lines(spec_file.read_text(encoding="utf-8").splitlines()):
        name = _extract_field_name(entry)
        if name:
            columns.append(name)
    return columns


def get_spec_columns(report: str, device: str) -> List[str]:
    """Obtener el listado de columnas definidas en la spec en orden."""

    spec_path = Path(get_spec_path(report, device))
    return load_spec_columns_from_path(spec_path)


__all__ = ["get_spec_path", "get_spec_columns", "load_spec_columns_from_path"]
