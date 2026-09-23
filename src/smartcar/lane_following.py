from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Union

import cv2
import numpy as np


@dataclass(frozen=True)
class LanePreprocessConfig:
    input_size: int = 128
    hsv_lower: Tuple[int, int, int] = (25, 75, 190)
    hsv_upper: Tuple[int, int, int] = (40, 255, 255)
    legacy_memory_layout: bool = True


def preprocess_lane_frame(frame: np.ndarray, config: LanePreprocessConfig) -> np.ndarray:
    """Convert a camera frame into the tensor used by the historical steering model."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.asarray(config.hsv_lower, dtype=np.uint8),
        np.asarray(config.hsv_upper, dtype=np.uint8),
    )
    resized = cv2.resize(mask, (config.input_size, config.input_size), interpolation=cv2.INTER_AREA)
    bgr = cv2.cvtColor(resized.astype(np.float32), cv2.COLOR_GRAY2BGR) / 255.0

    if config.legacy_memory_layout:
        # The original code reshaped NHWC memory directly to NCHW.  It is kept as an
        # explicit compatibility option because the deployed model may have been tuned
        # against that exact preprocessing path.
        return np.ascontiguousarray(bgr[np.newaxis, ...].reshape(1, 3, config.input_size, config.input_size))

    return np.ascontiguousarray(bgr.transpose(2, 0, 1)[np.newaxis, ...])


def steering_from_model_output(raw_value: float, minimum: int = 500, maximum: int = 2450) -> int:
    """Reproduce the final steering calibration found in Auto_Driver_client2.py."""
    steering = int(raw_value * 600 + 1200)

    if steering >= 1725:
        steering += 498
    elif steering >= 1580:
        steering += 497
    elif steering >= 1525:
        steering += 492

    if steering <= 1360:
        steering -= 418
    elif steering <= 1470:
        steering -= 418
    elif steering <= 1499:
        steering -= 430

    return max(minimum, min(maximum, steering))


class PaddleLiteLaneModel:
    """Paddle Lite wrapper for the lane-steering regression model."""

    def __init__(self, model_dir: Union[str, Path]):
        try:
            from paddlelite import (  # type: ignore
                CxxConfig,
                CreatePaddlePredictor,
                DataLayoutType,
                Place,
                PrecisionType,
                TargetType,
            )
        except ImportError as exc:
            raise RuntimeError(
                "The Paddle Lite Python runtime is missing. Install the version supplied "
                "for the embedded board / accelerator SDK."
            ) from exc

        model_dir = Path(model_dir)
        model_file = model_dir / "model"
        params_file = model_dir / "params"
        if not model_file.exists() or not params_file.exists():
            raise FileNotFoundError(
                f"Lane model files are missing under {model_dir}; expected 'model' and 'params'."
            )

        valid_places = (
            Place(TargetType.kFPGA, PrecisionType.kFP16, DataLayoutType.kNHWC),
            Place(TargetType.kHost, PrecisionType.kFloat),
            Place(TargetType.kARM, PrecisionType.kFloat),
        )
        config = CxxConfig()
        config.set_model_file(str(model_file))
        config.set_param_file(str(params_file))
        config.set_valid_places(valid_places)
        self._predictor = CreatePaddlePredictor(config)

    def predict(self, tensor: np.ndarray) -> float:
        input_tensor = self._predictor.get_input(0)
        input_tensor.resize(tuple(tensor.shape))
        input_tensor.set_data(tensor)
        self._predictor.run()
        output = self._predictor.get_output(0)
        return float(output.data()[0][0])
