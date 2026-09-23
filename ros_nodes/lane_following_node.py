#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import rospkg
import rospy
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image
from std_msgs.msg import Int32

from smartcar.config import resolve_project_path
from smartcar.lane_following import (
    LanePreprocessConfig,
    PaddleLiteLaneModel,
    preprocess_lane_frame,
    steering_from_model_output,
)


class LaneFollowingNode:
    def __init__(self) -> None:
        cfg = rospy.get_param("/smartcar/lane_model", {})
        vehicle = rospy.get_param("/smartcar/vehicle", {})
        root = Path(rospkg.RosPack().get_path("smartcar_autonomous_driving"))

        self._pre_cfg = LanePreprocessConfig(
            input_size=int(cfg.get("input_size", 128)),
            hsv_lower=tuple(cfg.get("hsv_lower", [25, 75, 190])),
            hsv_upper=tuple(cfg.get("hsv_upper", [40, 255, 255])),
            legacy_memory_layout=bool(cfg.get("legacy_memory_layout", True)),
        )
        self._minimum = int(vehicle.get("steering_min", 500))
        self._maximum = int(vehicle.get("steering_max", 2450))
        model_path = resolve_project_path(cfg.get("path", "models/lane/model_infer"), root)
        self._model = PaddleLiteLaneModel(model_path)
        self._bridge = CvBridge()
        self._publisher = rospy.Publisher("lane/steering", Int32, queue_size=1)
        self._subscriber = rospy.Subscriber("camera/image_raw", Image, self._on_image, queue_size=1, buff_size=2 ** 24)
        rospy.loginfo("lane_following_node: model=%s", model_path)

    def _on_image(self, msg: Image) -> None:
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            tensor = preprocess_lane_frame(frame, self._pre_cfg)
            raw = self._model.predict(tensor)
            steering = steering_from_model_output(raw, self._minimum, self._maximum)
            self._publisher.publish(Int32(data=steering))
        except (CvBridgeError, RuntimeError, ValueError) as exc:
            rospy.logerr_throttle(2.0, "lane_following_node inference failed: %s", exc)


def main() -> None:
    rospy.init_node("lane_following_node")
    LaneFollowingNode()
    rospy.spin()


if __name__ == "__main__":
    main()
