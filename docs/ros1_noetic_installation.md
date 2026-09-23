# ROS 1 Noetic installation

This project targets **ROS 1 Noetic on Ubuntu 20.04 (Focal)**.

> ROS Noetic reached end-of-life on 31 May 2025. The final packages remain hosted, but Noetic no longer receives upstream security updates or bug fixes. Use it here because the original smart-car project is being preserved and modernized as a ROS1 project.

## Recommended installation

On Ubuntu 20.04:

```bash
cd smartcar-autonomous-driving-ros1
sudo bash scripts/install_ros1_noetic_focal.sh
source /opt/ros/noetic/setup.bash
```

The installer:

1. Verifies that the host is Ubuntu 20.04/Focal.
2. Installs the current ROS repository configuration package.
3. Verifies its SHA256 checksum.
4. Installs ROS Noetic `ros-base` plus the ROS packages needed by this repository.
5. Initializes `rosdep`.
6. Adds `/opt/ros/noetic/setup.bash` to `~/.bashrc`.
7. Verifies `roscore`, `roslaunch`, `catkin_make`, `rostest`, `rospy`, `cv_bridge`, `pyserial`, and OpenCV CascadeClassifier and default Haar-cascade support.

## Build and integration test

```bash
bash scripts/build_and_test_ros1.sh
```

By default the script builds in `~/catkin_ws`. To use another workspace:

```bash
SMARTCAR_CATKIN_WS=~/smartcar_ws bash scripts/build_and_test_ros1.sh
```

The validation sequence is:

```text
rosdep install
    ↓
catkin_make
    ↓
Python compileall
    ↓
pytest
    ↓
rospack find
    ↓
rostest behavior_ros.test
    ↓
rostest logistics_ros.test
```

## Ubuntu 22.04/24.04 or Debian

Do not install Noetic binary packages directly into those systems. Use an Ubuntu 20.04 VM, WSL2 distribution, or container for this ROS1 project. The upstream binary packages are built for Focal; mixing Focal ROS packages into a newer host can break system libraries.

## WSL2

For Windows development, the cleanest legacy setup is an Ubuntu 20.04 WSL2 distribution dedicated to ROS1. Build this repository inside that distribution, while keeping newer ML environments in a separate WSL2 distribution if necessary.
