#!/usr/bin/env bash
set -eo pipefail
cd "$(dirname "$0")"
source /opt/ros/humble/setup.bash
source ../estun/ros2_ws/install/setup.bash
python3 run_pick.py "$@"
