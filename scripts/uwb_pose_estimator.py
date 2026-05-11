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

        self.last_pose = None
        self.yaw = 0.0

        self.pose_pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)
        self.status_pub = rospy.Publisher("/uwb_pose_status", String, queue_size=10)

        rospy.Subscriber("/uwb/ranges", Float32MultiArray, self.ranges_callback)
        rospy.Subscriber("/odom", Odometry, self.odom_callback)

        rospy.loginfo("uwb_pose_estimator ready. anchors=%s", self.anchors)

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

    def odom_callback(self, msg):
        q = msg.pose.pose.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        self.yaw = math.atan2(siny_cosp, cosy_cosp)

    def ranges_callback(self, msg):
        ranges = self.filter_ranges(msg.data)
        if len(ranges) < self.min_valid_anchors:
            self.status_pub.publish(String(data="NOT_ENOUGH_VALID_RANGES"))
            return

        pose_xy = self.solve_position(ranges)
        if pose_xy is None:
            self.status_pub.publish(String(data="POSITION_SOLVE_FAILED"))
            return

        x, y = pose_xy
        if self.last_pose is not None:
            alpha = self.smoothing_alpha
            x = alpha * x + (1.0 - alpha) * self.last_pose.x
            y = alpha * y + (1.0 - alpha) * self.last_pose.y

        pose = Pose2D(x=x, y=y, theta=self.yaw)
        self.last_pose = pose
        self.pose_pub.publish(pose)
        self.status_pub.publish(String(data="UWB_POSE_OK"))

    def filter_ranges(self, raw_ranges):
        ranges = []
        for index, distance in enumerate(raw_ranges):
            if index >= len(self.anchors):
                break
            if math.isnan(distance) or math.isinf(distance):
                continue
            if distance <= 0.0 or distance > self.max_range:
                continue
            ranges.append((index, float(distance)))

        return ranges

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
