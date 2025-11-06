"""Paquete principal del analizador Queclink."""

from __future__ import annotations

from .parser import (
    detect_model_from_identifiers,
    identify_head,
    load_spec,
    model_from_imei,
    normalize_line_for_spec,
    parse_line,
)

__all__ = [
    "identify_head",
    "load_spec",
    "model_from_imei",
    "detect_model_from_identifiers",
    "normalize_line_for_spec",
    "parse_line",
]
