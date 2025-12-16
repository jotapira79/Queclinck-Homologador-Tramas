import pytest

from queclink.parser import detect_model_from_identifiers, parse_line


@pytest.mark.parametrize(
    "line, expected_source, expected_report, expected_send_time",
    [
        (
            "+RESP:GTFRI,8020210100,868487004398921,GV30CAU,,10,1,1,26.6,66,21.2,117.248633,31.855967,20250307020609,0460,0000,5666,05C5DF2D,00,13.3,,,,,,220100,,,,20250307020611,2800$",
            "RESP",
            "GTFRI",
            "20250307020611",
        ),
        (
            "+BUFF:GTFRI,8020210100,868487004398921,GV30CAU,12000,10,1,5,60.0,180,50.0,117.129417,31.839262,20250307030323,0460,0001,DF5C,027A4F1F,03,12,2,12345.6,0000012:34:56,12000,0,0,80,220100,0,4,28,,20250307030325,00AF$",
            "BUFF",
            "GTFRI",
            "20250307030325",
        ),
        (
            "+RESP:GTERI,8020210100,868487004398475,GV30CAU,00008000,,10,1,1,0.0,183,151.1,117.129417,31.839262,20250307030112,0460,0001,DF5C,027A4F1F,00,13.6,,,,,,210100,,4,3,20250307030112,0ACC$",
            "RESP",
            "GTERI",
            "20250307030112",
        ),
        (
            "+BUFF:GTERI,8020210100,868487004398475,GV30CAU,00000000,12000,10,1,5,60.0,180,50.0,117.129417,31.839262,20250307030323,0460,0001,DF5C,027A4F1F,00,12345.6,000000,0000012:34:56,28,0,210100,,,,20250307030325,00AF$",
            "BUFF",
            "GTERI",
            "20250307030325",
        ),
        (
            "+RESP:GTINF,8020210200,868487004398475,GV30CAU,21,898600810906F8048812,28,0,1,12346,3,4.20,0,1,, ,20250314090748,03,12000,, ,03,01,+0000,0,20250314090751,0999$",
            "RESP",
            "GTINF",
            "20250314090751",
        ),
        (
            "+RESP:GTJDS,8020210100,868487004398970,GV30CAU,1,3,0,0.0,190,189.3,117.129604,31.837816,20250303071543,0460,0001,DF5C,05FE6667,00,20250303072530,0139$",
            "RESP",
            "GTJDS",
            "20250303072530",
        ),
    ],
)
def test_parse_line_gv30cau_reports(line, expected_source, expected_report, expected_send_time):
    parsed = parse_line(line)

    assert parsed["report"] == expected_report
    assert parsed["source"] == expected_source
    assert parsed["model"] == "GV30CAU"
    assert parsed["imei"].startswith("868487004")
    assert parsed["send_time"] == expected_send_time

    if expected_report == "GTERI":
        assert "eri_mask" in parsed


def test_detect_model_uses_longer_gv30cau_prefix_when_no_device_name():
    imei = "868487004398475"
    detected = detect_model_from_identifiers(imei, None)

    assert detected == "GV30CAU"
