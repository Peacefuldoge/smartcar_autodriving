from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .fleet import AT_HOME, IDLE, RETURNING_HOME, TO_DROPOFF, TO_PICKUP, VERIFY_RECIPIENT, DeliveryTask
from .navigation import GeoPoint


@dataclass(frozen=True)
class MissionTransition:
    state: str
    target: Optional[GeoPoint] = None
    goal_type: str = ""
    event: str = ""
    task_id: str = ""


class MissionManagerCore:
    def __init__(self, *, home: Optional[GeoPoint] = None, capture_start_as_home: bool = True) -> None:
        self.home = home
        self.capture_start_as_home = bool(capture_start_as_home)
        self.state = IDLE
        self.task: Optional[DeliveryTask] = None
        self.current_target: Optional[GeoPoint] = None
        self.goal_type = ""
        self.battery_low = False

    def observe_position(self, position: GeoPoint) -> None:
        if self.home is None and self.capture_start_as_home:
            self.home = position

    def assign(self, task: DeliveryTask) -> MissionTransition:
        if self.battery_low:
            return MissionTransition(self.state, event="task_rejected_low_battery", task_id=task.task_id)
        if self.state not in {IDLE, AT_HOME}:
            return MissionTransition(self.state, event="task_rejected_busy", task_id=task.task_id)
        self.task = task
        self.state = TO_PICKUP
        self.current_target = task.pickup
        self.goal_type = "pickup"
        return MissionTransition(self.state, task.pickup, "pickup", "task_accepted", task.task_id)

    def set_low_battery(self, low: bool) -> MissionTransition:
        self.battery_low = bool(low)
        if not low:
            if self.state == AT_HOME:
                self.state = IDLE
                return MissionTransition(self.state, event="battery_recovered")
            return MissionTransition(self.state)
        if self.home is None:
            return MissionTransition(self.state, event="return_home_unavailable")
        aborted = self.task.task_id if self.task else ""
        self.task = None
        self.state = RETURNING_HOME
        self.current_target = self.home
        self.goal_type = "home"
        return MissionTransition(self.state, self.home, "home", "task_aborted_low_battery" if aborted else "return_home", aborted)

    def goal_reached(self, goal_type: str) -> MissionTransition:
        if goal_type != self.goal_type:
            return MissionTransition(self.state)
        if self.state == TO_PICKUP and self.task:
            self.state = TO_DROPOFF
            self.current_target = self.task.dropoff
            self.goal_type = "dropoff"
            return MissionTransition(self.state, self.current_target, "dropoff", "pickup_reached", self.task.task_id)
        if self.state == TO_DROPOFF and self.task:
            self.state = VERIFY_RECIPIENT
            self.current_target = None
            self.goal_type = ""
            return MissionTransition(self.state, event="dropoff_reached", task_id=self.task.task_id)
        if self.state == RETURNING_HOME:
            self.state = AT_HOME
            self.current_target = None
            self.goal_type = ""
            return MissionTransition(self.state, event="home_reached")
        return MissionTransition(self.state)

    def verify_recipient(self, person_id: str) -> MissionTransition:
        if self.state != VERIFY_RECIPIENT or not self.task:
            return MissionTransition(self.state)
        if person_id != self.task.recipient_id:
            return MissionTransition(self.state, event="recipient_mismatch", task_id=self.task.task_id)
        task_id = self.task.task_id
        self.task = None
        self.state = IDLE
        return MissionTransition(self.state, event="task_completed", task_id=task_id)
