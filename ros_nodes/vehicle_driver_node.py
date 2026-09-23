#!/usr/bin/env python3
from __future__ import annotations

import time
import threading
from pathlib import Path

import rospkg
import rospy

from smartcar.config import resolve_project_path
from smartcar.hardware import DriveCommand, DryRunDriver, RaceCarDriver
from smartcar_autonomous_driving.msg import DriveCommand as DriveCommandMsg


class VehicleDriverNode:
    def __init__(self) -> None:
        vehicle = rospy.get_param("/smartcar/vehicle", {})
        root = Path(rospkg.RosPack().get_path("smartcar_autonomous_driving"))
        self._neutral = int(vehicle.get("neutral", 1500))
        self._lock = threading.Lock()
        self._timeout = float(rospy.get_param("~watchdog_timeout", 0.3))
        self._last_rx = time.monotonic()
        self._stopped_for_timeout = False

        if bool(rospy.get_param("~dry_run", False)):
            self._driver = DryRunDriver()
            rospy.logwarn("vehicle_driver_node: DRY RUN enabled; no command will reach the vehicle")
        else:
            library = resolve_project_path(vehicle.get("driver_library", "lib/libart_driver.so"), root)
            self._driver = RaceCarDriver(
                library,
                vehicle.get("serial_device", "/dev/ttyUSB0"),
                int(vehicle.get("baudrate", 38400)),
            )
            rospy.loginfo("vehicle_driver_node: serial=%s", vehicle.get("serial_device", "/dev/ttyUSB0"))

        rospy.Subscriber("cmd_drive", DriveCommandMsg, self._on_command, queue_size=1)
        self._timer = rospy.Timer(rospy.Duration(max(0.02, self._timeout / 3.0)), self._watchdog)
        rospy.on_shutdown(self._on_shutdown)

    def _on_command(self, msg: DriveCommandMsg) -> None:
        with self._lock:
            self._last_rx = time.monotonic()
            self._stopped_for_timeout = False
            self._driver.send(DriveCommand(int(msg.throttle), int(msg.steering)))

    def _watchdog(self, _event) -> None:
        timed_out = False
        with self._lock:
            if time.monotonic() - self._last_rx > self._timeout and not self._stopped_for_timeout:
                self._driver.stop(self._neutral)
                self._stopped_for_timeout = True
                timed_out = True
        if timed_out:
            rospy.logwarn("vehicle_driver_node: command timeout; neutral command sent")

    def _on_shutdown(self) -> None:
        with self._lock:
            self._driver.stop(self._neutral)


def main() -> None:
    rospy.init_node("vehicle_driver_node")
    VehicleDriverNode()
    rospy.spin()


if __name__ == "__main__":
    main()
