from viz.geo import bearing, bearing_to_cardinal


def test_bearing_cardinal():
    santiago = {"lat": -33.45, "lon": -70.66}
    valparaiso = {"lat": -33.047, "lon": -71.6127}
    angle = bearing(santiago, valparaiso)
    assert 290 <= angle <= 305  # Oeste-noroeste aproximado
    assert bearing_to_cardinal(angle) in {"ONO", "NO"}


def test_bearing_precision():
    assert bearing_to_cardinal(0, precision=4) == "N"
    assert bearing_to_cardinal(90, precision=4) == "E"
