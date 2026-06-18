# AGENTS.md

## Repository context

This repository currently contains a TurtleBot/UWB-LiDAR charging project.
Do not remove or rewrite the existing ROS project unless explicitly asked.

A new follow-up research workspace is added under:

- `research/uwb_followup/`

## UWB follow-up research goal

The follow-up study focuses on UWB RTLS methods from the reference projects:

- `FastTurtle7892/UWB-Ranging-Optimization`
- `FastTurtle7892/UWB_AoA_Project`
- `FastTurtle7892/UWB-Autonomous-Robot` only as background/reference

The first goal is not hardware flashing. The first goal is to reproduce the method in simulation and identify weaknesses.

Focus on:

1. DS-TWR ranging and timing parameters
2. Treply / packet time / measurement-rate tradeoff
3. AoA angle estimation from phase difference
4. 2D position estimation from range R and angle theta
5. Error analysis and filtering

## Constraints

- Codex cloud cannot access local UWB hardware, USB, UART, nRF boards, Raspberry Pi SPI, or Segger Embedded Studio.
- Do not attempt to flash hardware from the cloud environment.
- Hardware-specific code should be analyzed and documented, not executed in Codex cloud.
- Keep reference/original repositories unchanged unless explicitly asked.
- New research code should go under `research/uwb_followup/`.

## Setup

Install Python dependencies with:

```bash
pip install -r requirements.txt
```

Run the baseline UWB AoA simulation with:

```bash
python research/uwb_followup/simulation/run_all.py
```

## Validation

Run:

```bash
python research/uwb_followup/simulation/run_all.py
python -m pytest research/uwb_followup/tests
```

If tests are missing, create basic tests for numerical functions before changing algorithms.

## Suggested first Codex tasks

1. Inspect `research/uwb_followup/README.md`.
2. Summarize the FastTurtle7892 UWB reference repositories in `research/uwb_followup/notes/repo_map.md`.
3. Extend the baseline simulation to compare vertical, horizontal, and diagonal movement.
4. Add RMSE, mean error, max error, x-axis error, and y-axis error metrics.
5. Compare raw estimates, moving average, median filter, and Kalman filter.
6. Save plots under `research/uwb_followup/results/`.
