"""Parser tests for GV310LAU +RESP/+BUFF:GTJDS messages."""

from queclink.parser import parse_line


RESP_SAMPLE = (
    "+RESP:GTJDS,6E0C03,868589060379784,GV310LAU,1,3,1,85.7,350,1206.3,"
    "-69.972567,-28.038460,20251016202522,0730,0001,0C82,00550412,00,"
    "20251016202522,8170$"
)


RESP_WITH_MASK = (
    "+RESP:GTJDS,6E0C03,868589060255190,GV310LAU,1,3,0,126.8,339,759.7,"
    "-70.625297,-33.348113,20251016202239,0730,0002,0517,00103625,0F,10,"
    "0.75,1.10,1.80,20251016202301,837A$"
)


BUFF_SAMPLE = (
    "+BUFF:GTJDS,6E0201,868589060079137,GV310LAU,2,5,0,0.0,249,117.2,"
    "-109.358792,-27.140638,20251016201343,,,,,00,20251016201442,8A0F$"
)


def test_parse_gtjds_resp_core_fields():
    data = parse_line(RESP_SAMPLE)

    assert data.get("header") == "+RESP:GTJDS"
    assert data.get("message") == "GTJDS"
    assert data.get("unique_id") == "868589060379784"
    assert data.get("device_name") == "GV310LAU"

    assert data.get("jamming_state") == 1
    assert data.get("jamming_net") == 3
    assert data.get("gnss_accuracy_level") == 1

    assert data.get("mcc") == "0730"
    assert data.get("mnc") == "0001"
    assert data.get("lac_hex") == "0C82"
    assert data.get("cell_id_hex") == "00550412"

    assert data.get("position_append_mask") == "00"
    assert data.get("satellites_in_use") is None
    assert data.get("horizontal_gnss_accuracy") is None
    assert data.get("vertical_gnss_accuracy") is None
    assert data.get("gnss_3d_accuracy") is None

    assert data.get("tail") == "$"


def test_parse_gtjds_resp_append_mask_fields():
    data = parse_line(RESP_WITH_MASK)

    assert data.get("header") == "+RESP:GTJDS"
    assert data.get("message") == "GTJDS"
    assert data.get("unique_id") == "868589060255190"

    assert data.get("position_append_mask") == "0F"
    assert data.get("satellites_in_use") == 10
    assert data.get("horizontal_gnss_accuracy") == 0.75
    assert data.get("vertical_gnss_accuracy") == 1.10
    assert data.get("gnss_3d_accuracy") == 1.80

    assert data.get("send_time") == "20251016202301"
    assert data.get("count_number") == "837A"


def test_parse_gtjds_buff_handles_missing_cellular_data():
    data = parse_line(BUFF_SAMPLE)

    assert data.get("header") == "+BUFF:GTJDS"
    assert data.get("message") == "GTJDS"
    assert data.get("unique_id") == "868589060079137"

    assert data.get("mcc") == ""
    assert data.get("mnc") == ""
    assert data.get("lac_hex") == ""
    assert data.get("cell_id_hex") == ""

    assert data.get("position_append_mask") == "00"
    assert data.get("tail") == "$"
