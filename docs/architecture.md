# Architecture

The refactor separates the original monolithic competition scripts into five responsibilities:

```text
V4L2 camera
   |
   +--> HSV lane mask --> Paddle Lite steering regressor --> servo calibration --+
   |                                                                              |
   +--> RGB 256x256 --> Paddle Mobile Tiny-YOLO --> detections --> behavior rules --+--> DriveCommand
                                                                                         |
                                                                                  libart_driver.so
                                                                                         |
                                                                                   serial @ 38400
                                                                                         |
                                                                                 motor-controller MCU
```

## Runtime flow

1. Capture a 424x240 MJPEG frame from `/dev/video2`.
2. Lane branch: threshold yellow lane markings in HSV, resize to 128x128, run the steering-regression model, then apply the historical servo calibration curve.
3. Detection branch: resize RGB to 256x256, normalize to the Paddle Mobile input range, run the Tiny-YOLO detector.
4. Behavior layer: confirm detections across multiple frames and apply course-level actions such as speed-limit mode, stop-line handling, left-turn bias and overtaking.
5. Vehicle layer: send `(throttle, steering)` commands through `libart_driver.so` to `/dev/ttyUSB0`.
6. The MCU converts steering into differential left/right motor commands.

## Why the refactor matters

The original code mixed inference, device initialization, global state and vehicle commands in the same file. A single detection could call `send_cmd` many times in one frame, and all classes shared one confirmation counter. The new layout makes inference, behavior and hardware independently testable while keeping the historical model interfaces and calibration logic.
