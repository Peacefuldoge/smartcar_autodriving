import math

from smartcar.gps import parse_nmea


def test_parse_gga_known_sentence():
    fix = parse_nmea('$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47')
    assert fix is not None
    assert math.isclose(fix.latitude, 48.1173, abs_tol=1e-5)
    assert math.isclose(fix.longitude, 11.5166667, abs_tol=1e-5)
    assert fix.satellites == 8
    assert math.isclose(fix.altitude, 545.4)


def test_bad_checksum_is_rejected():
    assert parse_nmea('$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*00') is None
