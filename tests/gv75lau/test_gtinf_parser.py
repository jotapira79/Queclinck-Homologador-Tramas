from queclink import parse_line
from tests.common.assert_gtinf_shape import assert_gtinf_shape


RAW = [
    "+RESP:GTINF,80200C0100,866314060583471,GV75LAU,11,8956012345678901234,27,0,1,13250,4,4.08,0,,,20251029091530,0F,01,00,+0000,0,20251029091533,6B91$",
    "+BUFF:GTINF,80200C0100,866314060583471,GV75LAU,12,8935711001088072340f,38,7,1,27890,,4.11,1,2,,20251007143611,0A,03,01,-0300,1,20251007143612,34DA$",
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
