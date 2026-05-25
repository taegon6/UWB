import argparse
import csv
import json
import math
import os
import time
from collections import deque
from datetime import datetime

import numpy as np
import serial
from scipy.optimize import least_squares


# =======================================================
# 1. Environment
# =======================================================
PORT_TAG1 = "COM7"  # TAG1 = Back
PORT_TAG2 = "COM5"  # TAG2 = Front
BAUD_RATE = 115200

anchors = np.array([
    [0.0, 0.0],  # Anchor A
    [5.0, 0.0],  # Anchor B
    [0.0, 5.0],  # Anchor C
])

HEIGHT_DIFF = 0.42
TAG_DISTANCE = 0.15
B = TAG_DISTANCE / 2.0

ROOM_MIN_X = 0.0
ROOM_MAX_X = 5.0
ROOM_MIN_Y = 0.0
ROOM_MAX_Y = 5.0

REFERENCE_CENTER = np.array([2.5, 2.5])
REFERENCE_HEADING_DEG = -90.0
active_reference_center = REFERENCE_CENTER.copy()
active_reference_heading_deg = REFERENCE_HEADING_DEG

# Current physical setup: TAG2 is robot front, TAG1 is robot back.
TAG2_IS_FRONT = True

# Fallback offsets from the last stable center calibration at
# x=2.5, y=2.5, heading=-90 deg.
TAG1_OFFSET = np.array([0.593, -0.592, 0.628])
TAG2_OFFSET = np.array([0.608, 0.623, 0.133])


# =======================================================
# 2. Runtime tuning
# =======================================================
CALIBRATION_TARGET_SAMPLES = 30
CALIBRATION_TIMEOUT = 90.0
CALIBRATION_MIN_SAMPLES = 12
CALIBRATION_MAX_ANCHOR_STD = 0.35
CALIBRATION_MAX_MEDIAN_DEVIATION = 0.45
MIN_VALID_DIST = 0.5
MAX_VALID_DIST = 10.5

PAIR_TIMEOUT = 2.5
MAX_TAG_DT = 1.0
CYCLE_DELAY = 0.02

MAX_COST = 0.06
MAX_HEADING_JUMP_DEG = 75.0
HEADING_ALPHA = 0.25
POSITION_ALPHA = 0.35

STABILITY_WINDOW = 25
STABLE_POS_STD_M = 0.12
STABLE_HEADING_STD_DEG = 18.0
STABLE_MEAN_COST = 0.035

VALIDATION_POINTS = [
    (1.0, 1.0),
    (4.0, 1.0),
    (4.0, 4.0),
    (1.0, 4.0),
    (2.5, 2.5),
]

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_FILE = os.path.join(LOG_DIR, "uwb_calibration.json")
LOG_FILE = os.path.join(
    LOG_DIR,
    f"uwb_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
)


# =======================================================
# 3. State
# =======================================================
last_pose = np.array([
    active_reference_center[0],
    active_reference_center[1],
    math.radians(active_reference_heading_deg),
])
last_valid_heading = None
filtered_heading = None
filtered_center = None
recent_results = deque(maxlen=STABILITY_WINDOW)
validation_index = 0
heading_output_offset_deg = 0.0


# =======================================================
# 4. Math utilities
# =======================================================
def normalize_angle_rad(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def normalize_angle_deg(angle):
    return (angle + 180.0) % 360.0 - 180.0


def angle_diff_deg(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def distance_2d(p1, p2):
    return float(np.linalg.norm(np.array(p1, dtype=float) - np.array(p2, dtype=float)))


def compensate_height(d_3d):
    if d_3d > HEIGHT_DIFF:
        return math.sqrt(d_3d ** 2 - HEIGHT_DIFF ** 2)
    return 0.0


def compensate_distances(corrected_3d):
    return np.array([compensate_height(d) for d in corrected_3d], dtype=float)


def expected_3d_distances(point_2d):
    point = np.array(point_2d, dtype=float)
    horizontal = np.linalg.norm(anchors - point, axis=1)
    return np.sqrt(horizontal ** 2 + HEIGHT_DIFF ** 2)


def reference_tag_positions():
    theta = math.radians(active_reference_heading_deg)
    u = np.array([math.cos(theta), math.sin(theta)])
    front = active_reference_center + B * u
    back = active_reference_center - B * u
    return front, back


# =======================================================
# 5. Serial parsing and filtering
# =======================================================
def is_valid_distance_set(distances):
    if distances is None or len(distances) != 3:
        return False
    for d in distances:
        if not math.isfinite(d):
            return False
        if d < MIN_VALID_DIST or d > MAX_VALID_DIST:
            return False
    return True


def parse_distance_line(line, tag_id):
    prefix = f"DIST,{tag_id}"
    if not line.startswith(prefix):
        return None

    parts = line.split(",")
    if len(parts) != 5:
        return None

    try:
        distances = [float(parts[2]), float(parts[3]), float(parts[4])]
    except ValueError:
        return None

    if not is_valid_distance_set(distances):
        print(f"[DROP] TAG{tag_id} invalid raw distance: {distances}")
        return None

    return distances


def read_one_tag(ser, tag_id):
    while ser.in_waiting > 0:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        parsed = parse_distance_line(line, tag_id)
        if parsed is not None:
            return parsed, time.time()
    return None, None


class MedianDistanceFilter:
    def __init__(self, window=7, max_jump=0.8):
        self.window = window
        self.max_jump = max_jump
        self.buffers = {}

    def filter(self, tag_id, distances):
        out = []
        for anchor_idx, d in enumerate(distances):
            key = (tag_id, anchor_idx)
            self.buffers.setdefault(key, deque(maxlen=self.window))
            buf = self.buffers[key]

            if len(buf) >= 3:
                med = float(np.median(buf))
                if abs(d - med) > self.max_jump:
                    out.append(med)
                    continue

            buf.append(d)
            out.append(d)

        return out


# =======================================================
# 6. Startup calibration
# =======================================================
def collect_calibration_samples(ser1, ser2, target, timeout):
    samples = {1: [], 2: []}
    dropped = {1: 0, 2: 0}
    start = time.time()

    print("=" * 76)
    print(
        f"[CAL] Put robot at x={active_reference_center[0]:.2f}, "
        f"y={active_reference_center[1]:.2f}, "
        f"heading={active_reference_heading_deg:.2f} deg and keep it still."
    )
    print(f"[CAL] Collecting {target} valid samples per tag...")
    print("=" * 76)

    while time.time() - start < timeout:
        for ser, tag_id in ((ser1, 1), (ser2, 2)):
            if len(samples[tag_id]) >= target:
                continue

            while ser.in_waiting > 0 and len(samples[tag_id]) < target:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                prefix = f"DIST,{tag_id}"
                if not line.startswith(prefix):
                    continue

                parts = line.split(",")
                if len(parts) != 5:
                    continue

                try:
                    distances = [float(parts[2]), float(parts[3]), float(parts[4])]
                except ValueError:
                    continue

                if not is_valid_distance_set(distances):
                    dropped[tag_id] += 1
                    print(f"[CAL DROP] TAG{tag_id}: {distances}")
                    continue

                samples[tag_id].append(distances)
                n1 = len(samples[1])
                n2 = len(samples[2])
                print(f"[CAL] TAG1 {n1:02d}/{target} | TAG2 {n2:02d}/{target}", end="\r")

        if len(samples[1]) >= target and len(samples[2]) >= target:
            print()
            break

        time.sleep(0.005)

    print()
    print(f"[CAL] Dropped outliers: TAG1={dropped[1]}, TAG2={dropped[2]}")
    return np.array(samples[1], dtype=float), np.array(samples[2], dtype=float)


def robust_calibration_samples(samples, tag_id):
    if len(samples) == 0:
        return samples

    median = np.median(samples, axis=0)
    deviation = np.abs(samples - median)
    keep = np.all(deviation <= CALIBRATION_MAX_MEDIAN_DEVIATION, axis=1)
    trimmed = samples[keep]

    if len(trimmed) < CALIBRATION_MIN_SAMPLES:
        print(
            f"[CAL WARN] TAG{tag_id} robust trim left only {len(trimmed)} samples; "
            "using per-anchor median from all samples"
        )
        return samples

    std = np.std(trimmed, axis=0)
    if np.any(std > CALIBRATION_MAX_ANCHOR_STD):
        print(
            f"[CAL WARN] TAG{tag_id} still noisy after trim: "
            f"std=[{std[0]:.3f}, {std[1]:.3f}, {std[2]:.3f}]"
        )

    dropped = len(samples) - len(trimmed)
    print(f"[CAL] TAG{tag_id} robust samples: kept={len(trimmed)}, dropped={dropped}")
    return trimmed


def calculate_offsets(tag1_samples, tag2_samples):
    if len(tag1_samples) == 0 or len(tag2_samples) == 0:
        raise RuntimeError("calibration failed: no valid samples from one or both tags")

    tag1_samples = robust_calibration_samples(tag1_samples, 1)
    tag2_samples = robust_calibration_samples(tag2_samples, 2)

    front_pos, back_pos = reference_tag_positions()
    tag1_pos = back_pos
    tag2_pos = front_pos

    tag1_expected = expected_3d_distances(tag1_pos)
    tag2_expected = expected_3d_distances(tag2_pos)

    tag1_mean = np.median(tag1_samples, axis=0)
    tag2_mean = np.median(tag2_samples, axis=0)
    tag1_std = np.std(tag1_samples, axis=0)
    tag2_std = np.std(tag2_samples, axis=0)

    tag1_offset = tag1_expected - tag1_mean
    tag2_offset = tag2_expected - tag2_mean

    print("=" * 76)
    print("[CAL RESULT]")
    print(f"TAG1 raw median: [{tag1_mean[0]:.3f}, {tag1_mean[1]:.3f}, {tag1_mean[2]:.3f}]")
    print(f"TAG1 raw std   : [{tag1_std[0]:.3f}, {tag1_std[1]:.3f}, {tag1_std[2]:.3f}]")
    print(f"TAG1 offset    : [{tag1_offset[0]:+.3f}, {tag1_offset[1]:+.3f}, {tag1_offset[2]:+.3f}]")
    print(f"TAG2 raw median: [{tag2_mean[0]:.3f}, {tag2_mean[1]:.3f}, {tag2_mean[2]:.3f}]")
    print(f"TAG2 raw std   : [{tag2_std[0]:.3f}, {tag2_std[1]:.3f}, {tag2_std[2]:.3f}]")
    print(f"TAG2 offset    : [{tag2_offset[0]:+.3f}, {tag2_offset[1]:+.3f}, {tag2_offset[2]:+.3f}]")
    print("=" * 76)

    return tag1_offset, tag2_offset


def save_calibration(tag1_offset, tag2_offset):
    payload = {
        "saved_at": datetime.now().isoformat(),
        "reference_center": [
            float(active_reference_center[0]),
            float(active_reference_center[1]),
        ],
        "reference_heading_deg": float(active_reference_heading_deg),
        "tag1_offset": [float(x) for x in tag1_offset],
        "tag2_offset": [float(x) for x in tag2_offset],
    }
    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[CAL] saved: {CALIBRATION_FILE}")


def load_calibration():
    if not os.path.exists(CALIBRATION_FILE):
        print("[CAL] saved calibration not found; using built-in fallback offsets")
        return TAG1_OFFSET.copy(), TAG2_OFFSET.copy()

    with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    tag1_offset = np.array(payload["tag1_offset"], dtype=float)
    tag2_offset = np.array(payload["tag2_offset"], dtype=float)
    ref_center = payload.get("reference_center", ["?", "?"])
    ref_heading = payload.get("reference_heading_deg", "?")

    print(f"[CAL] loaded: {CALIBRATION_FILE}")
    print(f"[CAL] source reference center={ref_center}, heading={ref_heading}")
    return tag1_offset, tag2_offset


# =======================================================
# 7. Pose estimation
# =======================================================
def apply_offsets(raw_distances, offset):
    return np.array(raw_distances, dtype=float) + np.array(offset, dtype=float)


def rigid_body_error(params, dist_front_corrected, dist_back_corrected):
    cx, cy, theta = params
    center = np.array([cx, cy])
    u = np.array([math.cos(theta), math.sin(theta)])

    pos_front = center + B * u
    pos_back = center - B * u

    measured_front = compensate_distances(dist_front_corrected)
    measured_back = compensate_distances(dist_back_corrected)

    calculated_front = np.linalg.norm(anchors - pos_front, axis=1)
    calculated_back = np.linalg.norm(anchors - pos_back, axis=1)

    return np.concatenate([
        calculated_front - measured_front,
        calculated_back - measured_back,
    ])


def best_initial_guess(dist_front_corrected, dist_back_corrected, center_hint):
    best = np.array([center_hint[0], center_hint[1], math.radians(active_reference_heading_deg)])
    best_cost = float("inf")

    for deg in range(-180, 180, 10):
        guess = np.array([center_hint[0], center_hint[1], math.radians(deg)])
        cost = float(np.sum(rigid_body_error(guess, dist_front_corrected, dist_back_corrected) ** 2))
        if cost < best_cost:
            best_cost = cost
            best = guess

    return best


def calculate_pose(dist_tag1_raw, dist_tag2_raw, tag1_offset, tag2_offset):
    global last_pose

    tag1_corrected = apply_offsets(dist_tag1_raw, tag1_offset)
    tag2_corrected = apply_offsets(dist_tag2_raw, tag2_offset)

    if TAG2_IS_FRONT:
        dist_front = tag2_corrected
        dist_back = tag1_corrected
    else:
        dist_front = tag1_corrected
        dist_back = tag2_corrected

    initial_guess = last_pose.copy()

    result = least_squares(
        rigid_body_error,
        initial_guess,
        args=(dist_front, dist_back),
        bounds=(
            [ROOM_MIN_X, ROOM_MIN_Y, -math.pi],
            [ROOM_MAX_X, ROOM_MAX_Y, math.pi],
        ),
        loss="soft_l1",
        f_scale=0.1,
        max_nfev=100,
    )

    if result.cost > MAX_COST:
        global_guess = best_initial_guess(dist_front, dist_back, result.x[:2])
        retry = least_squares(
            rigid_body_error,
            global_guess,
            args=(dist_front, dist_back),
            bounds=(
                [ROOM_MIN_X, ROOM_MIN_Y, -math.pi],
                [ROOM_MAX_X, ROOM_MAX_Y, math.pi],
            ),
            loss="soft_l1",
            f_scale=0.1,
            max_nfev=100,
        )
        if retry.cost < result.cost:
            result = retry

    cx, cy, theta = result.x
    theta = normalize_angle_rad(theta)
    last_pose = np.array([cx, cy, theta])

    center = np.array([cx, cy])
    u = np.array([math.cos(theta), math.sin(theta)])
    pos_front = center + B * u
    pos_back = center - B * u
    heading_deg = normalize_angle_deg(math.degrees(theta))

    return center, pos_front, pos_back, heading_deg, result.cost, tag1_corrected, tag2_corrected


def filter_pose(center, heading_raw):
    global filtered_center, filtered_heading, last_valid_heading

    if filtered_center is None:
        filtered_center = np.array(center, dtype=float)
    else:
        filtered_center = filtered_center + POSITION_ALPHA * (np.array(center) - filtered_center)

    if filtered_heading is None:
        filtered_heading = heading_raw
    else:
        diff = angle_diff_deg(heading_raw, filtered_heading)
        filtered_heading = normalize_angle_deg(filtered_heading + HEADING_ALPHA * diff)

    last_valid_heading = filtered_heading
    return filtered_center.copy(), filtered_heading


def align_heading_for_output(heading_raw):
    return normalize_angle_deg(heading_raw + heading_output_offset_deg)


def calculate_start_heading_offset(tag1_samples, tag2_samples, tag1_offset, tag2_offset):
    global last_pose

    last_pose = np.array([
        active_reference_center[0],
        active_reference_center[1],
        math.radians(active_reference_heading_deg),
    ])

    tag1_median = np.median(tag1_samples, axis=0)
    tag2_median = np.median(tag2_samples, axis=0)
    center, _, _, heading_raw, cost, _, _ = calculate_pose(
        tag1_median,
        tag2_median,
        tag1_offset,
        tag2_offset,
    )
    offset = normalize_angle_deg(active_reference_heading_deg - heading_raw)

    print("=" * 76)
    print("[HEADING ALIGN]")
    print(f"reference heading : {active_reference_heading_deg:8.2f} deg")
    print(f"UWB raw heading   : {heading_raw:8.2f} deg")
    print(f"output offset     : {offset:+8.2f} deg")
    print(f"cal pose center   : x={center[0]:.3f} m, y={center[1]:.3f} m, cost={cost:.6f}")
    print("=" * 76)

    return offset


# =======================================================
# 8. Runtime output and validation guidance
# =======================================================
def print_pose_result(cycle, center, center_filt, pos_front, pos_back, heading_raw,
                      heading_filt, dt, cost, tag1_corr, tag2_corr):
    tag_distance_est = distance_2d(pos_front, pos_back)

    print()
    print("-" * 76)
    print(f"Cycle {cycle:05d}")
    print(f"중심좌표 C        :  x = {center_filt[0]:7.3f} m    y = {center_filt[1]:7.3f} m")
    print(f"각도 Filtered     :  {heading_filt:8.2f} deg")
    print(f"각도 Raw          :  {heading_raw:8.2f} deg")
    print(f"앞 태그 Front     :  x = {pos_front[0]:7.3f} m    y = {pos_front[1]:7.3f} m")
    print(f"뒤 태그 Back      :  x = {pos_back[0]:7.3f} m    y = {pos_back[1]:7.3f} m")
    print(f"태그 간 거리      :  {tag_distance_est:7.3f} m")
    print(f"TAG1-TAG2 dt      :  {dt * 1000:7.1f} ms")
    print(f"least cost        :  {cost:10.6f}")
    print(f"TAG1 corrected    :  [{tag1_corr[0]:.3f}, {tag1_corr[1]:.3f}, {tag1_corr[2]:.3f}] m")
    print(f"TAG2 corrected    :  [{tag2_corr[0]:.3f}, {tag2_corr[1]:.3f}, {tag2_corr[2]:.3f}] m")
    print("-" * 76)


def circular_std_deg(values):
    if len(values) == 0:
        return float("inf")
    radians = np.radians(values)
    mean_sin = np.mean(np.sin(radians))
    mean_cos = np.mean(np.cos(radians))
    r = math.sqrt(mean_sin ** 2 + mean_cos ** 2)
    if r <= 0.0:
        return 180.0
    return math.degrees(math.sqrt(max(0.0, -2.0 * math.log(r))))


def update_stability(center_filt, heading_filt, cost):
    global validation_index

    recent_results.append((float(center_filt[0]), float(center_filt[1]), heading_filt, cost))
    if len(recent_results) < STABILITY_WINDOW:
        return

    arr = np.array(recent_results, dtype=float)
    pos_std = float(np.mean(np.std(arr[:, :2], axis=0)))
    heading_std = circular_std_deg(arr[:, 2])
    mean_cost = float(np.mean(arr[:, 3]))

    if pos_std <= STABLE_POS_STD_M and heading_std <= STABLE_HEADING_STD_DEG and mean_cost <= STABLE_MEAN_COST:
        if validation_index < len(VALIDATION_POINTS):
            x, y = VALIDATION_POINTS[validation_index]
            print()
            print("=" * 76)
            print("[STABLE] 현재 위치 추정이 충분히 안정적입니다.")
            print(f"[MOVE] 이제 로봇을 ({x:.1f}, {y:.1f}) 지점으로 옮기고 잠시 정지시켜 주세요.")
            print(f"[STAT] pos_std={pos_std:.3f} m, heading_std={heading_std:.2f} deg, mean_cost={mean_cost:.5f}")
            print("=" * 76)
            validation_index += 1
            recent_results.clear()


def wait_distance_pair(ser1, ser2):
    latest1 = None
    latest2 = None
    t1 = None
    t2 = None
    start = time.time()

    while time.time() - start < PAIR_TIMEOUT:
        p1, nt1 = read_one_tag(ser1, 1)
        if p1 is not None:
            latest1 = p1
            t1 = nt1

        p2, nt2 = read_one_tag(ser2, 2)
        if p2 is not None:
            latest2 = p2
            t2 = nt2

        if latest1 is not None and latest2 is not None:
            dt = abs(t2 - t1)
            return latest1, latest2, dt

        time.sleep(0.002)

    return None, None, None


# =======================================================
# 9. Main loop
# =======================================================
def run(args):
    global TAG1_OFFSET, TAG2_OFFSET, heading_output_offset_deg
    global active_reference_center, active_reference_heading_deg, last_pose

    active_reference_center = np.array([args.reference_x, args.reference_y], dtype=float)
    active_reference_heading_deg = normalize_angle_deg(args.reference_heading)
    last_pose = np.array([
        active_reference_center[0],
        active_reference_center[1],
        math.radians(active_reference_heading_deg),
    ])

    ser1 = None
    ser2 = None
    csv_file = None

    try:
        ser1 = serial.Serial(args.port_tag1, BAUD_RATE, timeout=0.1)
        ser2 = serial.Serial(args.port_tag2, BAUD_RATE, timeout=0.1)
        time.sleep(1.0)
        ser1.reset_input_buffer()
        ser2.reset_input_buffer()
        print(f"[OK] Serial connected: TAG1={args.port_tag1}, TAG2={args.port_tag2}")
    except Exception as exc:
        print(f"[ERROR] serial open failed: {exc}")
        return 1

    try:
        if args.skip_calibration:
            print("[CAL] skipped; using saved/fallback offsets")
            TAG1_OFFSET, TAG2_OFFSET = load_calibration()
            heading_output_offset_deg = 0.0
        else:
            tag1_samples, tag2_samples = collect_calibration_samples(
                ser1,
                ser2,
                args.calibration_samples,
                args.calibration_timeout,
            )
            if len(tag1_samples) < max(5, args.calibration_samples // 2):
                raise RuntimeError(f"not enough TAG1 samples: {len(tag1_samples)}")
            if len(tag2_samples) < max(5, args.calibration_samples // 2):
                raise RuntimeError(f"not enough TAG2 samples: {len(tag2_samples)}")
            TAG1_OFFSET, TAG2_OFFSET = calculate_offsets(tag1_samples, tag2_samples)
            save_calibration(TAG1_OFFSET, TAG2_OFFSET)
            heading_output_offset_deg = calculate_start_heading_offset(
                tag1_samples,
                tag2_samples,
                TAG1_OFFSET,
                TAG2_OFFSET,
            )

        csv_file = open(LOG_FILE, "w", newline="", encoding="utf-8")
        writer = csv.writer(csv_file)
        writer.writerow([
            "time",
            "cycle",
            "cx_raw",
            "cy_raw",
            "cx_filtered",
            "cy_filtered",
            "heading_raw",
            "heading_filtered",
            "front_x",
            "front_y",
            "back_x",
            "back_y",
            "dt_ms",
            "cost",
            "tag1_raw_a",
            "tag1_raw_b",
            "tag1_raw_c",
            "tag2_raw_a",
            "tag2_raw_b",
            "tag2_raw_c",
            "tag1_filtered_a",
            "tag1_filtered_b",
            "tag1_filtered_c",
            "tag2_filtered_a",
            "tag2_filtered_b",
            "tag2_filtered_c",
            "tag1_corrected_a",
            "tag1_corrected_b",
            "tag1_corrected_c",
            "tag2_corrected_a",
            "tag2_corrected_b",
            "tag2_corrected_c",
        ])
        csv_file.flush()

        filt = MedianDistanceFilter()
        start = time.time()
        cycle = 0

        print("=" * 76)
        print("[START] Real-time UWB pose estimation")
        print(f"[LOG] {LOG_FILE}")
        print(f"[OFFSET] TAG1 = [{TAG1_OFFSET[0]:+.3f}, {TAG1_OFFSET[1]:+.3f}, {TAG1_OFFSET[2]:+.3f}]")
        print(f"[OFFSET] TAG2 = [{TAG2_OFFSET[0]:+.3f}, {TAG2_OFFSET[1]:+.3f}, {TAG2_OFFSET[2]:+.3f}]")
        print(f"[REFERENCE] center=({active_reference_center[0]:.2f}, {active_reference_center[1]:.2f}), heading={active_reference_heading_deg:.2f} deg")
        print(f"[HEADING] output offset = {heading_output_offset_deg:+.2f} deg")
        print("[INFO] Ctrl+C to stop")
        print("=" * 76)

        while True:
            if args.duration > 0 and time.time() - start >= args.duration:
                print("[DONE] duration reached")
                break

            dist_tag1, dist_tag2, dt = wait_distance_pair(ser1, ser2)
            cycle += 1

            if dist_tag1 is None or dist_tag2 is None:
                print(f"[Cycle {cycle:05d}] pair timeout")
                continue

            if dt > MAX_TAG_DT:
                print(f"[Cycle {cycle:05d}] time gap rejected | dt={dt * 1000:.1f} ms")
                continue

            dist_tag1_raw = list(dist_tag1)
            dist_tag2_raw = list(dist_tag2)
            dist_tag1 = filt.filter(1, dist_tag1)
            dist_tag2 = filt.filter(2, dist_tag2)

            center, pos_front, pos_back, heading_raw, cost, tag1_corr, tag2_corr = calculate_pose(
                dist_tag1,
                dist_tag2,
                TAG1_OFFSET,
                TAG2_OFFSET,
            )

            if cost > MAX_COST:
                print(f"[Cycle {cycle:05d}] cost rejected | cost={cost:.6f}")
                continue

            heading_output = align_heading_for_output(heading_raw)

            if last_valid_heading is not None:
                jump = abs(angle_diff_deg(heading_output, last_valid_heading))
                if jump > MAX_HEADING_JUMP_DEG:
                    print(f"[Cycle {cycle:05d}] heading jump rejected | jump={jump:.2f} deg, raw={heading_output:.2f} deg")
                    continue

            center_filt, heading_filt = filter_pose(center, heading_output)

            print_pose_result(
                cycle,
                center,
                center_filt,
                pos_front,
                pos_back,
                heading_output,
                heading_filt,
                dt,
                cost,
                tag1_corr,
                tag2_corr,
            )

            writer.writerow([
                datetime.now().isoformat(),
                cycle,
                f"{center[0]:.4f}",
                f"{center[1]:.4f}",
                f"{center_filt[0]:.4f}",
                f"{center_filt[1]:.4f}",
                f"{heading_output:.2f}",
                f"{heading_filt:.2f}",
                f"{pos_front[0]:.4f}",
                f"{pos_front[1]:.4f}",
                f"{pos_back[0]:.4f}",
                f"{pos_back[1]:.4f}",
                f"{dt * 1000:.1f}",
                f"{cost:.6f}",
                f"{dist_tag1_raw[0]:.4f}",
                f"{dist_tag1_raw[1]:.4f}",
                f"{dist_tag1_raw[2]:.4f}",
                f"{dist_tag2_raw[0]:.4f}",
                f"{dist_tag2_raw[1]:.4f}",
                f"{dist_tag2_raw[2]:.4f}",
                f"{dist_tag1[0]:.4f}",
                f"{dist_tag1[1]:.4f}",
                f"{dist_tag1[2]:.4f}",
                f"{dist_tag2[0]:.4f}",
                f"{dist_tag2[1]:.4f}",
                f"{dist_tag2[2]:.4f}",
                f"{tag1_corr[0]:.4f}",
                f"{tag1_corr[1]:.4f}",
                f"{tag1_corr[2]:.4f}",
                f"{tag2_corr[0]:.4f}",
                f"{tag2_corr[1]:.4f}",
                f"{tag2_corr[2]:.4f}",
            ])
            csv_file.flush()

            update_stability(center_filt, heading_filt, cost)
            time.sleep(CYCLE_DELAY)

    except KeyboardInterrupt:
        print("\n[STOP] interrupted")
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        return 1
    finally:
        if csv_file is not None:
            csv_file.close()
        if ser1 is not None and ser1.is_open:
            ser1.close()
        if ser2 is not None and ser2.is_open:
            ser2.close()
        print("[DONE] serial ports closed")

    return 0


def self_test():
    global active_reference_center, active_reference_heading_deg, last_pose

    active_reference_center = REFERENCE_CENTER.copy()
    active_reference_heading_deg = REFERENCE_HEADING_DEG
    last_pose = np.array([
        active_reference_center[0],
        active_reference_center[1],
        math.radians(active_reference_heading_deg),
    ])

    front, back = reference_tag_positions()
    tag1_raw = expected_3d_distances(back) - TAG1_OFFSET
    tag2_raw = expected_3d_distances(front) - TAG2_OFFSET

    center, _, _, heading, cost, _, _ = calculate_pose(
        tag1_raw,
        tag2_raw,
        TAG1_OFFSET,
        TAG2_OFFSET,
    )
    err = distance_2d(center, active_reference_center)
    heading_err = abs(angle_diff_deg(heading, active_reference_heading_deg))

    print(f"self-test center=({center[0]:.4f}, {center[1]:.4f}) err={err:.4f} m")
    print(f"self-test heading={heading:.2f} deg err={heading_err:.2f} deg cost={cost:.6f}")

    if err > 0.02 or heading_err > 2.0 or cost > 0.001:
        raise SystemExit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="5x5 UWB pose estimator")
    parser.add_argument("--port-tag1", default=PORT_TAG1)
    parser.add_argument("--port-tag2", default=PORT_TAG2)
    parser.add_argument("--skip-calibration", action="store_true")
    parser.add_argument("--calibration-samples", type=int, default=CALIBRATION_TARGET_SAMPLES)
    parser.add_argument("--calibration-timeout", type=float, default=CALIBRATION_TIMEOUT)
    parser.add_argument("--duration", type=float, default=0.0, help="seconds; 0 means run forever")
    parser.add_argument("--reference-x", type=float, default=float(REFERENCE_CENTER[0]))
    parser.add_argument("--reference-y", type=float, default=float(REFERENCE_CENTER[1]))
    parser.add_argument("--reference-heading", type=float, default=REFERENCE_HEADING_DEG)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    parsed_args = parse_args()
    if parsed_args.self_test:
        self_test()
    else:
        raise SystemExit(run(parsed_args))
