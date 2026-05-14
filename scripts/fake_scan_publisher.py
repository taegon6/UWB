#!/usr/bin/env python3

import math

import rospy
from sensor_msgs.msg import LaserScan


class FakeScanPublisher:
    def __init__(self):
        rospy.init_node("fake_scan_publisher")

        self.rate = rospy.get_param("~rate", 10.0)
        self.obstacle_distance = rospy.get_param("~obstacle_distance", 2.0)
        self.default_distance = rospy.get_param("~default_distance", 3.5)
        self.front_width_deg = rospy.get_param("~front_width_deg", 30.0)
        self.pub = rospy.Publisher("/scan", LaserScan, queue_size=10)

        rospy.Timer(rospy.Duration(1.0 / self.rate), self.timer_callback)

    def timer_callback(self, _event):
        scan = LaserScan()
        scan.header.stamp = rospy.Time.now()
        scan.header.frame_id = "base_scan"
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = math.radians(1.0)
        scan.time_increment = 0.0
        scan.scan_time = 1.0 / self.rate
        scan.range_min = 0.12
        scan.range_max = 3.5

        count = int(round((scan.angle_max - scan.angle_min) / scan.angle_increment)) + 1
        ranges = []
        half_width = self.front_width_deg / 2.0
        for index in range(count):
            angle = scan.angle_min + index * scan.angle_increment
            angle_deg = math.degrees(angle)
            if -half_width <= angle_deg <= half_width:
                ranges.append(self.obstacle_distance)
            else:
                ranges.append(self.default_distance)

        scan.ranges = ranges
        self.pub.publish(scan)


if __name__ == "__main__":
    try:
        FakeScanPublisher()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
