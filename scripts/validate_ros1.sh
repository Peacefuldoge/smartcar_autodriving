#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m compileall -q src ros_nodes test tests scripts
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m pytest -q

if ! command -v rospack >/dev/null 2>&1; then
  echo "ROS1 is not sourced. Source your catkin workspace before running the ROS integration test." >&2
  exit 2
fi

rospack find smartcar_autonomous_driving >/dev/null
rostest smartcar_autonomous_driving behavior_ros.test
