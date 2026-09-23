import cv2
import numpy as np
import pytest

from smartcar.face_recognition import ConsecutiveVerifier, preprocess_face, require_fisherfaces


def test_face_preprocessing_produces_equal_sized_grayscale_image():
    image = np.zeros((80, 100, 3), dtype=np.uint8)
    out = preprocess_face(image, (64, 64))
    assert out.shape == (64, 64)
    assert out.dtype == np.uint8


def test_recipient_requires_consecutive_matches():
    verifier = ConsecutiveVerifier(3)
    verifier.set_expected('alice')
    assert not verifier.update('alice')
    assert not verifier.update('alice')
    assert verifier.update('alice')
    assert not verifier.update('bob')


def test_fisherfaces_dependency_is_explicit():
    if hasattr(cv2, 'face'):
        require_fisherfaces()
    else:
        with pytest.raises(RuntimeError, match='OpenCV contrib'):
            require_fisherfaces()
