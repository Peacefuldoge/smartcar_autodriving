from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .navigation import GeoPoint, haversine_m


IDLE = "IDLE"
ASSIGNED = "ASSIGNED"
TO_PICKUP = "TO_PICKUP"
TO_DROPOFF = "TO_DROPOFF"
VERIFY_RECIPIENT = "VERIFY_RECIPIENT"
RETURNING_HOME = "RETURNING_HOME"
AT_HOME = "AT_HOME"
OFFLINE = "OFFLINE"


@dataclass
class VehicleSnapshot:
    vehicle_id: str
    state: str = OFFLINE
    position: Optional[GeoPoint] = None
    battery_percentage: float = 0.0
    battery_low: bool = False
    task_id: str = ""
    last_seen: float = 0.0
    endpoint: Optional[Tuple[str, int]] = None


@dataclass
class DeliveryTask:
    task_id: str
    recipient_id: str
    pickup: GeoPoint
    dropoff: GeoPoint
    priority: int = 0
    created_at: float = 0.0
    assigned_vehicle: str = ""


class FleetCoordinatorCore:
    """Host-side task scheduler for a fixed fleet.

    Only healthy IDLE vehicles are eligible. Among them, the nearest vehicle to the
    pickup location is selected; task priority and FIFO order control which queued task
    is considered first.
    """

    def __init__(self, vehicle_ids, *, heartbeat_timeout: float = 3.0,
                 min_dispatch_battery: float = 0.25) -> None:
        ids = tuple(str(v) for v in vehicle_ids)
        if not ids:
            raise ValueError("at least one vehicle is required")
        self.vehicles: Dict[str, VehicleSnapshot] = {v: VehicleSnapshot(v) for v in ids}
        self.heartbeat_timeout = float(heartbeat_timeout)
        self.min_dispatch_battery = float(min_dispatch_battery)
        self.pending: List[DeliveryTask] = []
        self.active: Dict[str, DeliveryTask] = {}

    def update_vehicle(self, snapshot: VehicleSnapshot) -> None:
        if snapshot.vehicle_id not in self.vehicles:
            return
        active_for_vehicle = next(
            (task for task in self.active.values() if task.assigned_vehicle == snapshot.vehicle_id),
            None,
        )
        # A stale pre-assignment heartbeat may still say IDLE before the UDP task
        # arrives. Keep the vehicle reserved until it ACKs/transitions or the host
        # explicitly aborts/requeues the active task.
        if active_for_vehicle is not None and snapshot.state == IDLE:
            snapshot.state = ASSIGNED
            snapshot.task_id = active_for_vehicle.task_id
        self.vehicles[snapshot.vehicle_id] = snapshot

    def submit(self, task: DeliveryTask) -> None:
        if task.task_id in self.active or any(t.task_id == task.task_id for t in self.pending):
            raise ValueError(f"duplicate task_id: {task.task_id}")
        self.pending.append(task)
        self.pending.sort(key=lambda t: (-int(t.priority), float(t.created_at), t.task_id))

    def mark_offline(self, now: float) -> List[str]:
        offline = []
        for vehicle in self.vehicles.values():
            if vehicle.last_seen and now - vehicle.last_seen > self.heartbeat_timeout and vehicle.state != OFFLINE:
                vehicle.state = OFFLINE
                offline.append(vehicle.vehicle_id)
        return offline

    def _eligible(self, now: float) -> List[VehicleSnapshot]:
        result = []
        for vehicle in self.vehicles.values():
            fresh = bool(vehicle.last_seen) and now - vehicle.last_seen <= self.heartbeat_timeout
            if (fresh and vehicle.state == IDLE and not vehicle.task_id and not vehicle.battery_low
                    and vehicle.battery_percentage >= self.min_dispatch_battery):
                result.append(vehicle)
        return result

    def assign_pending(self, now: float) -> List[Tuple[VehicleSnapshot, DeliveryTask]]:
        assignments: List[Tuple[VehicleSnapshot, DeliveryTask]] = []
        while self.pending:
            eligible = self._eligible(now)
            if not eligible:
                break
            task = self.pending[0]

            def cost(vehicle: VehicleSnapshot):
                distance = haversine_m(vehicle.position, task.pickup) if vehicle.position else float("inf")
                return (distance, vehicle.vehicle_id)

            vehicle = min(eligible, key=cost)
            self.pending.pop(0)
            task.assigned_vehicle = vehicle.vehicle_id
            self.active[task.task_id] = task
            vehicle.state = ASSIGNED
            vehicle.task_id = task.task_id
            assignments.append((vehicle, task))
        return assignments

    def complete(self, task_id: str) -> Optional[DeliveryTask]:
        return self.active.pop(task_id, None)

    def abort(self, task_id: str, *, requeue: bool = True) -> Optional[DeliveryTask]:
        task = self.active.pop(task_id, None)
        if task and requeue:
            task.assigned_vehicle = ""
            self.pending.append(task)
            self.pending.sort(key=lambda t: (-int(t.priority), float(t.created_at), t.task_id))
        return task
