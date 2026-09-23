#!/usr/bin/env python3
from __future__ import annotations

import time
import threading

import rospy
from std_msgs.msg import String

from smartcar.hardware import DriveCommand
from smartcar.ros1_runtime import CommandMuxCore
from smartcar_autonomous_driving.msg import DriveCommand as DriveCommandMsg


class CommandMuxNode:
    def __init__(self) -> None:
        vehicle = rospy.get_param("/smartcar/vehicle", {})
        self._lock = threading.Lock()
        self._core = CommandMuxCore(
            neutral=int(vehicle.get("neutral", 1500)),
            timeout=float(rospy.get_param("~command_timeout", 0.3)),
            mode=rospy.get_param("~default_mode", "autonomous"),
        )
        self._publisher = rospy.Publisher("cmd_drive", DriveCommandMsg, queue_size=1)
        rospy.Subscriber("cmd_drive/autonomous", DriveCommandMsg, self._on_auto, queue_size=1)
        rospy.Subscriber("cmd_drive/manual", DriveCommandMsg, self._on_manual, queue_size=1)
        rospy.Subscriber("control_mode", String, self._on_mode, queue_size=1)
        rate = float(rospy.get_param("~publish_rate", 30.0))
        self._timer = rospy.Timer(rospy.Duration(1.0 / rate), self._on_timer)

    def _update(self, source: str, msg: DriveCommandMsg) -> None:
        with self._lock:
            self._core.update(source, DriveCommand(msg.throttle, msg.steering), time.monotonic())

    def _on_auto(self, msg: DriveCommandMsg) -> None:
        self._update("autonomous", msg)

    def _on_manual(self, msg: DriveCommandMsg) -> None:
        self._update("manual", msg)

    def _on_mode(self, msg: String) -> None:
        try:
            with self._lock:
                self._core.set_mode(msg.data.strip().lower())
                mode = self._core.mode
            rospy.loginfo("command_mux_node: mode=%s", mode)
        except ValueError as exc:
            rospy.logwarn("command_mux_node: %s", exc)

    def _on_timer(self, _event) -> None:
        with self._lock:
            selected = self._core.select(time.monotonic())
        out = DriveCommandMsg()
        out.header.stamp = rospy.Time.now()
        out.throttle = selected.throttle
        out.steering = selected.steering
        self._publisher.publish(out)


def main() -> None:
    rospy.init_node("command_mux_node")
    CommandMuxNode()
    rospy.spin()


if __name__ == "__main__":
    main()
