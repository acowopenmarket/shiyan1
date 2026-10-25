"""Regression checks for the authorized angle boundary correction; no hardware."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'camera'))
from coordinate_transform.pose_ranges import pose_component_ranges


class AngleBoundaryTests(unittest.TestCase):
    def test_stationary_across_pi(self):
        poses = [[.3, .1, .3, np.pi-1e-5, 0., -np.pi+2e-5],
                 [.3, .1, .3, -np.pi+1e-5, 0., np.pi-2e-5]]
        np.testing.assert_allclose(pose_component_ranges(poses), [0, 0, 0, 2e-5, 0, 4e-5], atol=1e-14)

    def test_real_motion_preserved(self):
        poses = [[.3, .1, .3, 3., .1, .2], [.301, .102, .303, -3., .2, .3]]
        np.testing.assert_allclose(pose_component_ranges(poses), [.001, .002, .003, 2*np.pi-6, .1, .1])

    def test_full_rotation_not_erased(self):
        poses = np.zeros((100, 6))
        poses[:, 3] = (np.linspace(0, 2*np.pi, 100) + np.pi) % (2*np.pi) - np.pi
        self.assertAlmostEqual(pose_component_ranges(poses)[3], 2*np.pi)

    def test_previous_capture(self):
        records = json.loads(Path(__file__).with_name('capture').joinpath('frame_records.json').read_text())
        poses = np.array([r['robot_pose'] for r in records])
        ranges = pose_component_ranges(poses)
        np.testing.assert_allclose(ranges[:3], np.ptp(poses, axis=0)[:3])
        self.assertLess(np.linalg.norm(ranges[3:]), .0017453292519943296)
        self.assertGreater(np.ptp(poses, axis=0)[3], 6.)


if __name__ == '__main__':
    unittest.main()
