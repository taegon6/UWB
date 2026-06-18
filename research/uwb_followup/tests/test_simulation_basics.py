import sys
from pathlib import Path

import numpy as np

SIM_DIR = Path(__file__).resolve().parents[1] / "simulation"
if str(SIM_DIR) not in sys.path:
    sys.path.insert(0, str(SIM_DIR))

from aoa_baseline import phase_to_angle, polar_to_xy
from filters import simple_kalman_1d
from metrics import position_rmse


def test_phase_to_angle_zero():
    angle = phase_to_angle(np.array([0.0]))
    assert np.allclose(angle, np.array([0.0]))


def test_polar_to_xy_unit_x_axis():
    x, y = polar_to_xy(np.array([1.0]), np.array([0.0]))
    assert np.allclose(x, np.array([1.0]))
    assert np.allclose(y, np.array([0.0]))


def test_position_rmse_zero_for_identical_paths():
    true_x = np.array([1.0, 2.0, 3.0])
    true_y = np.array([4.0, 5.0, 6.0])
    assert position_rmse(true_x, true_y, true_x, true_y) == 0.0


def test_simple_kalman_preserves_length():
    values = np.array([1.0, 1.1, 0.9, 1.0])
    filtered = simple_kalman_1d(values)
    assert len(filtered) == len(values)
