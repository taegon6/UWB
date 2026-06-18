import numpy as np


def phase_to_angle(delta_phi: np.ndarray) -> np.ndarray:
    """Convert phase difference to AoA angle.

    Simplified relation used by the reference AoA project:
        theta = arcsin(delta_phi / pi)

    Args:
        delta_phi: Phase difference in radians.

    Returns:
        AoA angle theta in radians.
    """
    ratio = np.clip(delta_phi / np.pi, -1.0, 1.0)
    return np.arcsin(ratio)


def polar_to_xy(r: np.ndarray, theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert range and angle to 2D coordinates."""
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return x, y


def generate_vertical_motion(n: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """Generate a simple vertical movement path.

    This scenario is useful because the reference AoA README mentions
    Y-axis movement error as a weakness.
    """
    true_x = np.ones(n) * 2.0
    true_y = np.linspace(0.5, 4.0, n)
    return true_x, true_y


def add_measurement_noise(
    true_x: np.ndarray,
    true_y: np.ndarray,
    range_std: float = 0.05,
    angle_std_deg: float = 3.0,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Convert true x/y path to noisy range/angle measurements."""
    rng = np.random.default_rng(seed)

    true_r = np.sqrt(true_x**2 + true_y**2)
    true_theta = np.arctan2(true_y, true_x)

    noisy_r = true_r + rng.normal(0.0, range_std, len(true_r))
    noisy_theta = true_theta + rng.normal(0.0, np.deg2rad(angle_std_deg), len(true_theta))

    est_x, est_y = polar_to_xy(noisy_r, noisy_theta)
    return noisy_r, noisy_theta, est_x, est_y
