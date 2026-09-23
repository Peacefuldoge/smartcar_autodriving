from __future__ import annotations

import csv
from pathlib import Path
from typing import Union
import time

import cv2

from .hardware import DriveCommand, RaceCarDriver
from .joystick import LinuxJoystick


def collect(
    output_dir: Union[str, Path],
    *,
    camera_device: str = "/dev/video2",
    joystick_device: str = "/dev/input/js0",
    serial_device: str = "/dev/ttyUSB0",
    library: Union[str, Path] = "lib/libart_driver.so",
    throttle: int = 1560,
    steering_min: int = 500,
    steering_max: int = 2450,
) -> None:
    """Collect camera frames and synchronized steering labels with a Linux joystick.

    Y starts recording, TL/TR stops and exits. The X axis controls steering.
    """
    output_dir = Path(output_dir)
    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    labels_path = output_dir / "labels.csv"

    cap = cv2.VideoCapture(camera_device)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open camera: {camera_device}")

    joystick = LinuxJoystick(joystick_device)
    driver = RaceCarDriver(library, serial_device)
    steering = 1500
    recording = False
    frame_id = _next_frame_id(image_dir)

    try:
        with labels_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if labels_path.stat().st_size == 0:
                writer.writerow(["frame", "steering", "throttle", "timestamp"])

            while True:
                for event in joystick.read_events():
                    if event.kind == "button" and event.name == "y" and event.value:
                        recording = True
                        print("recording started")
                    elif event.kind == "button" and event.name in {"tl", "tr"} and event.value:
                        return
                    elif event.kind == "axis" and event.name == "x":
                        steering = int(1500 - float(event.value) * 750)
                        steering = max(steering_min, min(steering_max, steering))

                driver.send(DriveCommand(throttle, steering))
                ok, frame = cap.read()
                if not ok:
                    continue

                if recording:
                    filename = f"{frame_id:06d}.jpg"
                    cv2.imwrite(str(image_dir / filename), frame)
                    writer.writerow([filename, steering, throttle, f"{time.time():.6f}"])
                    f.flush()
                    frame_id += 1
    finally:
        driver.stop()
        joystick.close()
        cap.release()


def _next_frame_id(image_dir: Path) -> int:
    ids = []
    for path in image_dir.glob("*.jpg"):
        try:
            ids.append(int(path.stem))
        except ValueError:
            continue
    return max(ids, default=-1) + 1
