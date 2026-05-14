#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Point, Pose2D, PoseStamped
from nav_msgs.msg import Path
from std_msgs.msg import Bool, String
from visualization_msgs.msg import Marker, MarkerArray


class UwbRvizVisualizer:
    def __init__(self):
        rospy.init_node("uwb_rviz_visualizer")

        self.frame_id = rospy.get_param("~frame_id", "uwb_map")
        self.path_max_points = rospy.get_param("~path_max_points", 1000)
        self.goal_radius = rospy.get_param("~goal_radius", 1.0)
        self.anchors = self.load_points("~anchors", [[0.0, 0.0], [5.0, 0.0], [0.0, 5.0], [5.0, 5.0]])
        self.chargers = self.load_chargers()

        self.robot_pose = None
        self.target = None
        self.lidar_state = "WAIT"
        self.near_charger = False
        self.path = Path()
        self.path.header.frame_id = self.frame_id

        self.marker_pub = rospy.Publisher("/uwb_markers", MarkerArray, queue_size=1)
        self.path_pub = rospy.Publisher("/uwb_path", Path, queue_size=1)

        rospy.Subscriber("/uwb_pose", Pose2D, self.pose_callback)
        rospy.Subscriber("/target_charger", Pose2D, self.target_callback)
        rospy.Subscriber("/lidar_state", String, self.state_callback)
        rospy.Subscriber("/near_charger", Bool, self.near_callback)

        rospy.Timer(rospy.Duration(0.2), self.publish_visualization)

    def load_points(self, param_name, default):
        raw_points = rospy.get_param(param_name, default)
        return [(float(item[0]), float(item[1])) for item in raw_points if len(item) >= 2]

    def load_chargers(self):
        raw_chargers = rospy.get_param("~chargers", [[1, 4.0, 1.2], [2, 4.0, 3.8]])
        chargers = []
        for item in raw_chargers:
            if len(item) >= 3:
                chargers.append((int(item[0]), float(item[1]), float(item[2])))
        return chargers

    def pose_callback(self, msg):
        self.robot_pose = msg

        stamped = PoseStamped()
        stamped.header.stamp = rospy.Time.now()
        stamped.header.frame_id = self.frame_id
        stamped.pose.position.x = msg.x
        stamped.pose.position.y = msg.y
        stamped.pose.position.z = 0.0
        stamped.pose.orientation.w = math.cos(msg.theta / 2.0)
        stamped.pose.orientation.z = math.sin(msg.theta / 2.0)

        self.path.header.stamp = stamped.header.stamp
        self.path.poses.append(stamped)
        if len(self.path.poses) > self.path_max_points:
            self.path.poses = self.path.poses[-self.path_max_points:]

    def target_callback(self, msg):
        self.target = msg

    def state_callback(self, msg):
        self.lidar_state = msg.data

    def near_callback(self, msg):
        self.near_charger = msg.data

    def publish_visualization(self, _event):
        markers = MarkerArray()
        stamp = rospy.Time.now()

        markers.markers.append(self.make_field_marker(stamp, 0))
        marker_id = 1

        for index, (x, y) in enumerate(self.anchors):
            markers.markers.append(self.make_cylinder(stamp, marker_id, x, y, 0.12, 0.20, (0.1, 0.2, 1.0, 1.0)))
            marker_id += 1
            markers.markers.append(self.make_text(stamp, marker_id, x, y + 0.18, "A{}".format(index), 0.16))
            marker_id += 1

        for charger_id, x, y in self.chargers:
            markers.markers.append(self.make_cylinder(stamp, marker_id, x, y, 0.25, 0.04, (0.0, 0.8, 0.2, 1.0)))
            marker_id += 1
            markers.markers.append(self.make_text(stamp, marker_id, x, y + 0.25, "C{}".format(charger_id), 0.18))
            marker_id += 1

        if self.target is not None:
            markers.markers.append(self.make_goal_radius_marker(stamp, marker_id, self.target.x, self.target.y))
            marker_id += 1
            markers.markers.append(self.make_cylinder(stamp, marker_id, self.target.x, self.target.y, 0.12, 0.08, (1.0, 0.6, 0.0, 1.0)))
            marker_id += 1

        if self.robot_pose is not None:
            markers.markers.append(self.make_robot_marker(stamp, marker_id, self.robot_pose))
            marker_id += 1
            status = "{} near={}".format(self.lidar_state, str(self.near_charger).lower())
            markers.markers.append(self.make_text(stamp, marker_id, self.robot_pose.x, self.robot_pose.y + 0.35, status, 0.16))
            marker_id += 1

        self.marker_pub.publish(markers)
        self.path_pub.publish(self.path)

    def make_field_marker(self, stamp, marker_id):
        marker = self.base_marker(stamp, marker_id, Marker.LINE_STRIP)
        marker.scale.x = 0.03
        marker.color.r = 0.7
        marker.color.g = 0.7
        marker.color.b = 0.7
        marker.color.a = 1.0
        for x, y in [(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)]:
            marker.points.append(Point(x=x, y=y, z=0.01))
        return marker

    def make_robot_marker(self, stamp, marker_id, pose):
        marker = self.base_marker(stamp, marker_id, Marker.ARROW)
        marker.pose.position.x = pose.x
        marker.pose.position.y = pose.y
        marker.pose.position.z = 0.08
        marker.pose.orientation.w = math.cos(pose.theta / 2.0)
        marker.pose.orientation.z = math.sin(pose.theta / 2.0)
        marker.scale.x = 0.35
        marker.scale.y = 0.12
        marker.scale.z = 0.12
        marker.color.r = 1.0
        marker.color.g = 0.1
        marker.color.b = 0.1
        marker.color.a = 1.0
        return marker

    def make_goal_radius_marker(self, stamp, marker_id, x, y):
        marker = self.base_marker(stamp, marker_id, Marker.CYLINDER)
        marker.pose.position.x = x
        marker.pose.position.y = y
        marker.pose.position.z = 0.01
        marker.scale.x = self.goal_radius * 2.0
        marker.scale.y = self.goal_radius * 2.0
        marker.scale.z = 0.02
        marker.color.r = 1.0
        marker.color.g = 0.8
        marker.color.b = 0.0
        marker.color.a = 0.22
        return marker

    def make_cylinder(self, stamp, marker_id, x, y, diameter, height, color):
        marker = self.base_marker(stamp, marker_id, Marker.CYLINDER)
        marker.pose.position.x = x
        marker.pose.position.y = y
        marker.pose.position.z = height / 2.0
        marker.scale.x = diameter
        marker.scale.y = diameter
        marker.scale.z = height
        marker.color.r, marker.color.g, marker.color.b, marker.color.a = color
        return marker

    def make_text(self, stamp, marker_id, x, y, text, size):
        marker = self.base_marker(stamp, marker_id, Marker.TEXT_VIEW_FACING)
        marker.pose.position.x = x
        marker.pose.position.y = y
        marker.pose.position.z = 0.25
        marker.scale.z = size
        marker.text = text
        marker.color.r = 1.0
        marker.color.g = 1.0
        marker.color.b = 1.0
        marker.color.a = 1.0
        return marker

    def base_marker(self, stamp, marker_id, marker_type):
        marker = Marker()
        marker.header.stamp = stamp
        marker.header.frame_id = self.frame_id
        marker.ns = "uwb_charging"
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.lifetime = rospy.Duration(0.5)
        return marker


if __name__ == "__main__":
    try:
        UwbRvizVisualizer()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
