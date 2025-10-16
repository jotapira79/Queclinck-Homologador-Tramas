from queclink.parser import parse_line


RESP_SAMPLE = (
    "+RESP:GTFRI,6E0C03,868589060693259,GV310LAU,25194,10,1,1,0.0,16,440.5,"\
    "-70.309823,-23.760673,20251016180342,0730,0002,00CE,0985D171,00,183603.6,"\
    "0000748:27:41,,,,100,210100,,,,20251016180343,28C2$"
)


MASKED_SAMPLE = (
    "+RESP:GTFRI,6E0C03,868589060367029,GV310LAU,28177,10,1,1,86.1,84,793.1,"\
    "-70.088989,-23.450741,20251016180340,0730,0001,0837,002BED03,09,11,0.85,"\
    "1.15,1.43,89436.1,0001852:29:57,,,,100,220100,,,,20251016180342,A9B5$"
)


BUFF_SAMPLE = MASKED_SAMPLE.replace("+RESP", "+BUFF", 1)


def test_parse_gtfri_gv310lau_basic_optional_fields():
    data = parse_line(RESP_SAMPLE)

    assert data.get("header") == "+RESP:GTFRI"
    assert data.get("message") == "GTFRI"
    assert data.get("unique_id") == "868589060693259"
    assert data.get("device_name") == "GV310LAU"

    assert data.get("position_append_mask") == "00"
    assert data.get("satellites_in_use") is None
    assert data.get("backup_battery_percentage") == 100
    assert data.get("tail") == "$"


def test_parse_gtfri_gv310lau_with_append_mask_data():
    data = parse_line(MASKED_SAMPLE)

    assert data.get("position_append_mask") == "09"
    assert data.get("satellites_in_use") == 11
    assert data.get("horizontal_gnss_accuracy") == 0.85
    assert data.get("vertical_gnss_accuracy") == 1.15
    assert data.get("gnss_3d_accuracy") == 1.43
    assert data.get("count_number") == "A9B5"


def test_parse_gtfri_gv310lau_buff_header_supported():
    data = parse_line(BUFF_SAMPLE)

    assert data.get("header") == "+BUFF:GTFRI"
    assert data.get("message") == "GTFRI"
    assert data.get("unique_id") == "868589060367029"
