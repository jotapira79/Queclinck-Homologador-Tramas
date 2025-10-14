"""Tests for repeated group parsing edge cases."""

from queclink.parser import FieldSpec, Spec, parse_line


def test_optional_group_skipped_when_repeat_count_is_zero():
    spec = Spec(
        model="DUMMY",
        message="GTFAKE",
        table_name="fake",
        delimiter=",",
        terminator="$",
        fields=(
            FieldSpec(name="count", type="int"),
            FieldSpec(
                name="devices",
                type="group_repeated",
                optional=True,
                repeat="count",
                fields=(FieldSpec(name="device_id", type="int"),),
            ),
            FieldSpec(name="after", type="int"),
        ),
    )

    parsed = parse_line("0,42$", message="GTFAKE", model="DUMMY", spec=spec)

    assert parsed == {"count": 0, "after": 42}
    assert "devices" not in parsed
