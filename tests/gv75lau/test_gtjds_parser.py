"""Parser tests for GV75LAU +RESP/+BUFF:GTJDS messages."""

from queclink.parser import parse_line


RESP_SAMPLE = (
    "+RESP:GTJDS,80200C0300,135790246811220,GV75LAU,1,3,0,4.3,92,70.0,"
    "121.354335,31.222073,20230214013254,0460,0000,18d8,6141,05,1,220100,"
    "20230214093254,11F0$"
)


BUFF_SAMPLE = (
    "+BUFF:GTJDS,80200C0300,135790246811220,GV75LAU,2,3,0,0.0,0,0.0,-, -,"
    "20230214013254,,,,,00,20230214013254,11F1$"
)


def test_parse_gtjds_resp_core_fields():
    data = parse_line(RESP_SAMPLE)

    assert data.get("header") == "+RESP:GTJDS"
    assert data.get("message") == "GTJDS"
    assert data.get("unique_id") == "135790246811220"
    assert data.get("device_name") == "GV75LAU"

    assert data.get("jamming_status") == 1
    assert data.get("jamming_net") == 3
    assert data.get("gnss_accuracy_level") == 0

    assert data.get("mcc") == "0460"
    assert data.get("mnc") == "0000"
    assert data.get("lac_hex") == "18D8"
    assert data.get("cell_id_hex") == "6141"

    assert data.get("position_append_mask") == "05"
    assert data.get("satellites_in_use") == 1
    assert data.get("device_status") == "220100"

    assert data.get("send_time") == "20230214093254"
    assert data.get("count_number") == "11F0"
    assert data.get("tail") == "$"


def test_parse_gtjds_buff_handles_missing_values():
    data = parse_line(BUFF_SAMPLE)

    assert data.get("header") == "+BUFF:GTJDS"
    assert data.get("message") == "GTJDS"
    assert data.get("unique_id") == "135790246811220"

    assert data.get("jamming_status") == 2
    assert data.get("longitude_deg") is None
    assert data.get("latitude_deg") is None

    assert data.get("mcc") == ""
    assert data.get("mnc") == ""
    assert data.get("lac_hex") == ""
    assert data.get("cell_id_hex") == ""

    assert data.get("position_append_mask") == "00"
    assert data.get("satellites_in_use") is None
    assert data.get("device_status") is None

    assert data.get("send_time") == "20230214013254"
    assert data.get("count_number") == "11F1"
    assert data.get("tail") == "$"
