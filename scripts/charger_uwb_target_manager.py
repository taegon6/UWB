#!/usr/bin/env python3

import math
import os
import time
from datetime import datetime

import numpy as np
import rospy
import serial
from geometry_msgs.msg import Pose2D
from scipy.optimize import least_squares
from std_msgs.msg import Bool, String


class ChargerUwbTargetManager:
    def __init__(self):
        rospy.init_node("charger_uwb_target_manager")

        self.anchors = np.array(rospy.get_param("~anchors", [[0.0, 0.0], [5.0, 0.0], [5.0, 5.0]]), dtype=float)
        self.height_diff = rospy.get_param("~height_diff", 0.52)
        self.anchor_bias = np.array(rospy.get_param("~anchor_bias", [0.0, 0.0, 0.0]), dtype=float)
        self.min_valid_dist = rospy.get_param("~min_valid_dist", 0.5)
        self.max_valid_dist = rospy.get_param("~max_valid_dist", 10.5)
        self.samples_per_charger = rospy.get_param("~samples_per_charger", 10)
        self.measure_timeout = rospy.get_param("~measure_timeout", 20.0)
        self.baud_rate = rospy.get_param("~baud_rate", 115200)

        self.charger_1_tag_id = rospy.get_param("~charger_1_tag_id", 3)
        self.charger_2_tag_id = rospy.get_param("~charger_2_tag_id", 4)
        self.charger_1_port = rospy.get_param("~charger_1_port", "/dev/ttyUSB2")
        self.charger_2_port = rospy.get_param("~charger_2_port", "/dev/ttyUSB3")

        self.robot_pose = None
        self.target_pub = rospy.Publisher("/target_charger", Pose2D, queue_size=1, latch=True)
        self.status_pub = rospy.Publisher("/charger_target_status", String, queue_size=10)
        self.measurement_pub = rospy.Publisher("/charger_uwb_measurements", String, queue_size=10)

        rospy.Subscriber("/uwb_pose", Pose2D, self.pose_callback)
        rospy.Subscriber("/charge_start", Bool, self.charge_start_callback)

        self.log_dir = os.path.expanduser(rospy.get_param("~log_dir", "~/catkin_ws/charger_target_logs"))
        os.makedirs(self.log_dir, exist_ok=True)

        rospy.loginfo(
            "charger_uwb_target_manager ready. charger1 tag=%s port=%s charger2 tag=%s port=%s",
            self.charger_1_tag_id,
            self.charger_1_port,
            self.charger_2_tag_id,
            self.charger_2_port,
        )

    def pose_callback(self, msg):
        self.robot_pose = msg

    def charge_start_callback(self, msg):
        if not msg.data:
            return
        self.select_nearest_charger()

    def select_nearest_charger(self):
        if self.robot_pose is None:
            self.publish_status("NO_UWB_POSE")
            return

        charger1 = self.measure_charger(self.charger_1_port, self.charger_1_tag_id)
        charger2 = self.measure_charger(self.charger_2_port, self.charger_2_tag_id)

        candidates = []
        if charger1 is not None:
            candidates.append((1, charger1))
        if charger2 is not None:
            candidates.append((2, charger2))

        if not candidates:
            self.publish_status("NO_CHARGER_MEASUREMENT")
            return

        selected_id, selected = min(candidates, key=lambda item: item[1]["distance_to_robot"])
        target = Pose2D(x=selected["x"], y=selected["y"], theta=0.0)
        self.target_pub.publish(target)

        status = "CHARGE_TARGET_SELECTED id={} x={:.3f} y={:.3f} distance={:.3f}".format(
            selected_id,
            selected["x"],
            selected["y"],
            selected["distance_to_robot"],
        )
        self.publish_status(status)

        measurement = self.format_measurement(selected_id, charger1, charger2)
        self.measurement_pub.publish(String(data=measurement))
        self.write_log(measurement)

    def measure_charger(self, port, tag_id):
        samples = []
        ser = None
        try:
            ser = serial.Serial(port, self.baud_rate, timeout=0.1)
            time.sleep(1.0)
            ser.reset_input_buffer()
            start = time.time()
            while time.time() - start < self.measure_timeout and len(samples) < self.samples_per_charger:
                parsed = self.read_distance_line(ser, tag_id)
                if parsed is not None:
                    samples.append(parsed)
                time.sleep(0.005)
        except Exception as exc:
            self.publish_status("CHARGER{}_PORT_ERROR {}".format(tag_id, exc))
            return None
        finally:
            if ser is not None and ser.is_open:
                ser.close()

        if not samples:
            return None

        raw = np.median(np.array(samples, dtype=float), axis=0)
        corrected = raw + self.anchor_bias
        xy = self.solve_position(corrected)
        if xy is None:
            return None

        x, y = xy
        distance_to_robot = math.hypot(x - self.robot_pose.x, y - self.robot_pose.y)
        return {
            "tag_id": tag_id,
            "x": x,
            "y": y,
            "distance_to_robot": distance_to_robot,
            "samples": len(samples),
            "raw": raw,
            "corrected": corrected,
        }

    def read_distance_line(self, ser, tag_id):
        while ser.in_waiting > 0:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            prefix = "DIST,{}".format(tag_id)
            if not line.startswith(prefix):
                continue
            parts = line.split(",")
            if len(parts) != 5:
                continue
            try:
                values = [float(parts[2]), float(parts[3]), float(parts[4])]
            except ValueError:
                continue
            if all(self.min_valid_dist <= value <= self.max_valid_dist for value in values):
                return values
        return None

    def solve_position(self, ranges_3d):
        horizontal = []
        for distance in ranges_3d:
            if distance > self.height_diff:
                horizontal.append(math.sqrt(distance * distance - self.height_diff * self.height_diff))
            else:
                horizontal.append(0.0)
        horizontal = np.array(horizontal, dtype=float)

        def residual(params):
            point = np.array(params, dtype=float)
            return np.linalg.norm(self.anchors - point, axis=1) - horizontal

        result = least_squares(
            residual,
            np.array([2.5, 2.5]),
            bounds=([0.0, 0.0], [5.0, 5.0]),
            loss="soft_l1",
            f_scale=0.1,
            max_nfev=100,
        )
        if not result.success:
            return None
        return float(result.x[0]), float(result.x[1])

    def format_measurement(self, selected_id, charger1, charger2):
        def one(label, item):
            if item is None:
                return "{} unavailable".format(label)
            return "{} tag{} ({:.3f},{:.3f}) dist={:.3f} samples={}".format(
                label,
                item["tag_id"],
                item["x"],
                item["y"],
                item["distance_to_robot"],
                item["samples"],
            )

        return "robot=({:.3f},{:.3f},{:.3f}) | selected={} | {} | {}".format(
            self.robot_pose.x,
            self.robot_pose.y,
            self.robot_pose.theta,
            selected_id,
            one("charger1", charger1),
            one("charger2", charger2),
        )

    def publish_status(self, text):
        self.status_pub.publish(String(data=text))
        rospy.loginfo(text)

    def write_log(self, text):
        path = os.path.join(self.log_dir, "charger_target_{}.log".format(datetime.now().strftime("%Y%m%d")))
        with open(path, "a") as f:
            f.write("{} {}\n".format(datetime.now().isoformat(), text))


if __name__ == "__main__":
    try:
        ChargerUwbTargetManager()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
