#!/usr/bin/env python3
from __future__ import annotations

import time
import threading

import rospy
from std_msgs.msg import Int32, String

from smartcar.behavior import BehaviorController
from smartcar.object_detection import Detection
from smartcar.ros1_runtime import TimedManeuverExecutor
from smartcar_autonomous_driving.msg import DetectionArray, DriveCommand as DriveCommandMsg


class BehaviorNode:
    def __init__(self) -> None:
        vehicle = rospy.get_param("/smartcar/vehicle", {})
        behavior = rospy.get_param("/smartcar/behavior", {})
        self._neutral = int(vehicle.get("neutral", 1500))
        self._lock = threading.Lock()
        self._steering = self._neutral
        self._controller = BehaviorController(
            cruise_speed=int(vehicle.get("cruise_speed", 1600)),
            limited_speed=int(vehicle.get("limited_speed", 1530)),
            slow_speed=int(vehicle.get("slow_speed", 1560)),
            turn_speed=int(vehicle.get("turn_speed", 1538)),
            neutral=self._neutral,
            left_bias=int(behavior.get("left_bias", 12)),
            left_bias_seconds=float(behavior.get("left_bias_seconds", 2.0)),
            cooldown_seconds=float(behavior.get("cooldown_seconds", 5.0)),
            confirmation_frames=behavior.get("confirmation_frames", {}),
        )
        self._maneuver = TimedManeuverExecutor()
        self._command_pub = rospy.Publisher("cmd_drive/autonomous", DriveCommandMsg, queue_size=1)
        self._event_pub = rospy.Publisher("behavior/event", String, queue_size=10)
        rospy.Subscriber("lane/steering", Int32, self._on_steering, queue_size=1)
        rospy.Subscriber("detector/detections", DetectionArray, self._on_detections, queue_size=1)
        rate = float(rospy.get_param("~publish_rate", 30.0))
        self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._on_timer)

    def _on_steering(self, msg: Int32) -> None:
        with self._lock:
            self._steering = int(msg.data)

    def _on_detections(self, msg: DetectionArray) -> None:
        detections = [
            Detection(d.label_id, d.score, d.xmin, d.ymin, d.xmax, d.ymax)
            for d in msg.detections
        ]
        now = time.monotonic()
        with self._lock:
            # A maneuver has priority; ignoring new detections during it prevents repeated triggers.
            if self._maneuver.active:
                return
            decision = self._controller.update(self._steering, detections, now=now)
            if decision.maneuver:
                self._maneuver.start(decision.maneuver, now)
            events = tuple(decision.events)
        for event in events:
            self._event_pub.publish(String(data=event))
            rospy.loginfo("behavior_node: event=%s", event)

    def _publish(self, throttle: int, steering: int) -> None:
        msg = DriveCommandMsg()
        msg.header.stamp = rospy.Time.now()
        msg.throttle = int(throttle)
        msg.steering = int(steering)
        self._command_pub.publish(msg)

    def _on_timer(self, _event) -> None:
        now = time.monotonic()
        with self._lock:
            command = self._maneuver.command(now)
            if command is None:
                command = self._controller.base_command(self._steering, now=now)
        self._publish(command.throttle, command.steering)


def main() -> None:
    rospy.init_node("behavior_node")
    BehaviorNode()
    rospy.spin()


if __name__ == "__main__":
    main()
