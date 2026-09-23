from smartcar.behavior import BehaviorController
from smartcar.object_detection import Detection


def det(label: int, score: float = 0.99) -> Detection:
    return Detection(label, score, 0, 0, 10, 10)


def test_speed_limit_can_be_enabled_and_cleared():
    controller = BehaviorController(
        confirmation_frames={"speed_limit": 1, "speed_limit_end": 1},
        cruise_speed=1600,
        limited_speed=1530,
    )
    assert controller.update(1500, [det(2)], now=0).command.throttle == 1530
    assert controller.update(1500, [], now=1).command.throttle == 1530
    assert controller.update(1500, [det(3)], now=2).command.throttle == 1600


def test_stop_line_is_one_shot():
    controller = BehaviorController(confirmation_frames={"stop_line": 1})
    first = controller.update(1500, [det(1)], now=0)
    second = controller.update(1500, [det(1)], now=1)
    assert first.maneuver
    assert second.maneuver == []


def test_overtake_has_explicit_timed_sequence():
    controller = BehaviorController(confirmation_frames={"overtake": 1})
    decision = controller.update(1500, [det(0)], now=0)
    assert len(decision.maneuver) == 8
