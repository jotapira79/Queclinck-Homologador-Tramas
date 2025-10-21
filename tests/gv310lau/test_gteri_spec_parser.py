import pytest

from queclink.parser import parse_line

RAW_WITH_UNMASKED_DOPS = (
    "+RESP:GTERI,6E0902,868589060824888,GV310LAU,00000002,14778,10,1,1,12.0,40,381.6," \
    "-70.331679,-27.366874,20251016235959,0730,0002,012F,08164920,09,12,0.83,1.64,1.83,600.0," \
    "0000015:21:09,,,,100,220100,0,0,20251017000001,3111$"
)


def test_parse_line_handles_unmasked_dops_gv310lau():
    data = parse_line(RAW_WITH_UNMASKED_DOPS)
    assert data["sats_in_use"] == 12
    assert data["hdop"] == pytest.approx(0.83)
    assert data["vdop"] == pytest.approx(1.64)
    assert data["pdop"] == pytest.approx(1.83)
    assert data["mileage_km"] == pytest.approx(600.0)
    assert data["hour_meter"] == "0000015:21:09"
    assert data["device_status"] == "220100"
    assert data["uart_device_type"] == 0
    assert data["send_time"] == "20251017000001"
    assert data["count_hex"] == "3111"
