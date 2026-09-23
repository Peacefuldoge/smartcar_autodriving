#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS="${SMARTCAR_CATKIN_WS:-$HOME/catkin_ws}"
PKG_LINK="$WS/src/smartcar_autonomous_driving"

if [[ ! -f /opt/ros/noetic/setup.bash ]]; then
  echo "ROS 1 Noetic not found at /opt/ros/noetic." >&2
  echo "Install it first with: sudo bash scripts/install_ros1_noetic_focal.sh" >&2
  exit 2
fi

# shellcheck disable=SC1091
source /opt/ros/noetic/setup.bash

mkdir -p "$WS/src"
if [[ ! -e "$WS/src/CMakeLists.txt" ]]; then
  (cd "$WS/src" && catkin_init_workspace)
fi

if [[ -L "$PKG_LINK" ]]; then
  ln -sfn "$ROOT" "$PKG_LINK"
elif [[ -e "$PKG_LINK" ]]; then
  if [[ "$(readlink -f "$PKG_LINK")" != "$ROOT" ]]; then
    echo "Workspace already contains a different package at: $PKG_LINK" >&2
    exit 3
  fi
else
  ln -s "$ROOT" "$PKG_LINK"
fi

printf 'Resolving package dependencies...\n'
rosdep install --from-paths "$WS/src" --ignore-src -r -y

printf '\nBuilding with catkin_make...\n'
catkin_make -C "$WS"

# shellcheck disable=SC1090
source "$WS/devel/setup.bash"

printf '\nRunning project validation...\n'
python3 -m compileall -q "$ROOT/src" "$ROOT/ros_nodes" "$ROOT/host_tools" "$ROOT/test" "$ROOT/tests" "$ROOT/scripts"
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -q "$ROOT/tests"
rospack find smartcar_autonomous_driving >/dev/null
rostest smartcar_autonomous_driving behavior_ros.test
rostest smartcar_autonomous_driving logistics_ros.test

printf '\nAll ROS1 build and test steps passed.\n'
