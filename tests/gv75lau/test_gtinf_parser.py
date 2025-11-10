from queclink import parse_line
from tests.common.assert_gtinf_shape import assert_gtinf_shape


RAW_WITH_ONE_WIRE = "+RESP:GTINF,80200C0100,866314060583471,GV75LAU,11,8956012345678901234,27,0,1,13250,4,4.08,0,2,,20251029091530,0F,01,00,+0000,0,0001,1,0011223344556677,1,7F00,20251029091533,6B91$"

RAW = [
    "+RESP:GTINF,80200C0100,866314060583471,GV75LAU,11,8956012345678901234,27,0,1,13250,4,4.08,0,,,20251029091530,0F,01,00,+0000,0,20251029091533,6B91$",
    "+BUFF:GTINF,80200C0100,866314060583471,GV75LAU,12,8935711001088072340f,38,7,1,27890,,4.11,1,2,,20251007143611,0A,03,01,-0300,1,20251007143612,34DA$",
    RAW_WITH_ONE_WIRE,
]


def test_gtinf_gv75lau_parsea_y_detecta_modelo_por_nombre_de_equipo():
    for line in RAW:
        shape = assert_gtinf_shape(line, "GV75LAU")
        data = parse_line(line)
        assert data["message"] == "GTINF"
        assert data["device"] == "GV75LAU"
        assert data["imei"] == shape["imei"]
        assert data["count_hex"] == shape["count_hex"]
        assert data.get("model") == "GV75LAU"


def test_gtinf_gv75lau_prefiere_nombre_cuando_el_prefijo_imei_es_ambiguo():
    raw = RAW[0].replace(",866314060583471,", ",866314061635635,", 1)
    data = parse_line(raw)
    assert data["message"] == "GTINF"
    assert data.get("model") == "GV75LAU"


def test_gtinf_gv75lau_incluye_mascara_y_datos_one_wire():
    data = parse_line(RAW_WITH_ONE_WIRE)

    assert data.get("inf_expand_mask") == "0001"
    assert data.get("one_wire_device_number") == 1

    devices = data.get("one_wire_devices")
    assert isinstance(devices, list)
    assert len(devices) == 1

    device = devices[0]
    assert device.get("one_wire_device_id") == "0011223344556677"
    assert device.get("one_wire_device_type") == 1
    assert device.get("one_wire_device_data") == "7F00"
