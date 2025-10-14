"""Compatibilidad para importar ``parse_gteri`` desde ``queclink.gteri``."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .parser import parse_gteri as _parse_gteri

__all__ = ["parse_gteri"]


def parse_gteri(line: str, source: str = "RESP", device: Optional[str] = None) -> Dict[str, Any]:
    return _parse_gteri(line, source=source, device=device)
