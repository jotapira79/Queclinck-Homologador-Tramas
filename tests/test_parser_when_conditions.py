"""Tests for spec-driven conditional parsing helpers."""

from __future__ import annotations

from queclink.parser import Condition, load_spec


def _field_map(spec):
    return {field.name: field for field in spec.fields}


def test_gv310_digital_fuel_uses_eri_mask_condition():
    spec = load_spec("GV310LAU", "GTERI")
    fields = _field_map(spec)
    digital_fuel = fields.get("digital_fuel_sensor_data")
    assert digital_fuel is not None
    conds = list(digital_fuel.enabled_if_any)
    assert conds, "digital_fuel_sensor_data should be gated by eri_mask"
    cond = conds[0]
    assert isinstance(cond, Condition)
    assert cond.mask_field == "eri_mask"
    assert cond.bit == 0


def test_gv310_band_depends_on_rat_presence():
    spec = load_spec("GV310LAU", "GTERI")
    fields = _field_map(spec)
    assert "rat" in fields
    band_field = fields.get("band")
    assert band_field is not None
    conds = list(band_field.enabled_if_any)
    assert conds, "band must depend on rat presence"
    assert conds[0].field_present == "rat"


def test_when_anyof_generates_multiple_conditions():
    spec = load_spec("GV310LAU", "GTERI")
    fields = _field_map(spec)
    fuel_block = fields.get("fuel_sensor_block")
    assert fuel_block is not None
    nested = {child.name: child for child in fuel_block.fields}
    temp_field = nested.get("fuel_temperature_c")
    assert temp_field is not None
    any_conditions = list(temp_field.present_if_any)
    assert len(any_conditions) == 2
    equals_values = {cond.equals for cond in any_conditions}
    assert equals_values == {2, 6}


def test_gv58_includes_rat_and_band():
    spec = load_spec("GV58LAU", "GTERI")
    fields = _field_map(spec)
    rat_field = fields.get("rat")
    band_field = fields.get("band")
    assert rat_field is not None
    assert band_field is not None
    rat_cond = list(rat_field.enabled_if_any)
    assert rat_cond and rat_cond[0].mask_field == "eri_mask"
    band_cond = list(band_field.enabled_if_any)
    assert band_cond and band_cond[0].field_present == "rat"
