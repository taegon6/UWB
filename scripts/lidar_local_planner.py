#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Pose2D, Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String


class LidarLocalPlanner:
    def __init__(self):
        rospy.init_node("lidar_local_planner")

        self.emergency_dist = rospy.get_param("~emergency_dist", 0.30)
        self.avoid_dist = rospy.get_param("~avoid_dist", 0.55)
        self.clear_dist = rospy.get_param("~clear_dist", 0.80)
        self.min_valid_scan_range = rospy.get_param("~min_valid_scan_range", 0.05)

        self.max_linear = rospy.get_param("~max_linear", 0.12)
        self.slow_linear = rospy.get_param("~slow_linear", 0.05)
        self.max_angular = rospy.get_param("~max_angular", 0.70)
        self.kp_heading = rospy.get_param("~kp_heading", 1.2)

        self.goal_radius = rospy.get_param("~goal_radius", 0.50)
        self.latch_near_charger = rospy.get_param("~latch_near_charger", True)
        self.goal_latch_reset_dist = rospy.get_param("~goal_latch_reset_dist", 0.20)
        self.control_period = rospy.get_param("~control_period", 0.05)
        self.scan_timeout = rospy.Duration(rospy.get_param("~scan_timeout", 0.5))
        self.uwb_timeout = rospy.Duration(rospy.get_param("~uwb_timeout", 2.0))
        self.target_timeout_sec = rospy.get_param("~target_timeout", 0.0)
        self.target_timeout = rospy.Duration(self.target_timeout_sec)

        self.robot_pose = None
        self.target = None
        self.scan = None
        self.last_pose_time = None
        self.last_target_time = None
        self.last_scan_time = None

        self.state = "WAIT"
        self.goal_latched = False

        self.cmd_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        self.state_pub = rospy.Publisher("/lidar_state", String, queue_size=10)
        self.near_pub = rospy.Publisher("/near_charger", Bool, queue_size=10)

        rospy.Subscriber("/scan", LaserScan, self.scan_callback)
        rospy.Subscriber("/uwb_pose", Pose2D, self.pose_callback)
        rospy.Subscriber("/target_charger", Pose2D, self.target_callback)

        rospy.Timer(rospy.Duration(self.control_period), self.control_loop)

    def pose_callback(self, msg):
        self.robot_pose = msg
        self.last_pose_time = rospy.Time.now()

    def target_callback(self, msg):
        if self.target_changed(msg):
            self.goal_latched = False
        self.target = msg
        self.last_target_time = rospy.Time.now()

    def scan_callback(self, msg):
        self.scan = msg
        self.last_scan_time = rospy.Time.now()

    def control_loop(self, _event):
        if self.robot_pose is None or self.target is None or self.scan is None:
            self.state = "WAIT"
            self.publish_stop()
            self.publish_state()
            return
        if self.goal_latched:
            self.state = "NEAR_CHARGER"
            self.near_pub.publish(Bool(data=True))
            self.publish_stop()
            self.publish_state()
            return
        if self.input_timed_out():
            self.state = "STALE_INPUT"
            self.near_pub.publish(Bool(data=False))
            self.publish_stop()
            self.publish_state()
            return

        dx = self.target.x - self.robot_pose.x
        dy = self.target.y - self.robot_pose.y
        dist_to_goal = math.hypot(dx, dy)

        if dist_to_goal < self.goal_radius:
            if self.latch_near_charger:
                self.goal_latched = True
            self.state = "NEAR_CHARGER"
            self.near_pub.publish(Bool(data=True))
            self.publish_stop()
            self.publish_state()
            return

        self.near_pub.publish(Bool(data=False))

        front_min = self.get_sector_min(-20.0, 20.0)
        front_left_avg = self.get_sector_avg(20.0, 70.0)
        front_right_avg = self.get_sector_avg(-70.0, -20.0)
        left_avg = self.get_sector_avg(70.0, 120.0)
        right_avg = self.get_sector_avg(-120.0, -70.0)

        left_score = 0.7 * front_left_avg + 0.3 * left_avg
        right_score = 0.7 * front_right_avg + 0.3 * right_avg

        twist = Twist()

        if front_min < self.emergency_dist:
            self.state = "EMERGENCY_STOP"
            twist.linear.x = 0.0
            twist.angular.z = self.max_angular if left_score > right_score else -self.max_angular
        elif self.should_avoid(front_min):
            if left_score > right_score:
                self.state = "AVOID_LEFT"
                twist.angular.z = self.max_angular * 0.7
            else:
                self.state = "AVOID_RIGHT"
                twist.angular.z = -self.max_angular * 0.7
            twist.linear.x = self.slow_linear
        else:
            self.state = "GO_TO_TARGET"
            twist = self.make_target_tracking_cmd(dx, dy)

        self.cmd_pub.publish(twist)
        self.publish_state()

    def input_timed_out(self):
        now = rospy.Time.now()
        checks = (
            (self.last_scan_time, self.scan_timeout),
            (self.last_pose_time, self.uwb_timeout),
        )

        if any(stamp is None or now - stamp > timeout for stamp, timeout in checks):
            return True

        if self.target_timeout_sec > 0.0:
            return self.last_target_time is None or now - self.last_target_time > self.target_timeout

        return False

    def target_changed(self, msg):
        if self.target is None:
            return False
        target_delta = math.hypot(msg.x - self.target.x, msg.y - self.target.y)
        return target_delta > self.goal_latch_reset_dist

    def should_avoid(self, front_min):
        if self.state in ("AVOID_LEFT", "AVOID_RIGHT", "EMERGENCY_STOP"):
            return front_min < self.clear_dist

        return front_min < self.avoid_dist

    def make_target_tracking_cmd(self, dx, dy):
        target_yaw = math.atan2(dy, dx)
        yaw_error = self.normalize_angle(target_yaw - self.robot_pose.theta)

        twist = Twist()
        twist.linear.x = self.max_linear
        twist.angular.z = self.clamp(
            self.kp_heading * yaw_error,
            -self.max_angular,
            self.max_angular,
        )

        if abs(yaw_error) > math.radians(45.0):
            twist.linear.x = min(twist.linear.x, 0.03)

        return twist

    def get_sector_values(self, angle_min_deg, angle_max_deg):
        values = []

        for index, distance in enumerate(self.scan.ranges):
            if math.isinf(distance) or math.isnan(distance):
                continue
            min_range = max(self.scan.range_min, self.min_valid_scan_range)
            if distance <= min_range or distance > self.scan.range_max:
                continue

            angle_rad = self.scan.angle_min + index * self.scan.angle_increment
            angle_deg = self.normalize_degree(math.degrees(angle_rad))

            if self.angle_in_sector(angle_deg, angle_min_deg, angle_max_deg):
                values.append(distance)

        return values

    def get_sector_min(self, angle_min_deg, angle_max_deg):
        values = self.get_sector_values(angle_min_deg, angle_max_deg)
        if not values:
            return float("inf")

        values.sort()
        sample_count = max(1, int(len(values) * 0.1))
        return sum(values[:sample_count]) / sample_count

    def get_sector_avg(self, angle_min_deg, angle_max_deg):
        values = self.get_sector_values(angle_min_deg, angle_max_deg)
        if not values:
            return float("inf")

        values.sort()
        start = int(len(values) * 0.2)
        end = int(len(values) * 0.8)
        trimmed = values[start:end]

        if not trimmed:
            return sum(values) / len(values)

        return sum(trimmed) / len(trimmed)

    def angle_in_sector(self, angle, start, end):
        angle = self.normalize_degree(angle)
        start = self.normalize_degree(start)
        end = self.normalize_degree(end)

        if start <= end:
            return start <= angle <= end

        return angle >= start or angle <= end

    @staticmethod
    def normalize_degree(angle):
        while angle > 180.0:
            angle -= 360.0
        while angle < -180.0:
            angle += 360.0
        return angle

    @staticmethod
    def normalize_angle(angle):
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    @staticmethod
    def clamp(value, lower, upper):
        return max(lower, min(value, upper))

    def publish_stop(self):
        self.cmd_pub.publish(Twist())

    def publish_state(self):
        self.state_pub.publish(String(data=self.state))


if __name__ == "__main__":
    try:
        LidarLocalPlanner()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
