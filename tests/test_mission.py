from smartcar.fleet import DeliveryTask, IDLE, RETURNING_HOME, TO_DROPOFF, TO_PICKUP, VERIFY_RECIPIENT
from smartcar.mission import MissionManagerCore
from smartcar.navigation import GeoPoint


def task():
    return DeliveryTask('T1', 'alice', GeoPoint(3.1, 101.1), GeoPoint(3.2, 101.2))


def test_delivery_state_machine_and_recipient_verification():
    core = MissionManagerCore(home=GeoPoint(3.0, 101.0))
    assert core.assign(task()).state == TO_PICKUP
    assert core.goal_reached('pickup').state == TO_DROPOFF
    assert core.goal_reached('dropoff').state == VERIFY_RECIPIENT
    assert core.verify_recipient('mallory').state == VERIFY_RECIPIENT
    done = core.verify_recipient('alice')
    assert done.state == IDLE
    assert done.event == 'task_completed'


def test_low_battery_aborts_task_and_returns_home():
    home = GeoPoint(3.0, 101.0)
    core = MissionManagerCore(home=home)
    core.assign(task())
    transition = core.set_low_battery(True)
    assert transition.state == RETURNING_HOME
    assert transition.target == home
    assert transition.event == 'task_aborted_low_battery'
    assert transition.task_id == 'T1'


def test_vehicle_becomes_idle_after_recovery_at_home():
    home = GeoPoint(3.0, 101.0)
    core = MissionManagerCore(home=home)
    core.set_low_battery(True)
    assert core.goal_reached('home').state == 'AT_HOME'
    recovered = core.set_low_battery(False)
    assert recovered.state == IDLE
    assert recovered.event == 'battery_recovered'


def test_low_battery_before_first_gps_returns_once_home_is_captured():
    core = MissionManagerCore(home=None, capture_start_as_home=True)
    first = core.set_low_battery(True)
    assert first.event == 'return_home_unavailable'
    start = GeoPoint(3.0, 101.0)
    core.observe_position(start)
    second = core.set_low_battery(True)
    assert second.state == RETURNING_HOME
    assert second.target == start
