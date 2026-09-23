# Validation

## Checks completed in the refactor environment

The following checks were executed successfully after the ROS1 integration:

```bash
python3 -m compileall -q src ros_nodes test tests scripts
PYTHONPATH=src python3 -m pytest -q
```

Result: **12 passed**.

The tests cover the original lane/behavior logic plus ROS-facing pure logic:

- steering calibration;
- speed-limit state transitions;
- one-shot stop-line behavior;
- overtaking sequence creation;
- non-blocking timed maneuver execution;
- autonomous/manual command mux and timeout-to-neutral behavior;
- joystick-to-steering mapping;
- ROS package/launch XML structure.

`CMakeLists.txt` was also configured with a lightweight mock catkin package so CMake syntax,
paths and install declarations could be checked in this container.

## Environment limitation

The build container used for this repository does **not** contain ROS1 (`rospy`, `roscore`,
`catkin_make` and `roslaunch` are absent). Therefore a genuine Noetic message-generation +
catkin build and live ROS master test cannot truthfully be claimed from this environment.

A real ROS integration test is included as `test/behavior_ros.test`. On an Ubuntu 20.04 /
ROS Noetic machine, after a successful catkin build and `source devel/setup.bash`, run:

```bash
rostest smartcar_autonomous_driving behavior_ros.test
```

or run all repository checks with:

```bash
./scripts/validate_ros1.sh
```

The rostest publishes synthetic lane steering and speed-limit detections and verifies the
resulting autonomous `DriveCommand` values without requiring a camera, Paddle model, serial
port, or physical car.
