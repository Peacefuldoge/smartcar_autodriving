#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path
import threading

import cv2
import message_filters
import rospkg
import rospy
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image
from std_srvs.srv import SetBool, SetBoolResponse

from smartcar.data_collection import _next_frame_id
from smartcar_autonomous_driving.msg import DriveCommand


class DataRecorderNode:
    """Record synchronized ROS camera frames and final drive commands.

    Recording is toggled through the private `~set_recording` SetBool service.  Using the
    final `/smartcar/cmd_drive` topic means labels match the command actually selected by
    the command mux rather than an upstream candidate command.
    """

    def __init__(self) -> None:
        root = Path(rospkg.RosPack().get_path("smartcar_autonomous_driving"))
        output_value = rospy.get_param("~output_dir", "data/ros_run")
        output = Path(output_value)
        self._output_dir = output if output.is_absolute() else (root / output)
        self._image_dir = self._output_dir / "images"
        self._image_dir.mkdir(parents=True, exist_ok=True)
        self._labels_path = self._output_dir / "labels.csv"
        self._frame_id = _next_frame_id(self._image_dir)
        self._recording = bool(rospy.get_param("~record_on_start", False))
        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._file = self._labels_path.open("a", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        if self._labels_path.stat().st_size == 0:
            self._writer.writerow(["frame", "steering", "throttle", "timestamp"])
            self._file.flush()

        image_sub = message_filters.Subscriber("camera/image_raw", Image)
        command_sub = message_filters.Subscriber("cmd_drive", DriveCommand)
        slop = float(rospy.get_param("~sync_slop", 0.05))
        queue_size = int(rospy.get_param("~sync_queue", 20))
        self._sync = message_filters.ApproximateTimeSynchronizer(
            [image_sub, command_sub], queue_size=queue_size, slop=slop
        )
        self._sync.registerCallback(self._on_pair)
        self._service = rospy.Service("~set_recording", SetBool, self._set_recording)
        rospy.on_shutdown(self._close)
        rospy.loginfo("data_recorder_node: output=%s recording=%s", self._output_dir, self._recording)

    def _set_recording(self, request) -> SetBoolResponse:
        with self._lock:
            self._recording = bool(request.data)
        state = "started" if self._recording else "stopped"
        rospy.loginfo("data_recorder_node: recording %s", state)
        return SetBoolResponse(success=True, message=f"recording {state}")

    def _on_pair(self, image_msg: Image, command_msg: DriveCommand) -> None:
        with self._lock:
            if not self._recording:
                return
            frame_id = self._frame_id
            self._frame_id += 1

        try:
            frame = self._bridge.imgmsg_to_cv2(image_msg, desired_encoding="bgr8")
        except CvBridgeError as exc:
            rospy.logerr_throttle(2.0, "data_recorder_node conversion failed: %s", exc)
            return

        filename = f"{frame_id:06d}.jpg"
        path = self._image_dir / filename
        if not cv2.imwrite(str(path), frame):
            rospy.logerr("data_recorder_node: failed to write %s", path)
            return

        stamp = image_msg.header.stamp.to_sec() if image_msg.header.stamp else rospy.Time.now().to_sec()
        with self._lock:
            self._writer.writerow([filename, command_msg.steering, command_msg.throttle, f"{stamp:.6f}"])
            self._file.flush()

    def _close(self) -> None:
        with self._lock:
            if not self._file.closed:
                self._file.flush()
                self._file.close()


def main() -> None:
    rospy.init_node("data_recorder_node")
    DataRecorderNode()
    rospy.spin()


if __name__ == "__main__":
    main()
