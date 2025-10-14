import pytest

from queclink.parser import FieldSpec, load_spec


def _field_map(spec) -> dict[str, FieldSpec]:
    return {field.name: field for field in spec.fields}


@pytest.mark.parametrize("model", ["GV310LAU", "GV350CEU"])
def test_one_wire_group_configured_as_optional_repeated(model):
    spec = load_spec(model, "GTERI")
    fields = _field_map(spec)

    assert "one_wire_device_number" in fields, "count field missing for model"
    assert "one_wire_devices" in fields, "group field missing for model"

    count_field = fields["one_wire_device_number"]
    group_field = fields["one_wire_devices"]

    assert count_field.optional, "count should be optional when mask disabled"
    assert group_field.optional, "group should be optional to tolerate zero count"
    assert group_field.type == "group_repeated"
    assert group_field.repeat == "one_wire_device_number"

    nested_names = {nested.name: nested for nested in group_field.fields}
    assert "one_wire_device_id" in nested_names
    assert nested_names["one_wire_device_id"].type == "hex"

    assert "one_wire_device_type" in nested_names
    assert nested_names["one_wire_device_type"].optional

    assert "one_wire_device_data" in nested_names
    assert nested_names["one_wire_device_data"].optional
