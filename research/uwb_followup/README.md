# UWB Example Setup Workspace

This workspace is for preparing and inspecting UWB reference examples before doing follow-up research.

The immediate goal is:

1. Clone the reference UWB repositories.
2. Check what examples exist.
3. Identify which example is currently selected.
4. Prepare a local/Codex workflow for reading and running what can be run without hardware.

This is not yet the analysis stage.

## Reference repositories

The setup script downloads these repositories under `research/uwb_followup/original_repos/`:

- `FastTurtle7892/UWB-Ranging-Optimization`
- `FastTurtle7892/UWB_AoA_Project`
- `FastTurtle7892/UWB-Autonomous-Robot`

## Codex / local setup

From the repository root:

```bash
pip install -r requirements.txt
bash research/uwb_followup/scripts/check_local_environment.sh
bash research/uwb_followup/scripts/bootstrap_reference_repos.sh
python research/uwb_followup/scripts/list_uwb_examples.py
```

## What each script does

### `check_local_environment.sh`

Checks whether basic tools are installed:

- `git`
- `python` / `python3`
- `pip`
- `make`
- `gcc` / `g++`

It also checks optional embedded tools:

- `arm-none-eabi-gcc`
- `JLinkExe`
- `nrfjprog`
- `minicom`
- `picocom`

These optional tools are mainly for local hardware work, not Codex cloud.

### `bootstrap_reference_repos.sh`

Clones or updates the reference UWB repositories into:

```text
research/uwb_followup/original_repos/
```

The cloned repositories are not committed into this repo. They are local working copies for inspection.

### `list_uwb_examples.py`

Scans the cloned repositories and prints:

- README files
- `example_selection.h` files
- active `#define` example selections
- commented example options
- example directories under `API/Src/examples/`

This is the first useful command to run in Codex after cloning the references.

## Important limitation

Codex cloud can inspect files, run Python scripts, and sometimes compile simple host-side code.

Codex cloud cannot directly access:

- nRF52840 boards
- DW3000/DW3110 hardware
- Raspberry Pi SPI
- USB UART
- Segger Embedded Studio GUI
- J-Link hardware

So the current workflow is:

```text
Codex:
  clone repos
  inspect examples
  check selected examples
  prepare build/run notes

Local PC / lab machine:
  install embedded tools
  connect UWB boards
  flash firmware
  read UART logs
```

## First Codex prompt

Use this prompt in Codex:

```text
Read AGENTS.md and research/uwb_followup/README.md.
Do not do analysis yet.
Set up the UWB example workspace only.

Run:
1. pip install -r requirements.txt
2. bash research/uwb_followup/scripts/check_local_environment.sh
3. bash research/uwb_followup/scripts/bootstrap_reference_repos.sh
4. python research/uwb_followup/scripts/list_uwb_examples.py

Then create research/uwb_followup/notes/example_inventory.md summarizing:
- which repositories were cloned
- which README files exist
- which example_selection.h files exist
- which examples are currently active
- which examples look relevant for DS-TWR, SS-TWR, AoA, and PDOA

Do not modify firmware code yet.
Do not create simulations yet.
Do not attempt hardware flashing.
```

## Later steps

After the example inventory is clear, the next step is to choose one minimal example to prepare for local hardware execution.

Likely candidates:

- device ID read test
- simple TX/RX
- SS-TWR initiator/responder
- DS-TWR initiator/responder
- PDOA/AoA-related examples
