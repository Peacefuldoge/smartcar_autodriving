from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class FaceDetection:
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height


class CascadeFaceDetector:
    """OpenCV CascadeClassifier wrapper used for delivery face verification.

    A generic frontal-face cascade detects the presence of a face; it does not
    identify who that face belongs to.  A custom target-specific cascade XML can
    be supplied when such a model has been trained separately.
    """

    def __init__(
        self,
        cascade_path: str | Path,
        *,
        scale_factor: float = 1.1,
        min_neighbors: int = 5,
        min_size: Tuple[int, int] = (60, 60),
    ) -> None:
        self.cascade_path = str(cascade_path)
        self.scale_factor = float(scale_factor)
        self.min_neighbors = int(min_neighbors)
        self.min_size = (int(min_size[0]), int(min_size[1]))
        self.classifier = cv2.CascadeClassifier(self.cascade_path)
        if self.classifier.empty():
            raise RuntimeError(f"Unable to load OpenCV cascade classifier: {self.cascade_path}")

    def detect(self, image: np.ndarray) -> List[FaceDetection]:
        if image is None or image.size == 0:
            raise ValueError("empty image")
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif image.ndim == 2:
            gray = image
        else:
            raise ValueError("image must be grayscale or BGR")

        gray = cv2.equalizeHist(gray)
        boxes: Sequence[Sequence[int]] = self.classifier.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_size,
        )
        return [FaceDetection(*(int(v) for v in box)) for box in boxes]


def default_frontal_face_cascade() -> str:
    path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
    if not path.exists():
        raise RuntimeError(f"OpenCV default Haar cascade not found: {path}")
    return str(path)


class ConsecutivePresenceVerifier:
    """Require a face to be detected in N consecutive frames before accepting."""

    def __init__(self, required_matches: int = 3) -> None:
        self.required_matches = max(1, int(required_matches))
        self.expected = ""
        self._count = 0

    def set_expected(self, recipient_id: str) -> None:
        recipient_id = str(recipient_id).strip()
        if recipient_id != self.expected:
            self.expected = recipient_id
            self._count = 0

    def reset(self) -> None:
        self._count = 0

    def update(self, detected: bool) -> bool:
        if self.expected and bool(detected):
            self._count += 1
        else:
            self._count = 0
        return self._count >= self.required_matches


# Backwards-compatible alias used by older tests/imports.  It now expresses
# consecutive presence rather than FisherFaces identity matches.
ConsecutiveVerifier = ConsecutivePresenceVerifier
