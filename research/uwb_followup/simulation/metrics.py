import numpy as np


def rmse(true_values: np.ndarray, estimated_values: np.ndarray) -> float:
    true_values = np.asarray(true_values)
    estimated_values = np.asarray(estimated_values)
    return float(np.sqrt(np.mean((true_values - estimated_values) ** 2)))


def position_error(
    true_x: np.ndarray,
    true_y: np.ndarray,
    est_x: np.ndarray,
    est_y: np.ndarray,
) -> np.ndarray:
    return np.sqrt((true_x - est_x) ** 2 + (true_y - est_y) ** 2)


def position_rmse(
    true_x: np.ndarray,
    true_y: np.ndarray,
    est_x: np.ndarray,
    est_y: np.ndarray,
) -> float:
    error_sq = (true_x - est_x) ** 2 + (true_y - est_y) ** 2
    return float(np.sqrt(np.mean(error_sq)))


def mean_position_error(
    true_x: np.ndarray,
    true_y: np.ndarray,
    est_x: np.ndarray,
    est_y: np.ndarray,
) -> float:
    return float(np.mean(position_error(true_x, true_y, est_x, est_y)))


def max_position_error(
    true_x: np.ndarray,
    true_y: np.ndarray,
    est_x: np.ndarray,
    est_y: np.ndarray,
) -> float:
    return float(np.max(position_error(true_x, true_y, est_x, est_y)))
