#!/usr/bin/env python3

import rospy
from geometry_msgs.msg import Pose2D


class FakeUwbPosePublisher:
    def __init__(self):
        rospy.init_node("fake_uwb_pose_publisher")

        self.rate = rospy.get_param("~rate", 10.0)
        self.x = rospy.get_param("~start_x", 0.5)
        self.y = rospy.get_param("~start_y", 0.5)
        self.theta = rospy.get_param("~theta", 0.0)
        self.vx = rospy.get_param("~vx", 0.0)
        self.vy = rospy.get_param("~vy", 0.0)
        self.pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)
        self.last_time = rospy.Time.now()

        rospy.Timer(rospy.Duration(1.0 / self.rate), self.timer_callback)

    def timer_callback(self, _event):
        now = rospy.Time.now()
        dt = (now - self.last_time).to_sec()
        self.last_time = now

        self.x += self.vx * dt
        self.y += self.vy * dt
        self.pub.publish(Pose2D(x=self.x, y=self.y, theta=self.theta))


if __name__ == "__main__":
    try:
        FakeUwbPosePublisher()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
