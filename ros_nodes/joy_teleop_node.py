#!/usr/bin/env python3
from __future__ import annotations

import rospy
from sensor_msgs.msg import Joy

from smartcar.ros1_runtime import steering_from_joy_axis
from smartcar_autonomous_driving.msg import DriveCommand as DriveCommandMsg


class JoyTeleopNode:
    def __init__(self) -> None:
        vehicle = rospy.get_param("/smartcar/vehicle", {})
        self._neutral = int(vehicle.get("neutral", 1500))
        self._throttle = int(rospy.get_param("~throttle", vehicle.get("slow_speed", 1560)))
        self._axis = int(rospy.get_param("~steering_axis", 0))
        self._deadman = int(rospy.get_param("~deadman_button", -1))
        self._minimum = int(vehicle.get("steering_min", 500))
        self._maximum = int(vehicle.get("steering_max", 2450))
        self._span = int(rospy.get_param("~steering_span", 750))
        self._publisher = rospy.Publisher("cmd_drive/manual", DriveCommandMsg, queue_size=1)
        rospy.Subscriber("joy", Joy, self._on_joy, queue_size=1)

    def _on_joy(self, msg: Joy) -> None:
        enabled = self._deadman < 0 or (self._deadman < len(msg.buttons) and bool(msg.buttons[self._deadman]))
        axis = msg.axes[self._axis] if 0 <= self._axis < len(msg.axes) else 0.0
        steering = steering_from_joy_axis(
            axis,
            center=self._neutral,
            span=self._span,
            minimum=self._minimum,
            maximum=self._maximum,
        )
        out = DriveCommandMsg()
        out.header.stamp = rospy.Time.now()
        out.throttle = self._throttle if enabled else self._neutral
        out.steering = steering if enabled else self._neutral
        self._publisher.publish(out)


def main() -> None:
    rospy.init_node("joy_teleop_node")
    JoyTeleopNode()
    rospy.spin()


if __name__ == "__main__":
    main()
