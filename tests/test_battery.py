from smartcar.battery import BatteryMonitorCore, parse_voltage_line


def test_voltage_parser_accepts_lower_controller_formats():
    assert parse_voltage_line('VOLTAGE:12.34') == 12.34
    assert parse_voltage_line('VBAT=11.8') == 11.8
    assert parse_voltage_line('V=10.75') == 10.75
    assert parse_voltage_line('12.10V') == 12.10
    assert parse_voltage_line('garbage') is None


def test_low_battery_hysteresis():
    monitor = BatteryMonitorCore(low_voltage=10.8, recovery_voltage=11.2,
                                 empty_voltage=10.0, full_voltage=12.6)
    assert not monitor.update(11.5).low
    assert monitor.update(10.7).low
    assert monitor.update(11.0).low
    assert not monitor.update(11.3).low
