from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union

import cv2
import numpy as np


@dataclass(frozen=True)
class Detection:
    label_id: int
    score: float
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0)


class PaddleMobileDetector:
    """Thin wrapper around the Tiny-YOLO Paddle Mobile model used in the project."""

    def __init__(self, model_dir: Union[str, Path], input_size: int = 256):
        try:
            import paddlemobile as pm  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The Paddle Mobile Python runtime is missing. Install the board-compatible SDK package."
            ) from exc

        model_dir = Path(model_dir)
        if not model_dir.exists():
            raise FileNotFoundError(f"Object-detection model directory not found: {model_dir}")

        config = pm.PaddleMobileConfig()
        config.precision = pm.PaddleMobileConfig.Precision.FP32
        config.device = pm.PaddleMobileConfig.Device.kFPGA
        config.model_dir = str(model_dir)
        config.thread_num = 4
        self._predictor = pm.CreatePaddlePredictor(config)
        self._pm = pm
        self.input_size = input_size

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_size, self.input_size), interpolation=cv2.INTER_LINEAR)
        tensor = resized.astype(np.float32).transpose(2, 0, 1)
        tensor -= 127.5
        tensor *= 0.007843
        return tensor[np.newaxis, ...]

    def predict(self, frame: np.ndarray, threshold: float = 0.0) -> List[Detection]:
        tensor_img = self._preprocess(frame)
        tensor = self._pm.PaddleTensor()
        tensor.dtype = self._pm.PaddleDType.FLOAT32
        tensor.shape = tuple(tensor_img.shape)
        tensor.data = self._pm.PaddleBuf(tensor_img)

        outputs = self._predictor.Run([tensor])
        if len(outputs) != 1:
            raise RuntimeError(f"Expected one detector output tensor, got {len(outputs)}")

        bboxes = np.array(outputs[0], copy=False)
        if bboxes.ndim == 1 or bboxes.size == 0:
            return []

        detections: List[Detection] = []
        for row in bboxes:
            if len(row) < 6:
                continue
            label, score, xmin, ymin, xmax, ymax = row[:6]
            if float(score) < threshold:
                continue
            detections.append(
                Detection(int(label), float(score), float(xmin), float(ymin), float(xmax), float(ymax))
            )
        return detections
