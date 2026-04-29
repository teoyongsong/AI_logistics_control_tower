from backend.routes.scenario import _estimate_demand_index, _estimate_fleet_health_index


def test_estimate_demand_index_increases_with_stress():
    low = _estimate_demand_index(distance_km=8.0, traffic_level="low", weather="clear")["value"]
    high = _estimate_demand_index(distance_km=40.0, traffic_level="high", weather="storm")["value"]
    assert 0.6 <= low <= 1.8
    assert 0.6 <= high <= 1.8
    assert high > low


def test_estimate_fleet_health_decreases_with_stress():
    low_stress = _estimate_fleet_health_index(distance_km=8.0, traffic_level="low", weather="clear")["value"]
    high_stress = _estimate_fleet_health_index(distance_km=40.0, traffic_level="high", weather="storm")["value"]
    assert 0.5 <= low_stress <= 1.0
    assert 0.5 <= high_stress <= 1.0
    assert high_stress < low_stress

