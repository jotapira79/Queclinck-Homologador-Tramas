"""Tests for GV350CEU GTFRI parser support."""

from queclink.parser import parse_line


RESP_SAMPLE = (
    "+RESP:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.5,169,672.9,"\
    "-70.292914,-23.949947,20251016184033,0730,0001,0836,002BEE06,01,12,"\
    "775824.1,0000439:30:29,,,,100,221102,,,,20251016184035,AA3C$"
)


BUFF_SAMPLE = (
    "+BUFF:GTFRI,740904,862524060867948,GV350CEU,,10,1,1,89.6,168,690.2,"\
    "-70.291068,-23.958760,20251016184113,0730,0001,0836,002BEE06,01,12,"\
    "775825.1,0000439:31:11,,,,100,221102,,,,20251016184115,AA41$"
)


def test_parse_gtfri_gv350ceu_resp_core_fields():
    data = parse_line(RESP_SAMPLE)

    assert data.get("header") == "+RESP:GTFRI"
    assert data.get("message") == "GTFRI"
    assert data.get("unique_id") == "862524060867948"
    assert data.get("device_name") == "GV350CEU"

    assert data.get("position_append_mask") == "01"
    assert data.get("satellites_in_use") == 12
    assert data.get("mileage_km") == 775824.1

    assert data.get("analog_in_1") is None
    assert data.get("analog_in_2") is None
    assert data.get("analog_in_3") is None
    assert data.get("backup_battery_percentage") == 100

    assert data.get("count_number") == "AA3C"
    assert data.get("tail") == "$"


def test_parse_gtfri_gv350ceu_buff_tail_fields():
    data = parse_line(BUFF_SAMPLE)

    assert data.get("header") == "+BUFF:GTFRI"
    assert data.get("message") == "GTFRI"
    assert data.get("unique_id") == "862524060867948"

    assert data.get("send_time") == "20251016184115"
    assert data.get("count_number") == "AA41"
    assert data.get("tail") == "$"

