# MATLAB Log Based UWB Calibration Workflow

This project uses a closed-loop calibration workflow:

1. Collect MATLAB/ROS logs from TurtleBot UWB experiments.
2. Save the log as `data/raw/*.csv`.
3. Run `tools/analyze_uwb_log.py`.
4. Generate `config/uwb_calibration.yaml`.
5. Launch ROS with the generated calibration parameters.
6. Validate with manual topic tests, Gazebo, rosbag replay, then real low-speed TurtleBot tests.

Preferred CSV columns:

```text
time,true_x,true_y,odom_x,odom_y,odom_yaw,
range_a0,range_a1,range_a2,range_a3,
uwb_x,uwb_y,cmd_linear,cmd_angular,
lidar_state,near_charger,selected_charger_id
```

Bias convention:

```text
anchor_bias = measured_range - expected_range
corrected_range = raw_range - anchor_bias
```

Existing logs with `cx_raw/cy_raw/cx_filtered/cy_filtered` can be used for stability checks, but they cannot produce anchor range bias without `true_x`, `true_y`, and `range_a*`.

## Evidence Pack

Build an AI-ready evidence pack:

```bash
python3 tools/build_evidence_pack.py --raw-dir data/raw --output-dir docs/evidence_pack
```

The evidence pack is the preferred input for GPT/Codex writing:

- It summarizes raw CSV logs.
- It copies the active config files.
- It records the code commit.
- It provides a writing prompt that forbids invented metrics.

Large raw files and rosbag files should stay outside Git or be stored in Drive/OneDrive. Keep manifests, summaries, and selected figures in the repository.
