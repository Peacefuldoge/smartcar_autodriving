# Validation

## Validation completed in this environment

After adding GPS, RS-232 battery telemetry, UDP host communication, three-vehicle scheduling, return-home mission control and CascadeClassifier integration, the following checks were executed successfully:

```bash
python3 -m compileall -q src ros_nodes host_tools test tests scripts
PYTHONPATH=src python3 -m pytest -q
```

Current result: **31 passed**.

The tests include:

- original steering calibration and behavior-controller cases;
- non-blocking maneuver execution and command mux fail-safe behavior;
- GPS NMEA parsing and checksum rejection;
- RS-232 voltage parsing, battery percentage and low-voltage hysteresis;
- HMAC-authenticated UDP packets and real localhost UDP datagrams;
- a real subprocess integration test that starts the fleet coordinator, sends three vehicle heartbeats over UDP, submits a delivery job, verifies nearest-idle-car dispatch and acknowledges the assignment;
- three-car scheduling rules that exclude busy/low-battery vehicles;
- delivery mission transitions: pickup -> dropoff -> recipient verification -> complete;
- low-battery task abort -> return-home -> recovered/idle;
- GPS distance, bearing and arrival behavior;
- CascadeClassifier loading, blank-frame detection behavior and consecutive face-presence verification logic;
- ROS package / launch / rostest XML structure.

Bash syntax is checked for all `scripts/*.sh`, and all package/launch/test XML files are parsed. `CMakeLists.txt` is also configured against a lightweight mock catkin/rostest CMake package to catch CMake syntax and install-path errors. The updated Arduino-style motor-controller firmware is compiled with a small Arduino API stub using `g++ -fsyntax-only`, which checks the added battery-telemetry C++ syntax without pretending that the target board/toolchain is present.

## ROS integration tests included

Two real ROS1 tests are included for Ubuntu 20.04 / Noetic:

```bash
rostest smartcar_autonomous_driving behavior_ros.test
rostest smartcar_autonomous_driving logistics_ros.test
```

`logistics_ros.test` verifies the ROS message path for: valid GPS home capture -> delivery assignment -> low battery -> `RETURNING_HOME` -> home `NavigationGoal`.

## Environment limitation

This execution container still does **not** contain ROS1 (`rospy`, `roscore`, `catkin_make`, `rostest`) and has no external package-download access. Therefore a genuine Noetic message-generation/catkin build cannot be truthfully claimed here. Use `scripts/install_ros1_noetic_focal.sh` on Ubuntu 20.04 and then run:

```bash
bash scripts/build_and_test_ros1.sh
```

That script performs `rosdep install`, `catkin_make`, the pure-Python test suite, `behavior_ros.test`, and `logistics_ros.test`.

## CascadeClassifier runtime verification

The installed OpenCV build exposes `cv2.CascadeClassifier` and the bundled `haarcascade_frontalface_default.xml`; both are exercised by the unit tests in this repository. `cv2.face` is no longer required. The default delivery gate is face-presence verification only, not biometric identity recognition.
