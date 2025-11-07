"""Tests for GV75LAU GTFRI parser support."""

from queclink.parser import parse_line


RAW = [
    (
        "+RESP:GTFRI,80200C0300,866314060583471,GV75LAU,10,1,12,45.6,180,12.3,"
        "-70.650123,-33.437200,20251029091530,0460,0000,1A2B,00FF,03,12,3,12345.6,"
        "00012:35:07,,,,85,221102,,,,20251029091533,1A2B$"
    ),
    (
        "+BUFF:GTFRI,80200C0300,866314060583471,GV75LAU,11,1,8,0.0,0,0.0,"
        "-70.650100,-33.437100,20251029092000,0460,0000,1A2B,0003,03,10,1,13550.0,"
        "00012:35:07,,,,100,210100,,,,20251029092002,3F7C$"
    ),
]


def test_gtfri_gv75lau_parse_line_resp_y_buff():
    for line in RAW:
        data = parse_line(line)
        assert data["message"] == "GTFRI"
        assert data.get("device") == "GV75LAU"
        assert data.get("model") == "GV75LAU"
        assert data.get("header") in {"+RESP:GT", "+BUFF:GT"}
        assert data.get("imei") == "866314060583471"
        assert data.get("position_append_mask") == "03"
        assert data.get("satellites_used") in {12, 10}
        assert data.get("gnss_trigger_type") in {3, 1}
        assert data.get("backup_battery_percentage") in {85, 100}
        assert data.get("device_status") in {"221102", "210100"}


def test_gtfri_gv75lau_optional_ext_power_before_report_id():
    line = (
        "+RESP:GTFRI,80200C0201,866314062233117,GV75LAU,,50,1,1,0.0,14,605.5,"
        "-70.638090,-33.433986,20251104153233,0730,0003,9C50,DF0D,03,12,3,45300.0,,,,,100,210100,,,,20251104153234,0FD9$"
    )

    data = parse_line(line)

    assert data.get("report_id_type") == "50"
    assert data.get("number") == 1
    assert data.get("ext_power_mv") is None
    assert data.get("satellites_used") == 12
    assert data.get("gnss_trigger_type") == 3
    assert data.get("backup_battery_percentage") == 100
    assert data.get("device_status") == "210100"
