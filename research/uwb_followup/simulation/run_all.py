from pathlib import Path
import sys

import matplotlib.pyplot as plt

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from aoa_baseline import add_measurement_noise, generate_vertical_motion
from filters import median_filter, moving_average, simple_kalman_1d
from metrics import max_position_error, mean_position_error, position_rmse


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    out_dir = base_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    true_x, true_y = generate_vertical_motion(n=200)
    _, _, est_x, est_y = add_measurement_noise(
        true_x,
        true_y,
        range_std=0.05,
        angle_std_deg=3.0,
        seed=42,
    )

    ma_x = moving_average(est_x, window=7)
    ma_y = moving_average(est_y, window=7)

    med_x = median_filter(est_x, window=7)
    med_y = median_filter(est_y, window=7)

    kal_x = simple_kalman_1d(est_x)
    kal_y = simple_kalman_1d(est_y)

    results = {
        "raw": (est_x, est_y),
        "moving_average": (ma_x, ma_y),
        "median": (med_x, med_y),
        "kalman": (kal_x, kal_y),
    }

    print("=== UWB AoA Position Estimation Simulation ===")
    for name, (x, y) in results.items():
        print(
            f"{name:15s} "
            f"position_rmse={position_rmse(true_x, true_y, x, y):.4f}, "
            f"mean_error={mean_position_error(true_x, true_y, x, y):.4f}, "
            f"max_error={max_position_error(true_x, true_y, x, y):.4f}"
        )

    plt.figure(figsize=(7, 7))
    plt.plot(true_x, true_y, label="True path", linewidth=3)
    plt.scatter(est_x, est_y, s=12, alpha=0.5, label="Raw estimate")
    plt.plot(ma_x, ma_y, label="Moving average")
    plt.plot(med_x, med_y, label="Median filter")
    plt.plot(kal_x, kal_y, label="Kalman filter")
    plt.axis("equal")
    plt.grid(True)
    plt.legend()
    plt.title("Single-anchor UWB AoA-DS-TWR Position Estimation")
    plt.xlabel("x [m]")
    plt.ylabel("y [m]")
    plt.tight_layout()
    plt.savefig(out_dir / "aoa_filter_comparison.png", dpi=200)
    plt.close()

    print(f"Saved plot to {out_dir / 'aoa_filter_comparison.png'}")


if __name__ == "__main__":
    main()
