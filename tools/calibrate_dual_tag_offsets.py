#!/usr/bin/env python3

import argparse
import math
import statistics
import time

import serial


ANCHORS = [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0)]


def parse_dist(line, tag_id):
    prefix = "DIST,{},".format(tag_id)
    if not line.startswith(prefix):
        return None
    parts = line.split(",")
    if len(parts) != 5 or parts[2] == "FAIL":
        return None
    try:
        return [float(parts[2]), float(parts[3]), float(parts[4])]
    except ValueError:
        return None


def collect(port, tag_id, baud, valid_samples, timeout):
    ser = serial.Serial(port, baud, timeout=0.2)
    time.sleep(1.0)
    samples = []
    deadline = time.time() + timeout
    try:
        while time.time() < deadline and len(samples) < valid_samples:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            values = parse_dist(line, tag_id)
            if values is not None:
                samples.append(values)
    finally:
        ser.close()
    return samples


def median_vector(samples):
    return [statistics.median(row[i] for row in samples) for i in range(3)]


def expected_distances(point, height_diff):
    out = []
    for ax, ay in ANCHORS:
        horizontal = math.hypot(point[0] - ax, point[1] - ay)
        out.append(math.sqrt(horizontal * horizontal + height_diff * height_diff))
    return out


def fmt(values):
    return "[" + ", ".join("{:.6f}".format(v) for v in values) + "]"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag1-port", default="/dev/ttyUSB1")
    parser.add_argument("--tag2-port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--center-x", type=float, default=2.5)
    parser.add_argument("--center-y", type=float, default=2.5)
    parser.add_argument("--theta", type=float, default=-math.pi / 2.0)
    parser.add_argument("--tag-distance", type=float, default=0.172)
    parser.add_argument("--height-diff", type=float, default=0.72)
    parser.add_argument("--valid-samples", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--tag2-is-front", action="store_true")
    args = parser.parse_args()

    half = args.tag_distance / 2.0
    forward = (math.cos(args.theta), math.sin(args.theta))
    front = (args.center_x + half * forward[0], args.center_y + half * forward[1])
    back = (args.center_x - half * forward[0], args.center_y - half * forward[1])

    tag1_point = back if args.tag2_is_front else front
    tag2_point = front if args.tag2_is_front else back

    tag1_samples = collect(args.tag1_port, 1, args.baud, args.valid_samples, args.timeout)
    tag2_samples = collect(args.tag2_port, 2, args.baud, args.valid_samples, args.timeout)

    print("tag1_samples={}".format(len(tag1_samples)))
    print("tag2_samples={}".format(len(tag2_samples)))
    if len(tag1_samples) < 3 or len(tag2_samples) < 3:
        raise SystemExit("Not enough valid samples to calibrate.")

    tag1_median = median_vector(tag1_samples)
    tag2_median = median_vector(tag2_samples)
    tag1_expected = expected_distances(tag1_point, args.height_diff)
    tag2_expected = expected_distances(tag2_point, args.height_diff)

    tag1_offset = [e - m for e, m in zip(tag1_expected, tag1_median)]
    tag2_offset = [e - m for e, m in zip(tag2_expected, tag2_median)]

    print("tag1_point={}".format(fmt(tag1_point)))
    print("tag2_point={}".format(fmt(tag2_point)))
    print("tag1_median={}".format(fmt(tag1_median)))
    print("tag2_median={}".format(fmt(tag2_median)))
    print("tag1_expected={}".format(fmt(tag1_expected)))
    print("tag2_expected={}".format(fmt(tag2_expected)))
    print("tag1_offset={}".format(fmt(tag1_offset)))
    print("tag2_offset={}".format(fmt(tag2_offset)))
    print("")
    print("roslaunch args:")
    print('tag1_offset:="{}" tag2_offset:="{}"'.format(fmt(tag1_offset), fmt(tag2_offset)))


if __name__ == "__main__":
    main()
