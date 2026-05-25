#!/usr/bin/env python3

import math
import time
from glob import glob

import numpy as np
import rospy
import serial
from geometry_msgs.msg import Pose2D
from scipy.optimize import least_squares
from std_msgs.msg import String


class DualTagUwbPoseRaw:
    def __init__(self):
        rospy.init_node("dual_tag_uwb_pose_raw")

        self.port_tag1 = rospy.get_param("~port_tag1", "auto")
        self.port_tag2 = rospy.get_param("~port_tag2", "auto")
        self.auto_detect_ports = rospy.get_param("~auto_detect_ports", True)
        self.port_scan_timeout = rospy.get_param("~port_scan_timeout", 4.0)
        self.baud_rate = rospy.get_param("~baud_rate", 115200)
        self.anchors = np.array(rospy.get_param("~anchors", [[0.0, 0.0], [5.0, 0.0], [5.0, 5.0]]), dtype=float)
        self.height_diff = rospy.get_param("~height_diff", 0.52)
        self.tag_distance = rospy.get_param("~tag_distance", 0.172)
        self.half_tag_distance = self.tag_distance / 2.0
        self.tag2_is_front = rospy.get_param("~tag2_is_front", True)
        self.tag1_offset = np.array(rospy.get_param("~tag1_offset", [0.593, -0.592, 0.628]), dtype=float)
        self.tag2_offset = np.array(rospy.get_param("~tag2_offset", [0.608, 0.623, 0.133]), dtype=float)

        self.min_valid_dist = rospy.get_param("~min_valid_dist", 0.5)
        self.max_valid_dist = rospy.get_param("~max_valid_dist", 10.5)
        self.max_tag_dt = rospy.get_param("~max_tag_dt", 1.0)
        self.max_cost = rospy.get_param("~max_cost", 0.06)
        self.position_alpha = rospy.get_param("~position_alpha", 0.35)
        self.heading_alpha = rospy.get_param("~heading_alpha", 0.25)
        self.publish_rate = rospy.get_param("~publish_rate", 5.0)

        self.last_pose = np.array(rospy.get_param("~initial_pose", [2.5, 2.5, -1.57079632679]), dtype=float)
        self.filtered_pose = None

        self.pose_pub = rospy.Publisher("/uwb/pose_raw", Pose2D, queue_size=10)
        self.status_pub = rospy.Publisher("/uwb_pose_status", String, queue_size=10)

        self.port_tag1, self.port_tag2 = self.resolve_tag_ports()
        if self.port_tag1 == self.port_tag2:
            raise rospy.ROSException("TAG1 and TAG2 resolved to the same serial port: {}".format(self.port_tag1))

        self.ser1 = serial.Serial(self.port_tag1, self.baud_rate, timeout=0.1)
        self.ser2 = serial.Serial(self.port_tag2, self.baud_rate, timeout=0.1)
        time.sleep(1.0)
        self.ser1.reset_input_buffer()
        self.ser2.reset_input_buffer()

        rospy.on_shutdown(self.close)
        rospy.loginfo("dual_tag_uwb_pose_raw ready. TAG1=%s TAG2=%s", self.port_tag1, self.port_tag2)

    def resolve_tag_ports(self):
        if not self.auto_detect_ports and self.port_tag1 != "auto" and self.port_tag2 != "auto":
            return self.port_tag1, self.port_tag2

        detected = self.detect_tag_ports()
        tag1_port = detected.get(1) if self.port_tag1 == "auto" else self.port_tag1
        tag2_port = detected.get(2) if self.port_tag2 == "auto" else self.port_tag2

        missing = []
        if tag1_port is None:
            missing.append("TAG1")
        if tag2_port is None:
            missing.append("TAG2")
        if missing:
            raise rospy.ROSException(
                "Could not auto-detect {} UWB serial port(s). Detected={}".format(
                    ", ".join(missing),
                    detected,
                )
            )

        rospy.loginfo("Auto-detected UWB ports: TAG1=%s TAG2=%s", tag1_port, tag2_port)
        return tag1_port, tag2_port

    def detect_tag_ports(self):
        detected = {}
        candidates = self.serial_candidates()
        rospy.loginfo("Scanning UWB serial candidates: %s", candidates)

        for port in candidates:
            if 1 in detected and 2 in detected:
                break
            tag_id = self.detect_tag_id_on_port(port)
            if tag_id in (1, 2) and tag_id not in detected:
                detected[tag_id] = port
                rospy.loginfo("Detected TAG%d on %s", tag_id, port)

        return detected

    @staticmethod
    def serial_candidates():
        ports = []
        for pattern in ("/dev/ttyUSB*", "/dev/ttyACM*"):
            ports.extend(glob(pattern))
        return sorted(set(ports))

    def detect_tag_id_on_port(self, port):
        try:
            ser = serial.Serial(port, self.baud_rate, timeout=0.1)
        except serial.SerialException as exc:
            rospy.logdebug("Skipping serial candidate %s: %s", port, exc)
            return None

        try:
            time.sleep(0.2)
            ser.reset_input_buffer()
            deadline = time.time() + self.port_scan_timeout
            while time.time() < deadline and not rospy.is_shutdown():
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                except serial.SerialException as exc:
                    rospy.logdebug("Skipping serial candidate %s after read error: %s", port, exc)
                    return None
                if not line:
                    continue
                tag_id = self.tag_id_from_line(line)
                if tag_id is not None:
                    return tag_id
        finally:
            ser.close()

        return None

    @staticmethod
    def tag_id_from_line(line):
        if line.startswith("DIST,1"):
            return 1
        if line.startswith("DIST,2"):
            return 2
        return None

    def spin(self):
        rate = rospy.Rate(self.publish_rate)
        while not rospy.is_shutdown():
            tag1, tag2, dt = self.read_pair()
            if tag1 is None or tag2 is None:
                self.status_pub.publish(String(data="UWB_RAW_PAIR_TIMEOUT"))
                rate.sleep()
                continue
            if dt > self.max_tag_dt:
                self.status_pub.publish(String(data="UWB_RAW_TAG_DT_REJECTED"))
                rate.sleep()
                continue

            result = self.calculate_pose(tag1, tag2)
            if result is None:
                rate.sleep()
                continue

            x, y, theta, cost = result
            if cost > self.max_cost:
                self.status_pub.publish(String(data="UWB_RAW_COST_REJECTED"))
                rate.sleep()
                continue

            x, y, theta = self.filter_pose(x, y, theta)
            self.pose_pub.publish(Pose2D(x=x, y=y, theta=theta))
            self.status_pub.publish(String(data="UWB_RAW_POSE_OK"))
            rate.sleep()

    def read_pair(self):
        latest1 = None
        latest2 = None
        t1 = None
        t2 = None
        start = time.time()
        while time.time() - start < 2.5 and not rospy.is_shutdown():
            parsed1 = self.read_tag(self.ser1, 1)
            if parsed1 is not None:
                latest1, t1 = parsed1, time.time()
            parsed2 = self.read_tag(self.ser2, 2)
            if parsed2 is not None:
                latest2, t2 = parsed2, time.time()
            if latest1 is not None and latest2 is not None:
                return latest1, latest2, abs(t2 - t1)
            time.sleep(0.002)
        return None, None, None

    def read_tag(self, ser, tag_id):
        while ser.in_waiting > 0:
            try:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
            except serial.SerialException as exc:
                self.status_pub.publish(String(data="UWB_RAW_SERIAL_READ_ERROR"))
                rospy.logwarn_throttle(2.0, "Serial read failed on %s: %s", ser.port, exc)
                return None
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
            if all(self.min_valid_dist <= d <= self.max_valid_dist for d in values):
                return values
        return None

    def calculate_pose(self, tag1_raw, tag2_raw):
        tag1 = np.array(tag1_raw, dtype=float) + self.tag1_offset
        tag2 = np.array(tag2_raw, dtype=float) + self.tag2_offset
        if self.tag2_is_front:
            front, back = tag2, tag1
        else:
            front, back = tag1, tag2

        result = least_squares(
            self.rigid_body_error,
            self.last_pose,
            args=(front, back),
            bounds=([0.0, 0.0, -math.pi], [5.0, 5.0, math.pi]),
            loss="soft_l1",
            f_scale=0.1,
            max_nfev=100,
        )
        if not result.success:
            self.status_pub.publish(String(data="UWB_RAW_SOLVE_FAILED"))
            return None
        x, y, theta = result.x
        theta = self.normalize_angle(theta)
        self.last_pose = np.array([x, y, theta])
        return x, y, theta, result.cost

    def rigid_body_error(self, params, front_ranges, back_ranges):
        x, y, theta = params
        center = np.array([x, y])
        direction = np.array([math.cos(theta), math.sin(theta)])
        front_pos = center + self.half_tag_distance * direction
        back_pos = center - self.half_tag_distance * direction

        front_horizontal = self.horizontal_ranges(front_ranges)
        back_horizontal = self.horizontal_ranges(back_ranges)

        front_calc = np.linalg.norm(self.anchors - front_pos, axis=1)
        back_calc = np.linalg.norm(self.anchors - back_pos, axis=1)
        return np.concatenate([front_calc - front_horizontal, back_calc - back_horizontal])

    def horizontal_ranges(self, ranges_3d):
        out = []
        for distance in ranges_3d:
            if distance > self.height_diff:
                out.append(math.sqrt(distance * distance - self.height_diff * self.height_diff))
            else:
                out.append(0.0)
        return np.array(out)

    def filter_pose(self, x, y, theta):
        if self.filtered_pose is None:
            self.filtered_pose = np.array([x, y, theta])
            return x, y, theta

        self.filtered_pose[0] += self.position_alpha * (x - self.filtered_pose[0])
        self.filtered_pose[1] += self.position_alpha * (y - self.filtered_pose[1])
        theta_diff = self.normalize_angle(theta - self.filtered_pose[2])
        self.filtered_pose[2] = self.normalize_angle(self.filtered_pose[2] + self.heading_alpha * theta_diff)
        return tuple(self.filtered_pose)

    def close(self):
        for ser in (getattr(self, "ser1", None), getattr(self, "ser2", None)):
            if ser is not None and ser.is_open:
                ser.close()

    @staticmethod
    def normalize_angle(angle):
        return math.atan2(math.sin(angle), math.cos(angle))


if __name__ == "__main__":
    try:
        DualTagUwbPoseRaw().spin()
    except rospy.ROSInterruptException:
        pass
