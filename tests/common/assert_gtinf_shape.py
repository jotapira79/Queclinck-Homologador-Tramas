"""Helpers para validar la estructura de mensajes GTINF en pruebas."""

from __future__ import annotations

from queclink.messages.gtinf import parse_gtinf


def assert_gtinf_shape(raw_line: str, device: str) -> dict[str, str]:
    """Parsear una trama GTINF y devolver campos clave para las pruebas."""

    parsed = parse_gtinf(raw_line, device=device)
    assert parsed, f"No se pudo parsear la trama GTINF para {device}: {raw_line!r}"

    protocol_version = parsed.get("full_protocol_version")
    imei = parsed.get("imei")
    count_hex = parsed.get("count_hex")

    assert protocol_version, "La spec debe contener full_protocol_version"
    assert imei, "La spec debe contener IMEI"
    assert count_hex, "La spec debe contener count_hex"

    return {
        "protocol_version": str(protocol_version),
        "imei": str(imei),
        "count_hex": str(count_hex),
    }
