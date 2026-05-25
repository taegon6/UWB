#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Pose2D
from sensor_msgs.msg import Imu


class FakeUwbImuTest:
    def __init__(self):
        rospy.init_node("fake_uwb_imu_test")
        self.rate_hz = rospy.get_param("~rate", 10.0)
        self.uwb_x = rospy.get_param("~uwb_x", 1.2)
        self.uwb_y = rospy.get_param("~uwb_y", 0.8)
        self.uwb_theta = rospy.get_param("~uwb_theta", 1.57)
        self.imu_yaw = rospy.get_param("~imu_yaw", 0.25)

        self.uwb_pub = rospy.Publisher("/uwb/pose_raw", Pose2D, queue_size=10)
        self.imu_pub = rospy.Publisher("/imu", Imu, queue_size=10)

    def spin(self):
        rate = rospy.Rate(self.rate_hz)
        while not rospy.is_shutdown():
            self.uwb_pub.publish(Pose2D(x=self.uwb_x, y=self.uwb_y, theta=self.uwb_theta))
            self.imu_pub.publish(self.make_imu(self.imu_yaw))
            rate.sleep()

    @staticmethod
    def make_imu(yaw):
        msg = Imu()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = "imu_link"
        msg.orientation.w = math.cos(yaw / 2.0)
        msg.orientation.z = math.sin(yaw / 2.0)
        return msg


if __name__ == "__main__":
    try:
        FakeUwbImuTest().spin()
    except rospy.ROSInterruptException:
        pass
