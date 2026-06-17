#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Pose2D, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import String


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class OdomPoseFromStart:
    def __init__(self):
        rospy.init_node("odom_pose_from_start")

        self.start_x = float(rospy.get_param("~start_x", 0.0))
        self.start_y = float(rospy.get_param("~start_y", 0.0))
        self.start_theta = float(rospy.get_param("~start_theta", 0.0))
        self.frame_id = rospy.get_param("~frame_id", "uwb_map")

        self.odom_origin = None
        self.pose_pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)
        self.debug_pub = rospy.Publisher("/uwb/pose", PoseWithCovarianceStamped, queue_size=10)
        self.status_pub = rospy.Publisher("/uwb_pose_status", String, queue_size=10)

        rospy.Subscriber("/odom", Odometry, self.odom_callback)
        rospy.loginfo(
            "odom_pose_from_start ready. start=(%.3f, %.3f, %.3f)",
            self.start_x,
            self.start_y,
            self.start_theta,
        )

    def odom_callback(self, msg):
        odom_x = msg.pose.pose.position.x
        odom_y = msg.pose.pose.position.y
        odom_theta = self.quaternion_to_yaw(msg.pose.pose.orientation)

        if self.odom_origin is None:
            self.odom_origin = (odom_x, odom_y, odom_theta)
            self.status_pub.publish(String(data="ODOM_POSE_ORIGIN_SET"))

        origin_x, origin_y, origin_theta = self.odom_origin
        dx = odom_x - origin_x
        dy = odom_y - origin_y

        rotate = self.start_theta - origin_theta
        cos_r = math.cos(rotate)
        sin_r = math.sin(rotate)

        pose = Pose2D()
        pose.x = self.start_x + cos_r * dx - sin_r * dy
        pose.y = self.start_y + sin_r * dx + cos_r * dy
        pose.theta = normalize_angle(self.start_theta + normalize_angle(odom_theta - origin_theta))

        self.pose_pub.publish(pose)
        self.debug_pub.publish(self.to_covariance_pose(pose))
        self.status_pub.publish(String(data="ODOM_POSE_OK"))

    def to_covariance_pose(self, pose):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = self.frame_id
        msg.pose.pose.position.x = pose.x
        msg.pose.pose.position.y = pose.y
        msg.pose.pose.position.z = 0.0
        half_yaw = pose.theta * 0.5
        msg.pose.pose.orientation.z = math.sin(half_yaw)
        msg.pose.pose.orientation.w = math.cos(half_yaw)
        msg.pose.covariance[0] = 0.10 * 0.10
        msg.pose.covariance[7] = 0.10 * 0.10
        msg.pose.covariance[35] = math.radians(10.0) ** 2
        return msg

    @staticmethod
    def quaternion_to_yaw(q):
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)


if __name__ == "__main__":
    try:
        OdomPoseFromStart()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
