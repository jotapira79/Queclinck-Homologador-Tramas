import pytest

from queclink.parser import parse_line

RAW_WITH_UNMASKED_DOPS = (
    "+RESP:GTERI,6E0902,868589060824888,GV310LAU,00000002,14778,10,1,1,12.0,40,381.6," \
    "-70.331679,-27.366874,20251016235959,0730,0002,012F,08164920,09,12,0.83,1.64,1.83,600.0," \
    "0000015:21:09,,,,100,220100,0,0,20251017000001,3111$"
)

RAW_WITHOUT_DOPS = (
    "+RESP:GTERI,6E0C03,868589060707695,GV310LAU,00000002,12797,10,1,1,0.0,348,479.8," \
    "-70.775486,-33.431415,20251023201230,0730,0001,333C,00B24D03,00,17558.1,0001138:26:28,,,,100,110000," \
    "0,0,20251023201458,A4C5$"
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


def test_parse_line_skips_forced_dops_outside_range_gv310lau():
    data = parse_line(RAW_WITHOUT_DOPS)

    assert "hdop" not in data or data["hdop"] is None
    assert data["mileage_km"] == pytest.approx(17558.1)
    assert data["hour_meter"] == "0001138:26:28"
    assert data["backup_battery_pct"] == 100
