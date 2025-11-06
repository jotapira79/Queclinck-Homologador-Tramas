"""Tests for GV75LAU GTFRI parser support."""

from queclink.parser import parse_line


RAW = [
    "+RESP:GTFRI,80200C0100,866314060583471,GV75LAU,10,1,12,45.6,180,12.3,-70.650123,-33.437200,20251029091530,0460,0000,1A2B,00FF,03,12345.6,20251029091533,1A2B$",
    "+BUFF:GTFRI,80200C0100,866314060583471,GV75LAU,11,1,8,0.0,0,0.0,-70.650100,-33.437100,20251029092000,0460,0000,1A2B,0003,08,0,13550,00012:35:07,20251029092002,3F7C$",
]


def test_gtfri_gv75lau_parse_line_resp_y_buff():
    for line in RAW:
        data = parse_line(line)
        assert data["message"] == "GTFRI"
        assert data.get("device") == "GV75LAU"
        assert data.get("model") == "GV75LAU"
        assert data.get("header") in {"+RESP:GT", "+BUFF:GT"}
        assert data.get("imei") == "866314060583471"
