from pathlib import Path

import cv2
import numpy as np
import pytest

from smartcar.face_recognition import (
    CascadeFaceDetector,
    ConsecutivePresenceVerifier,
    default_frontal_face_cascade,
)


def test_default_opencv_frontal_cascade_loads():
    path = Path(default_frontal_face_cascade())
    assert path.exists()
    detector = CascadeFaceDetector(path)
    assert not detector.classifier.empty()


def test_blank_frame_has_no_face():
    detector = CascadeFaceDetector(default_frontal_face_cascade(), min_size=(20, 20))
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    assert detector.detect(image) == []


def test_empty_image_rejected():
    detector = CascadeFaceDetector(default_frontal_face_cascade())
    with pytest.raises(ValueError, match='empty image'):
        detector.detect(np.empty((0, 0), dtype=np.uint8))


def test_face_presence_requires_consecutive_frames():
    verifier = ConsecutivePresenceVerifier(3)
    verifier.set_expected('alice')
    assert not verifier.update(True)
    assert not verifier.update(True)
    assert verifier.update(True)
    assert not verifier.update(False)


def test_changing_recipient_resets_counter():
    verifier = ConsecutivePresenceVerifier(2)
    verifier.set_expected('alice')
    assert not verifier.update(True)
    verifier.set_expected('bob')
    assert not verifier.update(True)
    assert verifier.update(True)


def test_regular_opencv_build_is_enough():
    # The CascadeClassifier API is part of the normal OpenCV build; cv2.face is
    # deliberately not required anymore.
    assert hasattr(cv2, 'CascadeClassifier')
