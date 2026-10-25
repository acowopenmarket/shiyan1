#!/usr/bin/env bash
# No camera, hardware bridge, or gripper node is started.
set -eo pipefail
cd "$(dirname "$0")/.."
repo_root="$PWD"
export PYTHONDONTWRITEBYTECODE=1
python3 scripts/verify_sources.py
python3 t/check_syntax.py
python3 t/test_angle_boundary.py -v
PYTHONPATH="$repo_root/camera" python3 -m unittest discover -s camera/tests -v
python3 -m unittest discover -s estun/tests -p test_motion.py -v
python3 -m unittest discover -s try/tests -p test_pick.py -v
PYTHONPATH="$repo_root/jia/ros2_ws/src/ms42_gripper" python3 -m unittest discover \
  -s jia/ros2_ws/src/ms42_gripper/test -p test_protocol.py -v
PYTHONPATH="$repo_root/jia/ros2_ws/src/ms42_gripper" python3 -m unittest discover \
  -s jia/ros2_ws/src/ms42_gripper/test -p test_client.py -v
echo "Site log summary is optional and requires private local records (not published)."
