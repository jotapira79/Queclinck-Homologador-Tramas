from queclink.parser import parse_gteri

RAW_GV58_GTERI = (
    "+RESP:GTERI,8020040900,866314060268081,GV58LAU,00000100,,10,1,2,14.2,71,35.6,117.243103,31.854079,20250320015848,0460,0000," 
    "550B,0E9E30A5,0009,9,2.01,1.47,2.49,0.0,1234:56:07,,85,220100,,2,00,1,0,00000001,001F,TD_100109,FD6D3DE6D704,1,3600,18,01,1," 
    "3,0000006D,011F,DU_100361,F022A2143F36,1,3500,0,9,0,20250320015850,00D0$"
)


def test_gteri_gv58_ble_and_reserved_fields():
    data = parse_gteri(RAW_GV58_GTERI)

    assert data.get("device") == "GV58LAU"
    assert data.get("ble_count") == 2

    block = data.get("ble_block") or {}
    items = block.get("items") or []
    assert len(items) == 2
    assert items[0].get("name") == "TD_100109"
    assert items[1].get("name") == "DU_100361"

    assert data.get("reserved_1") == "220100"
    assert data.get("reserved_2") is None
    assert data.get("reserved_3") is None

    rat_band = data.get("rat_band") or {}
    assert rat_band.get("rat") == 0
    assert rat_band.get("band") in (None, "0")

    assert data.get("spec_path") == "spec/gv58lau/gteri.yml"
