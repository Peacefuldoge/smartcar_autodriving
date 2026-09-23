from smartcar.fleet import DeliveryTask, FleetCoordinatorCore, VehicleSnapshot, IDLE, TO_DROPOFF
from smartcar.navigation import GeoPoint


def vehicle(vehicle_id, lat, lon, *, state=IDLE, battery=0.8, low=False, now=100.0):
    return VehicleSnapshot(vehicle_id=vehicle_id, state=state, position=GeoPoint(lat, lon),
                           battery_percentage=battery, battery_low=low, last_seen=now,
                           endpoint=('127.0.0.1', 52000))


def test_three_car_scheduler_prefers_nearest_idle_vehicle():
    core = FleetCoordinatorCore(['car_1', 'car_2', 'car_3'], min_dispatch_battery=0.25)
    core.update_vehicle(vehicle('car_1', 3.0000, 101.0000))
    core.update_vehicle(vehicle('car_2', 3.0010, 101.0010, state=TO_DROPOFF))
    core.update_vehicle(vehicle('car_3', 3.0001, 101.0001))
    task = DeliveryTask('T1', 'alice', GeoPoint(3.0002, 101.0002), GeoPoint(3.01, 101.01), created_at=1.0)
    core.submit(task)
    assignments = core.assign_pending(100.1)
    assert len(assignments) == 1
    assert assignments[0][0].vehicle_id == 'car_3'


def test_low_battery_idle_vehicle_is_not_dispatched():
    core = FleetCoordinatorCore(['car_1', 'car_2', 'car_3'], min_dispatch_battery=0.25)
    core.update_vehicle(vehicle('car_1', 3.0, 101.0, battery=0.15, low=True))
    core.update_vehicle(vehicle('car_2', 3.1, 101.1, battery=0.8))
    core.update_vehicle(vehicle('car_3', 3.2, 101.2, state=TO_DROPOFF))
    core.submit(DeliveryTask('T2', 'bob', GeoPoint(3.0, 101.0), GeoPoint(3.3, 101.3), created_at=1.0))
    assignments = core.assign_pending(100.1)
    assert assignments[0][0].vehicle_id == 'car_2'
