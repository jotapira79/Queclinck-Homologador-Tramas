from queclink.parser import parse_line


def test_gteri_one_wire_count_missing_defaults_to_zero():
    line = (
        "+RESP:GT,ERI,740904,862524060876527,GV350CEU,00000002,,10,1,1,71.4,195,127.3,"
        "-70.278081,-22.932350,20251013124444,0730,0001,0AF1,00A0F802,01,12,785403.4,"
        "0000399:46:38,,,,100,221100,0,0,20251013124445,8822$"
    )

    record = parse_line(line, source="RESP", model="gv350ceu", message="GTERI")

    assert record["one_wire_device_number"] == 0
    assert "one_wire_devices" not in record or record["one_wire_devices"] == []
    assert record["send_time"] == "20251013124445"
    assert record["count_hex"] == "8822"
