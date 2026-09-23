from __future__ import annotations

import time
from pathlib import Path
from typing import Union

from .behavior import BehaviorController
from .camera import CameraConfig, V4L2MJPEGCamera
from .config import load_config, resolve_project_path
from .hardware import DryRunDriver, RaceCarDriver
from .lane_following import LanePreprocessConfig, PaddleLiteLaneModel, preprocess_lane_frame, steering_from_model_output
from .object_detection import PaddleMobileDetector


def run(config_path: Union[str, Path], *, dry_run: bool = False) -> None:
    config_path = Path(config_path).resolve()
    project_root = config_path.parent.parent
    cfg = load_config(config_path)

    camera_cfg = CameraConfig(**cfg["camera"])
    lane_cfg_raw = cfg["lane_model"]
    lane_cfg = LanePreprocessConfig(
        input_size=lane_cfg_raw["input_size"],
        hsv_lower=tuple(lane_cfg_raw["hsv_lower"]),
        hsv_upper=tuple(lane_cfg_raw["hsv_upper"]),
        legacy_memory_layout=lane_cfg_raw.get("legacy_memory_layout", True),
    )
    vehicle = cfg["vehicle"]

    lane_model = PaddleLiteLaneModel(resolve_project_path(lane_cfg_raw["path"], project_root))
    detector_cfg = cfg["detector"]
    detector = PaddleMobileDetector(
        resolve_project_path(detector_cfg["path"], project_root),
        input_size=detector_cfg["input_size"],
    )

    behavior_cfg = cfg["behavior"]
    behavior = BehaviorController(
        cruise_speed=vehicle["cruise_speed"],
        limited_speed=vehicle["limited_speed"],
        slow_speed=vehicle["slow_speed"],
        turn_speed=vehicle["turn_speed"],
        neutral=vehicle["neutral"],
        left_bias=behavior_cfg["left_bias"],
        left_bias_seconds=behavior_cfg["left_bias_seconds"],
        cooldown_seconds=behavior_cfg["cooldown_seconds"],
        confirmation_frames=behavior_cfg["confirmation_frames"],
    )

    driver = DryRunDriver() if dry_run else RaceCarDriver(
        project_root / "lib" / "libart_driver.so",
        vehicle["serial_device"],
        vehicle["baudrate"],
    )

    try:
        with V4L2MJPEGCamera(camera_cfg) as camera:
            while True:
                frame = camera.read()
                lane_tensor = preprocess_lane_frame(frame, lane_cfg)
                raw_steering = lane_model.predict(lane_tensor)
                steering = steering_from_model_output(
                    raw_steering,
                    minimum=vehicle["steering_min"],
                    maximum=vehicle["steering_max"],
                )
                detections = detector.predict(frame, threshold=detector_cfg["score_threshold"])
                decision = behavior.update(steering, detections)

                if decision.maneuver:
                    for step in decision.maneuver:
                        driver.send(step.command)
                        time.sleep(step.duration)
                else:
                    driver.send(decision.command)

                if decision.events:
                    print("events:", ", ".join(decision.events))
    except KeyboardInterrupt:
        pass
    finally:
        driver.stop(vehicle["neutral"])
