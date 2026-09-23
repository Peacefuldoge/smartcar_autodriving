#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import threading

import cv2
import rospkg
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String

from smartcar.face_recognition import ConsecutiveVerifier, FisherFacesModel
from smartcar.config import resolve_project_path
from smartcar_autonomous_driving.msg import FaceRecognition


class FaceRecognitionNode:
    def __init__(self) -> None:
        cfg = rospy.get_param('/smartcar/face_recognition', {})
        root = Path(rospkg.RosPack().get_path('smartcar_autonomous_driving'))
        size = cfg.get('face_size', [160, 160])
        self._model = FisherFacesModel(
            threshold=float(cfg.get('threshold', 3500.0)),
            face_size=(int(size[0]), int(size[1])),
        )
        self._model.load(
            resolve_project_path(cfg.get('model_path', 'models/fisherfaces.yml'), root),
            resolve_project_path(cfg.get('labels_path', 'models/fisherfaces_labels.json'), root),
        )
        cascade_path = cfg.get('cascade_path', '')
        if cascade_path:
            cascade_path = str(resolve_project_path(cascade_path, root))
        else:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self._cascade = cv2.CascadeClassifier(cascade_path)
        if self._cascade.empty():
            raise RuntimeError(f'Unable to load Haar cascade: {cascade_path}')

        self._bridge = CvBridge()
        self._enabled = False
        self._lock = threading.Lock()
        self._verifier = ConsecutiveVerifier(int(cfg.get('required_matches', 3)))
        self._scale_factor = float(cfg.get('scale_factor', 1.1))
        self._min_neighbors = int(cfg.get('min_neighbors', 5))
        min_size = cfg.get('min_face_size', [60, 60])
        self._min_size = (int(min_size[0]), int(min_size[1]))
        self._publisher = rospy.Publisher('face/recognition', FaceRecognition, queue_size=5)
        rospy.Subscriber('camera/image_raw', Image, self._on_image, queue_size=1, buff_size=2 ** 24)
        rospy.Subscriber('delivery/recognition_enabled', Bool, self._on_enabled, queue_size=1)
        rospy.Subscriber('delivery/expected_recipient', String, self._on_expected, queue_size=1)

    def _on_enabled(self, msg: Bool) -> None:
        with self._lock:
            self._enabled = bool(msg.data)

    def _on_expected(self, msg: String) -> None:
        with self._lock:
            self._verifier.set_expected(msg.data.strip())

    def _on_image(self, msg: Image) -> None:
        with self._lock:
            if not self._enabled:
                return
            expected = self._verifier.expected
        if not expected:
            return
        frame = self._bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=self._scale_factor,
            minNeighbors=self._min_neighbors,
            minSize=self._min_size,
        )
        if len(faces) == 0:
            return
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        prediction = self._model.predict(frame[y:y + h, x:x + w])
        with self._lock:
            verified = self._verifier.update(prediction.person_id if prediction.recognized else '')

        out = FaceRecognition()
        out.header.stamp = rospy.Time.now()
        out.label = prediction.label
        out.person_id = prediction.person_id
        out.distance = prediction.distance
        out.recognized = prediction.recognized
        out.verified = verified
        self._publisher.publish(out)
        if verified:
            rospy.loginfo_throttle(2.0, 'face_recognition_node: recipient verified: %s', prediction.person_id)


def main() -> None:
    rospy.init_node('face_recognition_node')
    FaceRecognitionNode()
    rospy.spin()


if __name__ == '__main__':
    main()
