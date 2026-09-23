from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class FacePrediction:
    label: int
    person_id: str
    distance: float
    recognized: bool


def preprocess_face(image: np.ndarray, size: Tuple[int, int] = (160, 160)) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("empty face image")
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif image.ndim == 2:
        gray = image
    else:
        raise ValueError("face image must be grayscale or BGR")
    gray = cv2.resize(gray, tuple(map(int, size)), interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(gray)


def require_fisherfaces() -> None:
    has_factory = hasattr(cv2, "face") and (
        hasattr(cv2.face, "FisherFaceRecognizer_create")
        or hasattr(cv2.face, "FisherFaceRecognizer")
    )
    if not has_factory:
        raise RuntimeError(
            "FisherFaces requires OpenCV contrib. Install the ROS/Python-compatible "
            "opencv-contrib build (the plain opencv-python package does not expose cv2.face)."
        )


def _create_fisherfaces(threshold: float):
    require_fisherfaces()
    if hasattr(cv2.face, "FisherFaceRecognizer_create"):
        return cv2.face.FisherFaceRecognizer_create(0, float(threshold))
    return cv2.face.FisherFaceRecognizer.create(0, float(threshold))


class FisherFacesModel:
    def __init__(self, *, threshold: float = 3500.0, face_size: Tuple[int, int] = (160, 160)) -> None:
        require_fisherfaces()
        self.threshold = float(threshold)
        self.face_size = tuple(map(int, face_size))
        self.model = _create_fisherfaces(self.threshold)
        self.labels: Dict[int, str] = {}

    def train(self, images: Iterable[np.ndarray], labels: Iterable[int], label_names: Dict[int, str]) -> None:
        processed = [preprocess_face(img, self.face_size) for img in images]
        label_values = np.asarray(list(labels), dtype=np.int32)
        if len(processed) != len(label_values) or len(processed) < 2:
            raise ValueError("images and labels must contain the same number of samples")
        if len(set(label_values.tolist())) < 2:
            raise ValueError("FisherFaces requires at least two different people/classes")
        self.model.train(processed, label_values)
        self.labels = {int(k): str(v) for k, v in label_names.items()}

    def predict(self, face: np.ndarray) -> FacePrediction:
        label, distance = self.model.predict(preprocess_face(face, self.face_size))
        label = int(label)
        person = self.labels.get(label, "") if label >= 0 else ""
        return FacePrediction(label, person, float(distance), label >= 0 and bool(person))

    def save(self, model_path: Path, labels_path: Path) -> None:
        model_path = Path(model_path)
        labels_path = Path(labels_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        self.model.write(str(model_path))
        labels_path.write_text(json.dumps(self.labels, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, model_path: Path, labels_path: Path) -> None:
        self.model.read(str(model_path))
        raw = json.loads(Path(labels_path).read_text(encoding="utf-8"))
        self.labels = {int(k): str(v) for k, v in raw.items()}


class ConsecutiveVerifier:
    def __init__(self, required_matches: int = 3) -> None:
        self.required_matches = max(1, int(required_matches))
        self.expected = ""
        self._count = 0

    def set_expected(self, person_id: str) -> None:
        person_id = str(person_id)
        if person_id != self.expected:
            self.expected = person_id
            self._count = 0

    def update(self, predicted_person: str) -> bool:
        if self.expected and predicted_person == self.expected:
            self._count += 1
        else:
            self._count = 0
        return self._count >= self.required_matches
