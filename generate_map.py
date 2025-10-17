"""Script de conveniencia para generar mapas interactivos por IMEI."""
from __future__ import annotations

from typing import Optional, Sequence

from viz.mapa_recorridos import main as _map_main


def main(argv: Optional[Sequence[str]] = None) -> None:
    _map_main(argv)


if __name__ == "__main__":  # pragma: no cover - script manual
    main()
