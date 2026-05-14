#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Pose2D
from nav_msgs.msg import Odometry
from std_msgs.msg import Float32MultiArray, String


class UwbPoseEstimator:
    def __init__(self):
        rospy.init_node("uwb_pose_estimator")

        self.anchors = self.load_anchors()
        self.min_valid_anchors = rospy.get_param("~min_valid_anchors", 3)
        self.max_range = rospy.get_param("~max_range", 20.0)
        self.smoothing_alpha = rospy.get_param("~smoothing_alpha", 0.35)
        self.anchor_bias = self.load_anchor_bias()
        self.max_range_jump = rospy.get_param("~max_range_jump", 0.50)
        self.max_pose_jump = rospy.get_param("~max_pose_jump", 0.70)
        self.residual_threshold = rospy.get_param("~residual_threshold", 0.35)
        self.uwb_timeout = rospy.Duration(rospy.get_param("~uwb_timeout", 1.5))

        self.last_ranges = {}
        self.last_filter_status = "UWB_POSE_OK"
        self.last_range_time = None
        self.last_pose = None
        self.yaw = 0.0

        self.pose_pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)
        self.status_pub = rospy.Publisher("/uwb_pose_status", String, queue_size=10)

        rospy.Subscriber("/uwb/ranges", Float32MultiArray, self.ranges_callback)
        rospy.Subscriber("/odom", Odometry, self.odom_callback)
        rospy.Timer(rospy.Duration(0.5), self.stale_input_timer)

        rospy.loginfo("uwb_pose_estimator ready. anchors=%s bias=%s", self.anchors, self.anchor_bias)

    def load_anchors(self):
        raw_anchors = rospy.get_param(
            "~anchors",
            [
                [0.0, 0.0],
                [5.0, 0.0],
                [0.0, 5.0],
                [5.0, 5.0],
            ],
        )

        anchors = []
        for item in raw_anchors:
            if len(item) < 2:
                rospy.logwarn("Ignoring invalid anchor entry: %s", item)
                continue
            anchors.append((float(item[0]), float(item[1])))

        if len(anchors) < 3:
            raise rospy.ROSException("At least 3 UWB anchors are required")

        return anchors

    def load_anchor_bias(self):
        raw_bias = rospy.get_param("~anchor_bias", [])
        bias = [0.0 for _ in self.anchors]

        for index, value in enumerate(raw_bias):
            if index >= len(bias):
                break
            bias[index] = float(value)

        return bias

    def odom_callback(self, msg):
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.yaw = math.atan2(siny_cosp, cosy_cosp)

    def ranges_callback(self, msg):
        self.last_range_time = rospy.Time.now()
        ranges = self.filter_ranges(msg.data)
        if len(ranges) < self.min_valid_anchors:
            if self.last_filter_status == "RANGE_OUTLIER_REJECTED":
                self.status_pub.publish(String(data="RANGE_OUTLIER_REJECTED"))
            else:
                self.status_pub.publish(String(data="NOT_ENOUGH_VALID_RANGES"))
            return

        pose_xy = self.solve_position(ranges)
        if pose_xy is None:
            self.status_pub.publish(String(data="POSITION_SOLVE_FAILED"))
            return

        ranges, pose_xy, residual_status = self.reject_high_residual_ranges(ranges, pose_xy)
        if len(ranges) < self.min_valid_anchors:
            self.status_pub.publish(String(data=residual_status))
            return

        x, y = pose_xy
        if self.last_pose is not None:
            pose_jump = math.hypot(x - self.last_pose.x, y - self.last_pose.y)
            if pose_jump > self.max_pose_jump:
                self.status_pub.publish(String(data="POSE_JUMP_REJECTED"))
                return

        if self.last_pose is not None:
            alpha = self.smoothing_alpha
            x = alpha * x + (1.0 - alpha) * self.last_pose.x
            y = alpha * y + (1.0 - alpha) * self.last_pose.y

        pose = Pose2D(x=x, y=y, theta=self.yaw)
        self.last_pose = pose
        self.update_last_ranges(ranges)
        self.pose_pub.publish(pose)
        if self.last_filter_status == "RANGE_OUTLIER_REJECTED" and residual_status == "UWB_POSE_OK":
            self.status_pub.publish(String(data="RANGE_OUTLIER_REJECTED"))
        else:
            self.status_pub.publish(String(data=residual_status))

    def filter_ranges(self, raw_ranges):
        ranges = []
        range_jump_rejected = False
        for index, distance in enumerate(raw_ranges):
            if index >= len(self.anchors):
                break
            if math.isnan(distance) or math.isinf(distance):
                continue
            corrected = float(distance) - self.anchor_bias[index]
            if corrected <= 0.0 or corrected > self.max_range:
                continue
            if self.range_jumped(index, corrected):
                range_jump_rejected = True
                continue
            ranges.append((index, corrected))

        self.last_filter_status = "RANGE_OUTLIER_REJECTED" if range_jump_rejected else "UWB_POSE_OK"
        return ranges

    def range_jumped(self, index, distance):
        previous = self.last_ranges.get(index)
        if previous is None:
            return False
        return abs(distance - previous) > self.max_range_jump

    def update_last_ranges(self, ranges):
        for index, distance in ranges:
            self.last_ranges[index] = distance

    def stale_input_timer(self, _event):
        if self.last_range_time is None:
            return
        if rospy.Time.now() - self.last_range_time > self.uwb_timeout:
            self.status_pub.publish(String(data="STALE_UWB_INPUT"))

    def reject_high_residual_ranges(self, ranges, pose_xy):
        residuals = self.compute_residuals(ranges, pose_xy)
        accepted = [
            item for item in ranges
            if residuals.get(item[0], 0.0) <= self.residual_threshold
        ]

        if len(accepted) == len(ranges):
            return ranges, pose_xy, "UWB_POSE_OK"

        if len(accepted) < self.min_valid_anchors:
            return accepted, pose_xy, "HIGH_RESIDUAL_REJECTED"

        refined_pose = self.solve_position(accepted)
        if refined_pose is None:
            return accepted, pose_xy, "POSITION_SOLVE_FAILED"

        return accepted, refined_pose, "RANGE_OUTLIER_REJECTED"

    def compute_residuals(self, ranges, pose_xy):
        x, y = pose_xy
        residuals = {}
        for index, distance in ranges:
            ax, ay = self.anchors[index]
            expected = math.hypot(x - ax, y - ay)
            residuals[index] = abs(expected - distance)
        return residuals

    def solve_position(self, ranges):
        ref_index, ref_distance = ranges[0]
        x0, y0 = self.anchors[ref_index]

        ata00 = 0.0
        ata01 = 0.0
        ata11 = 0.0
        atb0 = 0.0
        atb1 = 0.0

        for index, distance in ranges[1:]:
            xi, yi = self.anchors[index]
            a0 = 2.0 * (xi - x0)
            a1 = 2.0 * (yi - y0)
            b = (
                ref_distance * ref_distance
                - distance * distance
                + xi * xi
                - x0 * x0
                + yi * yi
                - y0 * y0
            )

            ata00 += a0 * a0
            ata01 += a0 * a1
            ata11 += a1 * a1
            atb0 += a0 * b
            atb1 += a1 * b

        determinant = ata00 * ata11 - ata01 * ata01
        if abs(determinant) < 1e-9:
            return None

        x = (atb0 * ata11 - atb1 * ata01) / determinant
        y = (ata00 * atb1 - ata01 * atb0) / determinant

        return x, y


if __name__ == "__main__":
    try:
        UwbPoseEstimator()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
