import numpy as np
import pandas as pd


def moving_average(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Centered moving average filter."""
    return (
        pd.Series(values)
        .rolling(window=window, min_periods=1, center=True)
        .mean()
        .to_numpy()
    )


def median_filter(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Centered median filter."""
    return (
        pd.Series(values)
        .rolling(window=window, min_periods=1, center=True)
        .median()
        .to_numpy()
    )


def simple_kalman_1d(values: np.ndarray, q: float = 1e-3, r: float = 1e-2) -> np.ndarray:
    """Simple scalar Kalman filter.

    Args:
        values: 1D measurement sequence.
        q: Process noise.
        r: Measurement noise.
    """
    values = np.asarray(values)
    if values.size == 0:
        return values.copy()

    x_hat = values[0]
    p = 1.0
    output = []

    for z in values:
        p = p + q
        k = p / (p + r)
        x_hat = x_hat + k * (z - x_hat)
        p = (1.0 - k) * p
        output.append(x_hat)

    return np.array(output)
