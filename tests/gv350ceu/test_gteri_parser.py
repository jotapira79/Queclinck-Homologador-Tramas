from queclink.parser import parse_gteri

RAW_GV350_GTERI = (
    "+RESP:GTERI,740904,862524060204589,GV350CEU,00000100,,10,1,1,0.0,355,97.7,117.129252,31.839388,20240415054037,0460,0000,"
    "550B,085BE2AA,01,11,3.6,,,,,0,210100,0,1,00,11,0,0000001E,100F,,D325C2B2A2F8,1,2967,0,15,0,20240415154438,405C$"
)


def test_gteri_gv350_ble_and_rat_band():
    data = parse_gteri(RAW_GV350_GTERI)

    assert data.get("device") == "GV350CEU"
    assert data.get("ble_count") == 1

    block = data.get("ble_block") or {}
    assert block.get("accessory_number") == 1
    items = block.get("items") or []
    assert len(items) == 1
    first = items[0]
    assert first.get("accessory_type") == 11
    assert first.get("append_mask") == "100F"

    rat_band = data.get("rat_band") or {}
    assert rat_band.get("rat") == 15
    assert rat_band.get("band") in ("0", None)

    assert data.get("spec_path") == "spec/gv350ceu/gteri.yml"
