import re
from queclink.parser import parse_line
from tests.common.assert_gtinf_shape import assert_gtinf_shape

RAW = [
    "+RESP:GTINF,8020040900,866314061635635,GV58LAU,11,89999202003110001341,58,0,1,12943,3,4.15,0,1,,,20251007213819,0,,,,00,00,+0000,0,20251007215523,48D6$",
    "+BUFF:GTINF,8020040305,866314060965330,GV58LAU,22,89999112400719088191,26,0,1,13742,0,4.22,0,1,,,20250930110413,0,,,,01,00,+0000,0,20250930110413,ED27$",
]

def test_gtinf_gv58lau_basico():
    for line in RAW:
        shape = assert_gtinf_shape(line, "GV58LAU")
        d = parse_line(line)
        assert d["message"] == "GTINF"
        assert d["device"]  == "GV58LAU"
        assert d["source"]  in {"RESP","BUFF"}
        assert d["protocol_version"] == shape["protocol_version"]
        assert d["imei"] == shape["imei"]
        assert d["count_hex"] == shape["count_hex"]
        assert "send_time_iso" in d and len(d["send_time_iso"]) >= 19


def test_gtinf_detecta_modelo_por_prefijo_imei():
    raw = RAW[0].replace(",GV58LAU,", ",UnidadCamion,", 1)
    d = parse_line(raw)
    assert d["message"] == "GTINF"
    assert d["device"] == "GV58LAU"
    assert d.get("model") == "GV58LAU"
    assert d.get("device_name") == "UnidadCamion"
