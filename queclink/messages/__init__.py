"""Analizadores específicos por tipo de mensaje."""

from __future__ import annotations

from .gteri import parse_gteri
from .gtinf import parse_gtinf

__all__ = ["parse_gteri", "parse_gtinf"]
