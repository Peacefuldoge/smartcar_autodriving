#!/usr/bin/env python3
from __future__ import annotations

import json
import threading

import rospy
from sensor_msgs.msg import BatteryState, NavSatFix, NavSatStatus
from std_msgs.msg import Bool, String

from smartcar.fleet import DeliveryTask as CoreTask
from smartcar.mission import MissionManagerCore, MissionTransition
from smartcar.navigation import GeoPoint
from smartcar_autonomous_driving.msg import DeliveryTask, FaceRecognition, NavigationGoal, VehicleStatus


class MissionManagerNode:
    def __init__(self) -> None:
        cfg = rospy.get_param('/smartcar/mission', {})
        home = None
        if cfg.get('home_latitude') is not None and cfg.get('home_longitude') is not None:
            home = GeoPoint(float(cfg['home_latitude']), float(cfg['home_longitude']), float(cfg.get('home_altitude', 0.0)))
        self._vehicle_id = str(rospy.get_param('~vehicle_id', cfg.get('vehicle_id', 'car_1')))
        self._core = MissionManagerCore(home=home, capture_start_as_home=bool(cfg.get('capture_start_as_home', True)))
        self._lock = threading.Lock()
        self._position = GeoPoint(0.0, 0.0, 0.0)
        self._battery_voltage = 0.0
        self._battery_pct = 0.0
        self._battery_low = False

        self._goal_pub = rospy.Publisher('mission/navigation_goal', NavigationGoal, queue_size=1, latch=True)
        self._active_pub = rospy.Publisher('mission/active', Bool, queue_size=1, latch=True)
        self._state_pub = rospy.Publisher('mission/state', String, queue_size=1, latch=True)
        self._expected_pub = rospy.Publisher('delivery/expected_recipient', String, queue_size=1, latch=True)
        self._recognition_pub = rospy.Publisher('delivery/recognition_enabled', Bool, queue_size=1, latch=True)
        self._status_pub = rospy.Publisher('fleet/status', VehicleStatus, queue_size=10)
        self._event_pub = rospy.Publisher('fleet/event', String, queue_size=10)
        rospy.Subscriber('fleet/task', DeliveryTask, self._on_task, queue_size=10)
        rospy.Subscriber('gps/fix', NavSatFix, self._on_fix, queue_size=5)
        rospy.Subscriber('battery/state', BatteryState, self._on_battery, queue_size=5)
        rospy.Subscriber('battery/low', Bool, self._on_low_battery, queue_size=1)
        rospy.Subscriber('navigation/goal_reached', String, self._on_goal_reached, queue_size=5)
        rospy.Subscriber('face/recognition', FaceRecognition, self._on_face, queue_size=5)
        self._timer = rospy.Timer(rospy.Duration(0.5), self._publish_status)
        self._apply(MissionTransition(self._core.state))

    def _to_core_task(self, msg: DeliveryTask) -> CoreTask:
        return CoreTask(
            task_id=msg.task_id,
            recipient_id=msg.recipient_id,
            priority=int(msg.priority),
            pickup=GeoPoint(msg.pickup.latitude, msg.pickup.longitude, msg.pickup.altitude),
            dropoff=GeoPoint(msg.dropoff.latitude, msg.dropoff.longitude, msg.dropoff.altitude),
            created_at=rospy.Time.now().to_sec(),
        )

    def _on_task(self, msg: DeliveryTask) -> None:
        with self._lock:
            transition = self._core.assign(self._to_core_task(msg))
        self._apply(transition)

    def _on_fix(self, msg: NavSatFix) -> None:
        if msg.status.status == NavSatStatus.STATUS_NO_FIX:
            return
        pos = GeoPoint(msg.latitude, msg.longitude, msg.altitude)
        transition = None
        with self._lock:
            self._position = pos
            had_home = self._core.home is not None
            self._core.observe_position(pos)
            if self._battery_low and not had_home and self._core.home is not None:
                transition = self._core.set_low_battery(True)
        if transition is not None:
            self._apply(transition)

    def _on_battery(self, msg: BatteryState) -> None:
        with self._lock:
            self._battery_voltage = float(msg.voltage)
            self._battery_pct = float(msg.percentage)

    def _on_low_battery(self, msg: Bool) -> None:
        low = bool(msg.data)
        with self._lock:
            if low == self._battery_low:
                return
            self._battery_low = low
            transition = self._core.set_low_battery(low)
        self._apply(transition)

    def _on_goal_reached(self, msg: String) -> None:
        try:
            event = json.loads(msg.data)
            goal_type = str(event['goal_type'])
        except Exception:
            rospy.logwarn('mission_manager_node: invalid navigation arrival payload')
            return
        with self._lock:
            transition = self._core.goal_reached(goal_type)
        self._apply(transition)

    def _on_face(self, msg: FaceRecognition) -> None:
        if not msg.verified:
            return
        with self._lock:
            transition = self._core.verify_recipient(msg.person_id)
        self._apply(transition)

    def _apply(self, transition: MissionTransition) -> None:
        self._state_pub.publish(String(data=transition.state))
        target = transition.target if transition.target is not None else self._core.current_target
        is_nav = target is not None
        self._active_pub.publish(Bool(data=is_nav))
        if target is not None:
            goal = NavigationGoal()
            goal.header.stamp = rospy.Time.now()
            goal.task_id = transition.task_id or (self._core.task.task_id if self._core.task else '')
            goal.goal_type = transition.goal_type
            goal.target.latitude = target.latitude
            goal.target.longitude = target.longitude
            goal.target.altitude = target.altitude
            self._goal_pub.publish(goal)

        expected = self._core.task.recipient_id if self._core.task else ''
        recognition_enabled = transition.state == 'VERIFY_RECIPIENT'
        self._expected_pub.publish(String(data=expected))
        self._recognition_pub.publish(Bool(data=recognition_enabled))
        if transition.event:
            payload = {'event': transition.event, 'task_id': transition.task_id, 'state': transition.state}
            self._event_pub.publish(String(data=json.dumps(payload, separators=(',', ':'))))
            rospy.loginfo('mission_manager_node: %s', payload)

    def _publish_status(self, _event) -> None:
        with self._lock:
            msg = VehicleStatus()
            msg.header.stamp = rospy.Time.now()
            msg.vehicle_id = self._vehicle_id
            msg.state = self._core.state
            msg.task_id = self._core.task.task_id if self._core.task else ''
            msg.latitude = self._position.latitude
            msg.longitude = self._position.longitude
            msg.battery_voltage = self._battery_voltage
            msg.battery_percentage = self._battery_pct
            msg.battery_low = self._battery_low
        self._status_pub.publish(msg)


def main() -> None:
    rospy.init_node('mission_manager_node')
    MissionManagerNode()
    rospy.spin()


if __name__ == '__main__':
    main()
