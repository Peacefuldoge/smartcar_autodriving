from smartcar.behavior import TimedCommand
from smartcar.hardware import DriveCommand
from smartcar.ros1_runtime import CommandMuxCore, TimedManeuverExecutor, steering_from_joy_axis


def test_timed_maneuver_executor_advances_without_blocking():
    executor = TimedManeuverExecutor()
    executor.start([
        TimedCommand(0.2, DriveCommand(1560, 1900)),
        TimedCommand(0.3, DriveCommand(1560, 1000)),
    ], now=10.0)

    assert executor.command(10.1) == DriveCommand(1560, 1900)
    assert executor.command(10.2) == DriveCommand(1560, 1000)
    assert executor.command(10.49) == DriveCommand(1560, 1000)
    assert executor.command(10.5) is None
    assert not executor.active


def test_command_mux_selects_mode_and_fails_safe_on_timeout():
    mux = CommandMuxCore(neutral=1500, timeout=0.3)
    auto = DriveCommand(1600, 1400)
    manual = DriveCommand(1550, 1700)
    mux.update("autonomous", auto, now=1.0)
    mux.update("manual", manual, now=1.0)

    assert mux.select(1.1) == auto
    mux.set_mode("manual")
    assert mux.select(1.1) == manual
    assert mux.select(1.31) == DriveCommand(1500, 1500)


def test_joystick_mapping_matches_historical_direction():
    assert steering_from_joy_axis(0.0) == 1500
    assert steering_from_joy_axis(1.0) == 750
    assert steering_from_joy_axis(-1.0) == 2250
