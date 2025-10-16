import re
from queclink.parser import parse_line
from tests.common.assert_gtinf_shape import assert_gtinf_shape

RAW = [
    "+RESP:GTINF,74040A,862524060748775,GV350CEU,11,89999112400719062394,37,0,1,13074,,4.19,0,1,,,20251007213710,,0,0,0,00,00,+0000,0,20251007213751,6B91$",
    "+BUFF:GTINF,740904,862524060876527,GV350CEU,22,8935711001088072340f,38,0,1,28018,3,4.11,0,1,,,20251007143611,,0,0,0,11,00,+0000,0,20251007143612,34DA$",
]

def test_gtinf_gv350ceu_basico():
    for line in RAW:
        shape = assert_gtinf_shape(line, "GV350CEU")
        d = parse_line(line)
        assert d["message"] == "GTINF"
        assert d["device"]  == "GV350CEU"
        assert d["source"]  in {"RESP","BUFF"}
        assert d["protocol_version"] == shape["protocol_version"]
        assert d["imei"] == shape["imei"]
        assert d["count_hex"] == shape["count_hex"]
        assert "send_time_iso" in d and len(d["send_time_iso"]) >= 19
