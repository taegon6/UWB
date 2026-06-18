# UWB Follow-up Research Workspace

This workspace is for follow-up research on UWB RTLS methods.

The first goal is to reproduce the original method in simulation before trying hardware flashing or UART-based measurement.

## Reference projects

- `FastTurtle7892/UWB-Ranging-Optimization`
- `FastTurtle7892/UWB_AoA_Project`
- `FastTurtle7892/UWB-Autonomous-Robot` as background/reference

## Research focus

1. DS-TWR ranging and timing parameters
2. `Treply`, packet time, and measurement-rate tradeoff
3. AoA angle estimation from phase difference
4. 2D position estimation from range `R` and angle `theta`
5. Error analysis and filtering

## Why simulation first?

The reference UWB projects depend on embedded hardware such as DW3000/DW3110, nRF52840-DK, Raspberry Pi SPI, UART logging, and vendor SDK build tools. Codex cloud cannot access those devices directly.

Therefore, this workspace starts with Python simulation:

```text
range R + angle theta
        -> x = R cos(theta)
        -> y = R sin(theta)
        -> noise injection
        -> filtering
        -> error metrics
```

## Setup

From the repository root:

```bash
pip install -r requirements.txt
```

## Run baseline simulation

```bash
python research/uwb_followup/simulation/run_all.py
```

The script prints RMSE and mean position error for raw and filtered estimates. It also saves a plot to:

```text
research/uwb_followup/results/aoa_filter_comparison.png
```

## Current baseline model

The simplified AoA relation is:

```text
theta = arcsin(delta_phi / pi)
```

Position is estimated by:

```text
x = R cos(theta)
y = R sin(theta)
```

## Next research tasks

1. Add horizontal and diagonal motion scenarios.
2. Separate range noise and angle noise experiments.
3. Compare x-axis error and y-axis error.
4. Add packet-time / Treply simulation for DS-TWR.
5. Document weaknesses in `notes/weakness_analysis.md`.
