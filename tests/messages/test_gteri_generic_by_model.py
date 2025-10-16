import pytest

from queclink.messages.gteri import parse_gteri

MODEL_IMEI = {
    "gv350ceu": "86252406",  # CEU
    "gv58lau": "86631406",  # 58LAU
    "gv310lau": "86858906",  # 310LAU
}


def make_line(model: str, eri_mask: str, pos_mask: str) -> str:
    imei = MODEL_IMEI[model] + "012345"
    return (
        f"+RESP:GTERI,740904,{imei},{model.upper()},"
        f"{eri_mask},13574,10,1,1,0.0,295,484.3,-70.297988,-23.739877,"
        f"20251009132737,0730,0001,0836,002BEE06,{pos_mask},8,799972.0,"
        f"0000329:43:11,,,,100,111000,0,0,20251009133001,2B8B$"
    )


@pytest.mark.parametrize("model", ["gv350ceu", "gv58lau", "gv310lau"])
@pytest.mark.parametrize(
    "eri_mask,pos_mask,expects",
    [
        ("00000000", "00", {"onewire": False, "ble": False, "rat": False}),
        ("00000002", "01", {"onewire": True, "ble": False, "rat": False}),
        ("00001000", "13", {"onewire": False, "ble": True, "rat": False}),
        ("00002000", "00", {"onewire": False, "ble": False, "rat": True}),
    ],
)
def test_gteri_masks_by_model(model, eri_mask, pos_mask, expects):
    line = make_line(model, eri_mask, pos_mask)
    parsed = parse_gteri(line, device=model.upper())
    assert all(k in parsed for k in ("imei", "lon", "lat", "send_time"))
    assert ("onewire_device_count" in parsed) == expects["onewire"]
    assert any(key.startswith("ble_") for key in parsed) == expects["ble"]
    present_rat = ("rat" in parsed) or ("band" in parsed)
    assert present_rat == expects["rat"]
