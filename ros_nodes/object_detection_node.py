#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import rospkg
import rospy
from cv_bridge import CvBridge, CvBridgeError
from sensor_msgs.msg import Image

from smartcar.config import resolve_project_path
from smartcar.object_detection import PaddleMobileDetector
from smartcar_autonomous_driving.msg import Detection as DetectionMsg
from smartcar_autonomous_driving.msg import DetectionArray


class ObjectDetectionNode:
    def __init__(self) -> None:
        cfg = rospy.get_param("/smartcar/detector", {})
        root = Path(rospkg.RosPack().get_path("smartcar_autonomous_driving"))
        model_path = resolve_project_path(cfg.get("path", "models/detector/freeze_model"), root)
        self._threshold = float(cfg.get("score_threshold", 0.35))
        self._detector = PaddleMobileDetector(model_path, input_size=int(cfg.get("input_size", 256)))
        self._bridge = CvBridge()
        self._publisher = rospy.Publisher("detector/detections", DetectionArray, queue_size=1)
        self._subscriber = rospy.Subscriber("camera/image_raw", Image, self._on_image, queue_size=1, buff_size=2 ** 24)
        rospy.loginfo("object_detection_node: model=%s threshold=%.3f", model_path, self._threshold)

    def _on_image(self, msg: Image) -> None:
        try:
            frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            detections = self._detector.predict(frame, threshold=self._threshold)
            out = DetectionArray()
            out.header = msg.header
            for d in detections:
                item = DetectionMsg()
                item.label_id = d.label_id
                item.score = d.score
                item.xmin = d.xmin
                item.ymin = d.ymin
                item.xmax = d.xmax
                item.ymax = d.ymax
                out.detections.append(item)
            self._publisher.publish(out)
        except (CvBridgeError, RuntimeError, ValueError) as exc:
            rospy.logerr_throttle(2.0, "object_detection_node inference failed: %s", exc)


def main() -> None:
    rospy.init_node("object_detection_node")
    ObjectDetectionNode()
    rospy.spin()


if __name__ == "__main__":
    main()
