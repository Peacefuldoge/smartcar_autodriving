from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraConfig:
    device: str = "/dev/video2"
    width: int = 424
    height: int = 240
    fourcc: str = "MJPG"


class V4L2MJPEGCamera:
    """Small wrapper around the v4l2capture API used by the original project."""

    def __init__(self, config: CameraConfig):
        try:
            import v4l2capture  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "v4l2capture is required on the embedded target. "
                "Install the board-compatible package before running the car."
            ) from exc

        self._select = __import__("select")
        self._video = v4l2capture.Video_device(config.device)
        self._video.set_format(config.width, config.height, fourcc=config.fourcc)
        self._video.create_buffers(1)
        self._video.queue_all_buffers()
        self._video.start()

    def read(self) -> np.ndarray:
        self._select.select((self._video,), (), ())
        image_data = self._video.read_and_queue()
        frame = cv2.imdecode(np.frombuffer(image_data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Camera returned an undecodable MJPEG frame")
        return frame

    def close(self) -> None:
        close = getattr(self._video, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "V4L2MJPEGCamera":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
