# AGENTS.md

## Repository context

This repository currently contains a TurtleBot/UWB-LiDAR charging project.
Do not remove or rewrite the existing ROS project unless explicitly asked.

The UWB example setup workspace is under:

- `research/uwb_followup/`

## Current goal

The immediate goal is environment setup only.

Focus on:

1. Cloning the reference UWB repositories.
2. Checking available examples.
3. Identifying active `example_selection.h` definitions.
4. Preparing notes for local hardware execution later.

Do not start algorithm analysis, filtering research, or simulation expansion unless explicitly requested.

## Reference repositories

Use these as external/local reference repositories:

- `FastTurtle7892/UWB-Ranging-Optimization`
- `FastTurtle7892/UWB_AoA_Project`
- `FastTurtle7892/UWB-Autonomous-Robot`

They should be cloned under:

- `research/uwb_followup/original_repos/`

Do not commit cloned reference repositories into this repository.

## Constraints

- Codex cloud cannot access local UWB hardware, USB, UART, nRF boards, Raspberry Pi SPI, or Segger Embedded Studio.
- Do not attempt to flash hardware from the cloud environment.
- Hardware-specific code should be inspected and documented, not executed in Codex cloud.
- Keep reference/original repositories unchanged unless explicitly asked.
- New setup scripts or notes should go under `research/uwb_followup/`.

## Setup commands

From the repository root:

```bash
pip install -r requirements.txt
bash research/uwb_followup/scripts/check_local_environment.sh
bash research/uwb_followup/scripts/bootstrap_reference_repos.sh
python research/uwb_followup/scripts/list_uwb_examples.py
```

## Suggested first Codex task

1. Read `research/uwb_followup/README.md`.
2. Run the setup commands above.
3. Create `research/uwb_followup/notes/example_inventory.md`.
4. Summarize:
   - cloned repositories
   - README files
   - `example_selection.h` files
   - active examples
   - examples related to SS-TWR, DS-TWR, PDOA, AoA

Do not modify firmware code yet.
Do not create new simulations yet.
Do not attempt hardware flashing.
