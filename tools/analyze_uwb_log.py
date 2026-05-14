#!/usr/bin/env python3

import argparse
import csv
import math
import os
import statistics


DEFAULT_ANCHORS = [
    (0.0, 0.0),
    (5.0, 0.0),
    (0.0, 5.0),
    (5.0, 5.0),
]


def main():
    parser = argparse.ArgumentParser(description="Analyze UWB CSV logs and generate calibration YAML.")
    parser.add_argument("--input", required=True, help="Input CSV log path")
    parser.add_argument("--output", default="config/uwb_calibration.yaml", help="Output YAML path")
    parser.add_argument(
        "--anchors",
        default="0,0;5,0;0,5;5,5",
        help="Anchor coordinates as 'x,y;x,y;x,y;x,y'",
    )
    args = parser.parse_args()

    anchors = parse_anchors(args.anchors)
    rows = read_rows(args.input)
    if not rows:
        raise SystemExit("No rows found in {}".format(args.input))

    report = analyze(rows, anchors)
    write_yaml(args.output, report)
    print_report(args.input, args.output, report)


def parse_anchors(raw):
    anchors = []
    for item in raw.split(";"):
        x_str, y_str = item.split(",")
        anchors.append((float(x_str), float(y_str)))
    return anchors or DEFAULT_ANCHORS


def read_rows(path):
    with open(path, "r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        return [row for row in reader]


def analyze(rows, anchors):
    range_columns = find_range_columns(rows[0])
    true_available = has_columns(rows[0], ("true_x", "true_y"))
    uwb_available = has_columns(rows[0], ("uwb_x", "uwb_y"))
    filtered_available = has_columns(rows[0], ("cx_filtered", "cy_filtered"))
    raw_available = has_columns(rows[0], ("cx_raw", "cy_raw"))

    anchor_bias = [0.0 for _ in anchors]
    anchor_std = [0.0 for _ in anchors]

    if range_columns and true_available:
        anchor_bias, anchor_std = compute_anchor_bias(rows, anchors, range_columns)

    position_errors = []
    if true_available and uwb_available:
        position_errors = compute_position_errors(rows, "uwb_x", "uwb_y")
    elif true_available and filtered_available:
        position_errors = compute_position_errors(rows, "cx_filtered", "cy_filtered")

    pose_jump_samples = []
    if uwb_available:
        pose_jump_samples = compute_pose_jumps(rows, "uwb_x", "uwb_y")
    elif filtered_available:
        pose_jump_samples = compute_pose_jumps(rows, "cx_filtered", "cy_filtered")
    elif raw_available:
        pose_jump_samples = compute_pose_jumps(rows, "cx_raw", "cy_raw")

    range_jump_samples = compute_range_jumps(rows, range_columns)

    pos_std_x, pos_std_y = compute_position_std(rows)
    max_range_jump = robust_threshold(range_jump_samples, default=0.50, floor=0.25, ceiling=1.50)
    max_pose_jump = robust_threshold(pose_jump_samples, default=0.70, floor=0.25, ceiling=1.50)
    smoothing_alpha = recommend_smoothing_alpha(pos_std_x, pos_std_y)
    residual_threshold = max(0.25, min(1.00, 3.0 * max(anchor_std or [0.0] + [0.12])))

    return {
        "anchor_bias": anchor_bias,
        "anchor_std": anchor_std,
        "uwb_position_error_mean": mean(position_errors, 0.0),
        "uwb_position_error_std": stdev(position_errors, 0.0),
        "uwb_position_std": {"x": pos_std_x, "y": pos_std_y},
        "recommended_params": {
            "smoothing_alpha": smoothing_alpha,
            "max_range_jump": max_range_jump,
            "max_pose_jump": max_pose_jump,
            "residual_threshold": residual_threshold,
            "max_range": 20.0,
            "min_valid_anchors": 3,
        },
    }


def find_range_columns(row):
    columns = []
    index = 0
    while True:
        name = "range_a{}".format(index)
        if name not in row:
            break
        columns.append(name)
        index += 1
    return columns


def has_columns(row, columns):
    return all(column in row for column in columns)


def compute_anchor_bias(rows, anchors, range_columns):
    errors_by_anchor = [[] for _ in anchors]
    for row in rows:
        true_x = as_float(row.get("true_x"))
        true_y = as_float(row.get("true_y"))
        if true_x is None or true_y is None:
            continue

        for index, column in enumerate(range_columns):
            if index >= len(anchors):
                break
            measured = as_float(row.get(column))
            if measured is None:
                continue
            ax, ay = anchors[index]
            expected = math.hypot(true_x - ax, true_y - ay)
            errors_by_anchor[index].append(measured - expected)

    bias = [mean(values, 0.0) for values in errors_by_anchor]
    std = [stdev(values, 0.0) for values in errors_by_anchor]
    return bias, std


def compute_position_errors(rows, x_column, y_column):
    errors = []
    for row in rows:
        true_x = as_float(row.get("true_x"))
        true_y = as_float(row.get("true_y"))
        x_value = as_float(row.get(x_column))
        y_value = as_float(row.get(y_column))
        if None in (true_x, true_y, x_value, y_value):
            continue
        errors.append(math.hypot(x_value - true_x, y_value - true_y))
    return errors


def compute_pose_jumps(rows, x_column, y_column):
    jumps = []
    previous = None
    for row in rows:
        x_value = as_float(row.get(x_column))
        y_value = as_float(row.get(y_column))
        if x_value is None or y_value is None:
            continue
        current = (x_value, y_value)
        if previous is not None:
            jumps.append(math.hypot(current[0] - previous[0], current[1] - previous[1]))
        previous = current
    return jumps


def compute_range_jumps(rows, range_columns):
    jumps = []
    previous = {}
    for row in rows:
        for column in range_columns:
            value = as_float(row.get(column))
            if value is None:
                continue
            if column in previous:
                jumps.append(abs(value - previous[column]))
            previous[column] = value
    return jumps


def compute_position_std(rows):
    if has_columns(rows[0], ("uwb_x", "uwb_y")):
        return column_std(rows, "uwb_x"), column_std(rows, "uwb_y")
    if has_columns(rows[0], ("cx_filtered", "cy_filtered")):
        return column_std(rows, "cx_filtered"), column_std(rows, "cy_filtered")
    return 0.0, 0.0


def robust_threshold(samples, default, floor, ceiling):
    if len(samples) < 2:
        return default
    sorted_samples = sorted(samples)
    p95 = percentile(sorted_samples, 95.0)
    sigma = stdev(samples, 0.0)
    return clamp(max(p95, 3.0 * sigma), floor, ceiling)


def recommend_smoothing_alpha(std_x, std_y):
    noise = max(std_x, std_y)
    if noise >= 0.20:
        return 0.20
    if noise >= 0.12:
        return 0.25
    if noise >= 0.07:
        return 0.30
    return 0.35


def write_yaml(path, report):
    params = report["recommended_params"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as output:
        output.write("# Generated by tools/analyze_uwb_log.py\n")
        output.write("# Bias convention: measured_range - expected_range; estimator uses corrected = raw - bias.\n")
        output.write("anchor_bias: {}\n".format(format_list(report["anchor_bias"])))
        output.write("smoothing_alpha: {:.3f}\n".format(params["smoothing_alpha"]))
        output.write("max_range_jump: {:.3f}\n".format(params["max_range_jump"]))
        output.write("max_pose_jump: {:.3f}\n".format(params["max_pose_jump"]))
        output.write("residual_threshold: {:.3f}\n".format(params["residual_threshold"]))
        output.write("max_range: {:.3f}\n".format(params["max_range"]))
        output.write("min_valid_anchors: {}\n".format(params["min_valid_anchors"]))
        output.write("\n")
        output.write("analysis_summary:\n")
        output.write("  anchor_std: {}\n".format(format_list(report["anchor_std"])))
        output.write("  uwb_position_error_mean: {:.3f}\n".format(report["uwb_position_error_mean"]))
        output.write("  uwb_position_error_std: {:.3f}\n".format(report["uwb_position_error_std"]))
        output.write("  uwb_position_std:\n")
        output.write("    x: {:.3f}\n".format(report["uwb_position_std"]["x"]))
        output.write("    y: {:.3f}\n".format(report["uwb_position_std"]["y"]))


def print_report(input_path, output_path, report):
    print("Analyzed: {}".format(input_path))
    print("Wrote: {}".format(output_path))
    print("anchor_bias:", format_list(report["anchor_bias"]))
    print("recommended:", report["recommended_params"])


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


def column_std(rows, column):
    values = [as_float(row.get(column)) for row in rows]
    values = [value for value in values if value is not None]
    return stdev(values, 0.0)


def mean(values, default):
    return sum(values) / len(values) if values else default


def stdev(values, default):
    return statistics.stdev(values) if len(values) >= 2 else default


def percentile(sorted_values, pct):
    if not sorted_values:
        return 0.0
    index = (len(sorted_values) - 1) * pct / 100.0
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return sorted_values[lower]
    fraction = index - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def clamp(value, lower, upper):
    return max(lower, min(value, upper))


def format_list(values):
    return "[" + ", ".join("{:.3f}".format(value) for value in values) + "]"


if __name__ == "__main__":
    main()
