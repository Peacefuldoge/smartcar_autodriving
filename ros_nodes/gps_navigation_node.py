#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import threading

import rospy
from sensor_msgs.msg import NavSatFix, NavSatStatus
from std_msgs.msg import Bool, Int32, String

from smartcar.navigation import GPSNavigatorCore, GeoPoint
from smartcar_autonomous_driving.msg import DriveCommand as DriveCommandMsg, NavigationGoal


class GPSNavigationNode:
    def __init__(self) -> None:
        vehicle = rospy.get_param('/smartcar/vehicle', {})
        cfg = rospy.get_param('/smartcar/navigation', {})
        self._lock = threading.Lock()
        self._neutral = int(vehicle.get('neutral', 1500))
        self._navigator = GPSNavigatorCore(
            neutral=self._neutral,
            speed=int(cfg.get('mission_speed', vehicle.get('slow_speed', 1560))),
            steering_min=int(vehicle.get('steering_min', 500)),
            steering_max=int(vehicle.get('steering_max', 2450)),
            arrival_radius_m=float(cfg.get('arrival_radius_m', 3.0)),
            bearing_gain=float(cfg.get('bearing_gain', 3.0)),
            steering_direction=float(cfg.get('steering_direction', 1.0)),
            heading_min_move_m=float(cfg.get('heading_min_move_m', 0.8)),
        )
        self._goal = None
        self._active = False
        self._position = None
        self._last_fix = 0.0
        self._lane_steering = self._neutral
        self._fix_timeout = float(cfg.get('fix_timeout', 2.0))
        self._arrived_sent = False
        self._cmd_pub = rospy.Publisher('cmd_drive/mission', DriveCommandMsg, queue_size=1)
        self._arrival_pub = rospy.Publisher('navigation/goal_reached', String, queue_size=10)
        rospy.Subscriber('mission/navigation_goal', NavigationGoal, self._on_goal, queue_size=1)
        rospy.Subscriber('mission/active', Bool, self._on_active, queue_size=1)
        rospy.Subscriber('gps/fix', NavSatFix, self._on_fix, queue_size=1)
        rospy.Subscriber('lane/steering', Int32, self._on_steering, queue_size=1)
        rate = max(2.0, float(cfg.get('control_rate', 10.0)))
        self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._on_timer)

    def _on_goal(self, msg: NavigationGoal) -> None:
        with self._lock:
            self._goal = msg
            self._navigator.reset()
            self._arrived_sent = False

    def _on_active(self, msg: Bool) -> None:
        with self._lock:
            self._active = bool(msg.data)

    def _on_fix(self, msg: NavSatFix) -> None:
        if msg.status.status == NavSatStatus.STATUS_NO_FIX:
            return
        with self._lock:
            self._position = GeoPoint(msg.latitude, msg.longitude, msg.altitude)
            self._last_fix = time.monotonic()

    def _on_steering(self, msg: Int32) -> None:
        with self._lock:
            self._lane_steering = int(msg.data)

    def _publish(self, throttle: int, steering: int) -> None:
        out = DriveCommandMsg()
        out.header.stamp = rospy.Time.now()
        out.throttle = int(throttle)
        out.steering = int(steering)
        self._cmd_pub.publish(out)

    def _on_timer(self, _event) -> None:
        arrival = None
        with self._lock:
            if not self._active:
                return
            if self._goal is None or self._position is None or time.monotonic() - self._last_fix > self._fix_timeout:
                command = (self._neutral, self._neutral)
            else:
                target = GeoPoint(self._goal.target.latitude, self._goal.target.longitude, self._goal.target.altitude)
                result = self._navigator.compute(self._position, target, self._lane_steering)
                command = (result.command.throttle, result.command.steering)
                if result.arrived and not self._arrived_sent:
                    arrival = {'task_id': self._goal.task_id, 'goal_type': self._goal.goal_type}
                    self._arrived_sent = True
        self._publish(*command)
        if arrival is not None:
            self._arrival_pub.publish(String(data=json.dumps(arrival, separators=(',', ':'))))


def main() -> None:
    rospy.init_node('gps_navigation_node')
    GPSNavigationNode()
    rospy.spin()


if __name__ == '__main__':
    main()
