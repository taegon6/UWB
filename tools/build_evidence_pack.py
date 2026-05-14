#!/usr/bin/env python3

import argparse
import csv
import datetime
import glob
import math
import os
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description="Build an AI-ready evidence pack for reports or papers.")
    parser.add_argument("--raw-dir", default="data/raw", help="Directory containing raw CSV logs")
    parser.add_argument("--processed-dir", default="data/processed", help="Directory containing generated metrics")
    parser.add_argument("--figures-dir", default="data/figures", help="Directory containing figures")
    parser.add_argument("--output-dir", default="docs/evidence_pack", help="Evidence pack output directory")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.processed_dir, exist_ok=True)
    os.makedirs(args.figures_dir, exist_ok=True)

    csv_files = sorted(glob.glob(os.path.join(args.raw_dir, "*.csv")))
    summaries = [summarize_csv(path) for path in csv_files]
    git_commit = get_git_commit()

    write_project_summary(args.output_dir, git_commit)
    write_system_architecture(args.output_dir)
    write_algorithm_description(args.output_dir)
    write_experiment_table(args.output_dir, summaries)
    write_summary_metrics(args.output_dir, summaries)
    write_failure_cases(args.output_dir)
    write_ai_prompt(args.output_dir)
    write_code_version(args.output_dir, git_commit)
    copy_configs(args.output_dir)

    print("Evidence pack written to {}".format(args.output_dir))
    print("CSV logs summarized: {}".format(len(csv_files)))


def summarize_csv(path):
    rows = read_rows(path)
    summary = {
        "file": normalize_path(path),
        "rows": len(rows),
        "columns": [],
        "start_time": "",
        "end_time": "",
        "uwb_x_std": "",
        "uwb_y_std": "",
        "uwb_error_mean": "",
        "near_charger_count": "",
        "lidar_states": "",
    }

    if not rows:
        return summary

    summary["columns"] = list(rows[0].keys())
    summary["start_time"] = rows[0].get("time", "")
    summary["end_time"] = rows[-1].get("time", "")

    if has_columns(rows[0], ("uwb_x", "uwb_y")):
        summary["uwb_x_std"] = fmt(stdev(valid_column(rows, "uwb_x")))
        summary["uwb_y_std"] = fmt(stdev(valid_column(rows, "uwb_y")))

    if has_columns(rows[0], ("true_x", "true_y", "uwb_x", "uwb_y")):
        errors = []
        for row in rows:
            true_x = as_float(row.get("true_x"))
            true_y = as_float(row.get("true_y"))
            uwb_x = as_float(row.get("uwb_x"))
            uwb_y = as_float(row.get("uwb_y"))
            if None not in (true_x, true_y, uwb_x, uwb_y):
                errors.append(math.hypot(uwb_x - true_x, uwb_y - true_y))
        summary["uwb_error_mean"] = fmt(mean(errors))

    if "near_charger" in rows[0]:
        summary["near_charger_count"] = str(sum(1 for row in rows if str(row.get("near_charger", "")).lower() in ("true", "1")))

    if "lidar_state" in rows[0]:
        states = sorted(set(row.get("lidar_state", "") for row in rows if row.get("lidar_state", "")))
        summary["lidar_states"] = ";".join(states)

    return summary


def read_rows(path):
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as csv_file:
            return list(csv.DictReader(csv_file))
    except OSError:
        return []


def write_project_summary(output_dir, git_commit):
    content = """# Project Summary

This project implements a mapless TurtleBot3 Waffle Pi wireless charging approach.

System sequence:

1. UWB estimates robot pose and provides charger target coordinates.
2. LiDAR local planner drives toward the target while avoiding nearby obstacles.
3. The robot stops approximately 1 m before the charger target.
4. Vision and UWB docking can take over for final alignment.

Code version:

```text
{}
```
""".format(git_commit)
    write_text(os.path.join(output_dir, "project_summary.md"), content)


def write_system_architecture(output_dir):
    content = """# System Architecture

ROS topics:

- `/uwb/ranges`: raw UWB ranges.
- `/uwb_pose`: estimated robot pose in the UWB coordinate frame.
- `/target_charger`: selected charger coordinate.
- `/scan`: LiDAR scan.
- `/cmd_vel`: velocity command.
- `/lidar_state`: local planner state.
- `/near_charger`: handoff flag for final docking.
- `/uwb_path`, `/uwb_markers`: RViz visualization.
"""
    write_text(os.path.join(output_dir, "system_architecture.md"), content)


def write_algorithm_description(output_dir):
    content = """# Algorithm Description

The UWB pose estimator applies anchor bias correction, range jump rejection, residual-based outlier rejection, pose jump rejection, and smoothing.

The LiDAR local planner divides LaserScan data into front, front-left, front-right, left, and right sectors. It drives toward the UWB target when the front sector is clear, turns toward the side with more free space when an obstacle is detected, and stops when the target is within `goal_radius`.
"""
    write_text(os.path.join(output_dir, "algorithm_description.md"), content)


def write_experiment_table(output_dir, summaries):
    path = os.path.join(output_dir, "experiment_table.csv")
    fieldnames = ["file", "rows", "start_time", "end_time", "columns"]
    with open(path, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            writer.writerow({
                "file": summary["file"],
                "rows": summary["rows"],
                "start_time": summary["start_time"],
                "end_time": summary["end_time"],
                "columns": ";".join(summary["columns"]),
            })


def write_summary_metrics(output_dir, summaries):
    path = os.path.join(output_dir, "summary_metrics.csv")
    fieldnames = [
        "file",
        "rows",
        "uwb_x_std",
        "uwb_y_std",
        "uwb_error_mean",
        "near_charger_count",
        "lidar_states",
    ]
    with open(path, "w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for summary in summaries:
            writer.writerow({name: summary.get(name, "") for name in fieldnames})


def write_failure_cases(output_dir):
    content = """# Failure Cases

Fill this after each experiment.

- UWB pose timeout:
- LiDAR stale input:
- Obstacle avoidance failure:
- Stop radius error:
- RViz/path discrepancy:
"""
    write_text(os.path.join(output_dir, "failure_cases.md"), content)


def write_ai_prompt(output_dir):
    content = """# AI Writing Prompt

Use the files in this evidence pack to draft a project report or paper.

Rules:

- Do not invent numerical results.
- Cite metrics only from `summary_metrics.csv` or provided figures.
- Mention the code commit from `code_version.txt`.
- Clearly separate completed work from future work.
- Explain limitations: no global map, local obstacle avoidance only, U-shaped obstacles are not guaranteed.
"""
    write_text(os.path.join(output_dir, "ai_writing_prompt.md"), content)


def write_code_version(output_dir, git_commit):
    write_text(os.path.join(output_dir, "code_version.txt"), git_commit + "\n")


def copy_configs(output_dir):
    config_dir = os.path.join(output_dir, "config")
    os.makedirs(config_dir, exist_ok=True)
    for path in glob.glob(os.path.join("config", "*.yaml")):
        shutil.copy2(path, os.path.join(config_dir, os.path.basename(path)))


def get_git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def write_text(path, content):
    with open(path, "w", encoding="utf-8") as output:
        output.write(content)


def has_columns(row, columns):
    return all(column in row for column in columns)


def valid_column(rows, column):
    values = [as_float(row.get(column)) for row in rows]
    return [value for value in values if value is not None]


def as_float(value):
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def mean(values):
    return sum(values) / len(values) if values else None


def stdev(values):
    if len(values) < 2:
        return None
    value_mean = mean(values)
    variance = sum((value - value_mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance)


def fmt(value):
    return "" if value is None else "{:.4f}".format(value)


def normalize_path(path):
    return path.replace(os.sep, "/")


if __name__ == "__main__":
    main()
