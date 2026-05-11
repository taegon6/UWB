#!/usr/bin/env python3

import math
import random

import rospy
from geometry_msgs.msg import Pose2D
from nav_msgs.msg import Odometry


class SimUwbPoseFromOdom:
    def __init__(self):
        rospy.init_node("sim_uwb_pose_from_odom")

        self.position_noise_std = rospy.get_param("~position_noise_std", 0.0)
        self.yaw_noise_std = rospy.get_param("~yaw_noise_std", 0.0)
        self.pose_pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)

        rospy.Subscriber("/odom", Odometry, self.odom_callback)
        rospy.loginfo("sim_uwb_pose_from_odom ready.")

    def odom_callback(self, msg):
        pose = msg.pose.pose
        yaw = self.quaternion_to_yaw(pose.orientation)

        uwb_pose = Pose2D()
        uwb_pose.x = pose.position.x + random.gauss(0.0, self.position_noise_std)
        uwb_pose.y = pose.position.y + random.gauss(0.0, self.position_noise_std)
        uwb_pose.theta = yaw + random.gauss(0.0, self.yaw_noise_std)

        self.pose_pub.publish(uwb_pose)

    @staticmethod
    def quaternion_to_yaw(q):
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)


if __name__ == "__main__":
    try:
        SimUwbPoseFromOdom()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
