from queclink.parser import parse_line


RESP_SAMPLE = (
    "+RESP:GTFRI,8020040900,866314061768998,GV58LAU,12714,50,1,1,0.0,235,2923.1,"\
    "-68.867600,-22.201688,20251016151536,0730,0001,0899,00542913,01,12,6537.2,"\
    "0000219:06:11,,,,100,220100,,,,20251016151537,591D$"
)


BUFF_SAMPLE_PDOP = (
    "+BUFF:GTFRI,8020040703,866314061771471,GV58LAU,28204,10,1,1,29.9,25,142.2,"\
    "-71.586724,-33.590164,20251015190846,,,,,08,0.69,1.11,1.30,659946.1,"\
    "0001265:29:11,,,,100,220100,,,,20251015190847,868C$"
)


def test_parse_gtfri_resp_basic_fields():
    data = parse_line(RESP_SAMPLE)

    assert data.get("header") == "+RESP:GTFRI"
    assert data.get("message") == "GTFRI"
    assert data.get("imei") == "866314061768998"
    assert data.get("device_name") == "GV58LAU"

    assert data.get("position_append_mask") == "01"
    assert data.get("sats_in_use") == 12
    assert data.get("mileage_km") == 6537.2

    assert data.get("count_number") == "591D"
    assert data.get("tail") == "$"


def test_parse_gtfri_buff_handles_pdop_bundle():
    data = parse_line(BUFF_SAMPLE_PDOP)

    assert data.get("header") == "+BUFF:GTFRI"
    assert data.get("position_append_mask") == "08"

    assert data.get("hdop") == 0.69
    assert data.get("vdop") == 1.11
    assert data.get("pdop_or_acc_factor") == 1.3

    assert data.get("count_number") == "868C"
    assert data.get("tail") == "$"
