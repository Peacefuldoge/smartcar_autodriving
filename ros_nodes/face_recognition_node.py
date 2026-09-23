#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import threading
from typing import Dict

import cv2
import rospkg
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String

from smartcar.config import resolve_project_path
from smartcar.face_recognition import (
    CascadeFaceDetector,
    ConsecutivePresenceVerifier,
    default_frontal_face_cascade,
)
from smartcar_autonomous_driving.msg import FaceRecognition


class FaceRecognitionNode:
    """Delivery face gate implemented with OpenCV CascadeClassifier.

    Modes:
      presence: a generic frontal-face cascade only proves that a face is in
                front of the camera.  It does NOT identify the recipient.
      recipient_cascade: load a recipient-specific cascade XML from the mapping
                in config.  This is only as reliable as the custom classifier.
    """

    def __init__(self) -> None:
        cfg = rospy.get_param('/smartcar/face_recognition', {})
        root = Path(rospkg.RosPack().get_path('smartcar_autonomous_driving'))
        self._mode = str(cfg.get('mode', 'presence')).strip().lower()
        if self._mode not in {'presence', 'recipient_cascade'}:
            raise ValueError("face_recognition.mode must be 'presence' or 'recipient_cascade'")

        cascade_path = str(cfg.get('cascade_path', '')).strip()
        if cascade_path:
            cascade_path = str(resolve_project_path(cascade_path, root))
        else:
            cascade_path = default_frontal_face_cascade()

        min_size = cfg.get('min_face_size', [60, 60])
        self._detector_kwargs = {
            'scale_factor': float(cfg.get('scale_factor', 1.1)),
            'min_neighbors': int(cfg.get('min_neighbors', 5)),
            'min_size': (int(min_size[0]), int(min_size[1])),
        }
        self._generic_detector = CascadeFaceDetector(cascade_path, **self._detector_kwargs)

        configured: Dict[str, str] = cfg.get('recipient_cascades', {}) or {}
        self._recipient_paths = {
            str(recipient): str(resolve_project_path(path, root))
            for recipient, path in configured.items()
        }
        self._recipient_detectors: Dict[str, CascadeFaceDetector] = {}

        self._bridge = CvBridge()
        self._enabled = False
        self._lock = threading.Lock()
        self._verifier = ConsecutivePresenceVerifier(int(cfg.get('required_matches', 3)))
        self._publisher = rospy.Publisher('face/recognition', FaceRecognition, queue_size=5)
        rospy.Subscriber('camera/image_raw', Image, self._on_image, queue_size=1, buff_size=2 ** 24)
        rospy.Subscriber('delivery/recognition_enabled', Bool, self._on_enabled, queue_size=1)
        rospy.Subscriber('delivery/expected_recipient', String, self._on_expected, queue_size=1)

        rospy.loginfo('face_recognition_node: CascadeClassifier mode=%s', self._mode)
        if self._mode == 'presence':
            rospy.logwarn(
                'face_recognition_node: presence mode confirms only that a face is visible; '
                'it does not identify the recipient'
            )

    def _on_enabled(self, msg: Bool) -> None:
        with self._lock:
            self._enabled = bool(msg.data)
            if not self._enabled:
                self._verifier.reset()

    def _on_expected(self, msg: String) -> None:
        with self._lock:
            self._verifier.set_expected(msg.data.strip())

    def _detector_for(self, expected: str) -> CascadeFaceDetector | None:
        if self._mode == 'presence':
            return self._generic_detector
        if not expected:
            return None
        detector = self._recipient_detectors.get(expected)
        if detector is not None:
            return detector
        path = self._recipient_paths.get(expected)
        if not path:
            rospy.logwarn_throttle(
                5.0,
                'face_recognition_node: no recipient cascade configured for %s',
                expected,
            )
            return None
        try:
            detector = CascadeFaceDetector(path, **self._detector_kwargs)
        except Exception as exc:
            rospy.logerr_throttle(5.0, 'face_recognition_node: cannot load %s: %s', path, exc)
            return None
        self._recipient_detectors[expected] = detector
        return detector

    def _on_image(self, msg: Image) -> None:
        with self._lock:
            if not self._enabled:
                return
            expected = self._verifier.expected
        if not expected:
            return

        detector = self._detector_for(expected)
        if detector is None:
            return
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        detections = detector.detect(frame)
        detected = bool(detections)

        with self._lock:
            verified = self._verifier.update(detected)

        out = FaceRecognition()
        out.header.stamp = rospy.Time.now()
        out.label = 1 if detected else -1
        # Compatibility with the existing mission interface.  In generic
        # presence mode this is the expected task recipient, not an independently
        # recognized biometric identity.
        out.person_id = expected if detected else ''
        out.distance = 0.0 if detected else -1.0
        out.recognized = detected
        out.verified = verified
        self._publisher.publish(out)

        if verified:
            if self._mode == 'presence':
                rospy.loginfo_throttle(2.0, 'face_recognition_node: face-presence gate satisfied')
            else:
                rospy.loginfo_throttle(2.0, 'face_recognition_node: recipient cascade matched: %s', expected)


def main() -> None:
    rospy.init_node('face_recognition_node')
    FaceRecognitionNode()
    rospy.spin()


if __name__ == '__main__':
    main()
