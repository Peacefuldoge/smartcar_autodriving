from smartcar.navigation import GeoPoint, GPSNavigatorCore, angle_error_deg, bearing_deg, haversine_m


def test_distance_and_bearing_are_sensible():
    a = GeoPoint(0.0, 0.0)
    east = GeoPoint(0.0, 0.001)
    assert 110.0 < haversine_m(a, east) < 112.5
    assert 89.0 < bearing_deg(a, east) < 91.0
    assert angle_error_deg(10.0, 350.0) == 20.0


def test_navigator_stops_inside_arrival_radius():
    nav = GPSNavigatorCore(arrival_radius_m=3.0)
    result = nav.compute(GeoPoint(3.0, 101.0), GeoPoint(3.0, 101.000001), 1500)
    assert result.arrived
    assert result.command.throttle == 1500
