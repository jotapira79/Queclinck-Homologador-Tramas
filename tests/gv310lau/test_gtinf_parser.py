import re
from queclink.parser import parse_line
from tests.common.assert_gtinf_shape import assert_gtinf_shape

RAW = [
    "+RESP:GTINF,6E0C03,868589060361840,GV310LAU,11,89999112400719079703,32,0,0,0,3,3.81,0,1,2,0,20251007214015,3,,0,,00,00,+0000,0,20251007215025,BD2C$",
    "+BUFF:GTINF,6E0C03,868589060716712,GV310LAU,21,89999112400719021127,15,0,1,27999,2,4.16,0,1,2,0,20251007194843,3,,0,,01,00,+0000,0,20251007194845,32B0$",
]

def test_gtinf_gv310lau_basico():
    for line in RAW:
        shape = assert_gtinf_shape(line, "GV310LAU")
        d = parse_line(line)
        assert d["message"] == "GTINF"
        assert d["device"]  == "GV310LAU"
        assert d["source"]  in {"RESP","BUFF"}
        assert d["protocol_version"] == shape["protocol_version"]
        assert d["imei"] == shape["imei"]
        assert d["count_hex"] == shape["count_hex"]
        assert "send_time_iso" in d and len(d["send_time_iso"]) >= 19
