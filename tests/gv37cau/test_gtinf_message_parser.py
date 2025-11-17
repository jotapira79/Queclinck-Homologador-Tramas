from queclink.messages.gtinf import parse_gtinf


def test_parse_gtinf_resp_gv37cau():
    line = (
        "+RESP:GTINF,8020230100,868487004398475,GV37CAU,21,898600810906F8048812,20,0,1,12000,,4.10,1,1,,1,"
        "20250314090000,,12345,,01,00,+0000,0,20250314090005,0001$"
    )

    homologated = parse_gtinf(line)

    assert homologated["header"] == "+RESP:GTINF"
    assert homologated["imei"] == "868487004398475"
    assert homologated["device_name"] == "GV37CAU"
    assert homologated["send_time"] == "20250314090005"
    assert homologated["count_number"] == "0001"


def test_parse_gtinf_buff_gv37cau_without_device_name():
    line = (
        "+BUFF:GTINF,4B0303,868487004398475,,21,898600810906F8048812,28,0,1,12346,,4.20,0,0,,1,"
        "20250314090748,,23000,,01,01,+0000,0,20250314090751,0999$"
    )

    homologated = parse_gtinf(line)

    assert homologated["header"] == "+BUFF:GTINF"
    assert homologated["imei"] == "868487004398475"
    assert homologated["device_name"] is None
    assert homologated["send_time"] == "20250314090751"
    assert homologated["count_number"] == "0999"
