#!/usr/bin/env bash
set -euo pipefail

# Installs ROS 1 Noetic and the dependencies required by this project.
# ROS Noetic binary packages target Ubuntu 20.04 (Focal).

if [[ ! -r /etc/os-release ]]; then
  echo "Cannot determine the operating system (/etc/os-release missing)." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID:-}" != "ubuntu" || "${VERSION_CODENAME:-}" != "focal" ]]; then
  cat >&2 <<MSG
ROS 1 Noetic binary installation requires Ubuntu 20.04 (Focal).
Detected: ${PRETTY_NAME:-unknown}

Recommended options:
  - Native/VM/WSL2: use Ubuntu 20.04.
  - Newer Ubuntu: run a Focal container/VM for this legacy ROS1 project.
MSG
  exit 2
fi

if [[ $EUID -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

ROS_APT_SOURCE_VERSION="1.3.0"
ROS_APT_SOURCE_URL="https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros-apt-source_${ROS_APT_SOURCE_VERSION}.focal_all.deb"
ROS_APT_SOURCE_SHA256="33a491f72e4e25491f8511c173526bb20ce84ff9faf596158f178f4900da5df1"
TMP_DEB="$(mktemp --suffix=.deb)"
trap 'rm -f "$TMP_DEB"' EXIT

export DEBIAN_FRONTEND=noninteractive

$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg lsb-release

printf 'Downloading ROS repository configuration...\n'
curl -fL --retry 3 --retry-delay 2 "$ROS_APT_SOURCE_URL" -o "$TMP_DEB"
echo "${ROS_APT_SOURCE_SHA256}  ${TMP_DEB}" | sha256sum -c -
$SUDO apt-get install -y "$TMP_DEB"

$SUDO apt-get update
$SUDO apt-get install -y --no-install-recommends \
  ros-noetic-ros-base \
  ros-noetic-cv-bridge \
  ros-noetic-joy \
  ros-noetic-message-filters \
  ros-noetic-message-generation \
  ros-noetic-message-runtime \
  ros-noetic-std-srvs \
  ros-noetic-rostest \
  python3-catkin-tools \
  python3-rosdep \
  python3-pytest \
  python3-opencv \
  python3-serial \
  python3-numpy

if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  $SUDO rosdep init
fi
rosdep update

SETUP_LINE='source /opt/ros/noetic/setup.bash'
if ! grep -Fxq "$SETUP_LINE" "$HOME/.bashrc" 2>/dev/null; then
  printf '\n# ROS 1 Noetic\n%s\n' "$SETUP_LINE" >> "$HOME/.bashrc"
fi

# shellcheck disable=SC1091
source /opt/ros/noetic/setup.bash

printf '\nROS 1 Noetic installation verification\n'
printf '%-18s %s\n' 'ROS_DISTRO:' "${ROS_DISTRO:-unset}"
printf '%-18s %s\n' 'roscore:' "$(command -v roscore)"
printf '%-18s %s\n' 'roslaunch:' "$(command -v roslaunch)"
printf '%-18s %s\n' 'catkin_make:' "$(command -v catkin_make)"
printf '%-18s %s\n' 'rostest:' "$(command -v rostest)"

python3 - <<'PY'
import rospy
import cv2
import cv_bridge
import serial
import sensor_msgs.msg
import std_msgs.msg
print("Python ROS imports: OK")
print("rospy:", rospy.__file__)
print("cv_bridge:", cv_bridge.__file__)
print("pyserial:", serial.__version__)
if not hasattr(cv2, "CascadeClassifier"):
    raise SystemExit("OpenCV CascadeClassifier is unavailable")
from pathlib import Path
cascade = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
model = cv2.CascadeClassifier(str(cascade))
if not cascade.exists() or model.empty():
    raise SystemExit(f"OpenCV Haar cascade unavailable: {cascade}")
print("OpenCV CascadeClassifier: OK")
PY

printf '\nROS 1 Noetic is installed. Open a new shell or run:\n'
printf '  source /opt/ros/noetic/setup.bash\n'
