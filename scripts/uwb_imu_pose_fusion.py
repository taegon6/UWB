#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Pose2D
from sensor_msgs.msg import Imu
from std_msgs.msg import String


class UwbImuPoseFusion:
    def __init__(self):
        rospy.init_node("uwb_imu_pose_fusion")

        self.imu_yaw_offset = rospy.get_param("~imu_yaw_offset", 0.0)
        self.invert_imu_yaw = rospy.get_param("~invert_imu_yaw", False)
        self.auto_calibrate_yaw_offset = rospy.get_param("~auto_calibrate_yaw_offset", False)
        self.uwb_timeout = rospy.Duration(rospy.get_param("~uwb_timeout", 2.0))
        self.imu_timeout = rospy.Duration(rospy.get_param("~imu_timeout", 0.5))
        self.publish_rate = rospy.get_param("~publish_rate", 20.0)

        self.last_uwb = None
        self.last_imu_yaw = None
        self.last_uwb_time = None
        self.last_imu_time = None
        self.did_auto_calibrate = False

        self.pose_pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)
        self.status_pub = rospy.Publisher("/uwb_pose_status", String, queue_size=10)

        rospy.Subscriber("/uwb/pose_raw", Pose2D, self.uwb_callback)
        rospy.Subscriber("/imu", Imu, self.imu_callback)
        rospy.Timer(rospy.Duration(1.0 / self.publish_rate), self.publish_pose)

        rospy.loginfo(
            "uwb_imu_pose_fusion ready. offset=%.3f invert=%s auto_cal=%s",
            self.imu_yaw_offset,
            self.invert_imu_yaw,
            self.auto_calibrate_yaw_offset,
        )

    def uwb_callback(self, msg):
        self.last_uwb = msg
        self.last_uwb_time = rospy.Time.now()
        self.try_auto_calibrate()

    def imu_callback(self, msg):
        self.last_imu_yaw = self.yaw_from_imu(msg)
        self.last_imu_time = rospy.Time.now()
        self.try_auto_calibrate()

    def try_auto_calibrate(self):
        if not self.auto_calibrate_yaw_offset or self.did_auto_calibrate:
            return
        if self.last_uwb is None or self.last_imu_yaw is None:
            return

        self.imu_yaw_offset = self.normalize_angle(self.last_uwb.theta - self.last_imu_yaw)
        self.did_auto_calibrate = True
        rospy.loginfo("Auto calibrated IMU yaw offset: %.3f rad", self.imu_yaw_offset)

    def publish_pose(self, _event):
        status = self.current_status()
        if status != "UWB_IMU_POSE_OK":
            self.status_pub.publish(String(data=status))
            return

        theta = self.normalize_angle(self.last_imu_yaw + self.imu_yaw_offset)
        pose = Pose2D(x=self.last_uwb.x, y=self.last_uwb.y, theta=theta)
        self.pose_pub.publish(pose)
        self.status_pub.publish(String(data=status))

    def current_status(self):
        now = rospy.Time.now()
        if self.last_uwb_time is None or now - self.last_uwb_time > self.uwb_timeout:
            return "UWB_TIMEOUT"
        if self.last_imu_time is None or now - self.last_imu_time > self.imu_timeout:
            return "IMU_TIMEOUT"
        return "UWB_IMU_POSE_OK"

    def yaw_from_imu(self, msg):
        q = msg.orientation
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        if self.invert_imu_yaw:
            yaw = -yaw
        return self.normalize_angle(yaw)

    @staticmethod
    def normalize_angle(angle):
        return math.atan2(math.sin(angle), math.cos(angle))


if __name__ == "__main__":
    try:
        UwbImuPoseFusion()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
