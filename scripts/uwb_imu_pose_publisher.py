#!/usr/bin/env python3

import math
import threading

import rospy
from geometry_msgs.msg import Pose2D, PoseWithCovarianceStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from std_msgs.msg import String


def normalize_angle(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class UwbImuPosePublisher:
    """Publish the planner pose from UWB x/y and IMU yaw.

    Input:
      /uwb/pose_raw  geometry_msgs/Pose2D  x, y, UWB dual-tag heading
      /imu           sensor_msgs/Imu       robot yaw source

    Output:
      /uwb_pose        geometry_msgs/Pose2D  x, y, IMU heading
      /uwb_pose_status std_msgs/String       health/status for debugging
    """

    def __init__(self):
        rospy.init_node("uwb_imu_pose_publisher")

        self.uwb_pose_raw_topic = rospy.get_param("~uwb_pose_raw_topic", "/uwb/pose_raw")
        self.imu_topic = rospy.get_param("~imu_topic", "/imu")
        self.odom_topic = rospy.get_param("~odom_topic", "/odom")
        self.frame_id = rospy.get_param("~frame_id", "map")
        self.publish_rate = float(rospy.get_param("~publish_rate", 20.0))
        self.uwb_timeout = rospy.Duration(float(rospy.get_param("~uwb_timeout", 1.0)))
        self.allow_stale_uwb = bool(rospy.get_param("~allow_stale_uwb", False))
        self.max_stale_uwb_age = rospy.Duration(float(rospy.get_param("~max_stale_uwb_age", 30.0)))
        self.use_odom_prediction = bool(rospy.get_param("~use_odom_prediction", True))
        self.odom_timeout = rospy.Duration(float(rospy.get_param("~odom_timeout", 0.5)))
        self.max_prediction_dt = float(rospy.get_param("~max_prediction_dt", 0.20))
        self.uwb_correction_alpha = float(rospy.get_param("~uwb_correction_alpha", 0.45))
        self.heading_correction_alpha = float(rospy.get_param("~heading_correction_alpha", 0.35))
        self.imu_timeout = rospy.Duration(float(rospy.get_param("~imu_timeout", 1.0)))
        self.heading_source = rospy.get_param("~heading_source", "imu").lower()
        self.initial_heading_deg = float(rospy.get_param("~initial_heading_deg", -90.0))
        self.imu_yaw_offset = float(rospy.get_param("~imu_yaw_offset", 0.0))
        self.invert_imu_yaw = bool(rospy.get_param("~invert_imu_yaw", False))
        self.auto_calibrate_yaw_offset = bool(rospy.get_param("~auto_calibrate_yaw_offset", False))
        self.auto_calibrate_sample_count = int(rospy.get_param("~auto_calibrate_sample_count", 20))
        self.auto_calibrate_min_resultant = float(rospy.get_param("~auto_calibrate_min_resultant", 0.70))
        self.auto_calibrate_max_position_std = float(rospy.get_param("~auto_calibrate_max_position_std", 0.35))

        self.room_min_x = float(rospy.get_param("~room_min_x", 0.0))
        self.room_max_x = float(rospy.get_param("~room_max_x", 5.0))
        self.room_min_y = float(rospy.get_param("~room_min_y", 0.0))
        self.room_max_y = float(rospy.get_param("~room_max_y", 5.0))
        self.pose_bounds_margin = float(rospy.get_param("~pose_bounds_margin", 0.10))
        self.boundary_clamp_margin = float(rospy.get_param("~boundary_clamp_margin", 0.05))
        self.invalid_origin_radius = float(rospy.get_param("~invalid_origin_radius", 0.12))
        self.max_pose_jump = float(rospy.get_param("~max_pose_jump", 0.80))
        self.require_pose_stability = bool(rospy.get_param("~require_pose_stability", True))
        self.stable_pose_radius = float(rospy.get_param("~stable_pose_radius", 0.35))
        self.stable_pose_samples_required = int(rospy.get_param("~stable_pose_samples_required", 2))

        self.lock = threading.Lock()
        self.latest_uwb_pose = None
        self.latest_uwb_time = None
        self.latest_imu_yaw = None
        self.latest_imu_time = None
        self.latest_odom_linear = 0.0
        self.latest_odom_angular = 0.0
        self.latest_odom_time = None
        self.last_accepted_uwb_pose = None
        self.pending_uwb_pose = None
        self.pending_uwb_count = 0
        self.fused_pose = None
        self.last_prediction_time = None
        self.calibration_samples = []
        self.yaw_offset_calibrated = not self.auto_calibrate_yaw_offset and self.heading_source != "initial_imu"
        self.last_status = None

        self.pose_pub = rospy.Publisher("/uwb_pose", Pose2D, queue_size=10)
        self.debug_pose_pub = rospy.Publisher("/uwb/pose", PoseWithCovarianceStamped, queue_size=10)
        self.status_pub = rospy.Publisher("/uwb_pose_status", String, queue_size=10)

        if self.heading_source not in ("imu", "uwb", "initial_imu"):
            rospy.logwarn("Invalid heading_source=%s. Falling back to imu.", self.heading_source)
            self.heading_source = "imu"

        rospy.Subscriber(self.uwb_pose_raw_topic, Pose2D, self.uwb_pose_callback)
        rospy.Subscriber(self.imu_topic, Imu, self.imu_callback)
        rospy.Subscriber(self.odom_topic, Odometry, self.odom_callback)
        rospy.Timer(rospy.Duration(1.0 / max(self.publish_rate, 1.0)), self.timer_callback)

        rospy.loginfo(
            "uwb_imu_pose_publisher ready. raw=%s imu=%s odom=%s heading_source=%s initial_heading_deg=%.1f odom_prediction=%s offset=%.3f auto_cal=%s samples=%d allow_stale_uwb=%s",
            self.uwb_pose_raw_topic,
            self.imu_topic,
            self.odom_topic,
            self.heading_source,
            self.initial_heading_deg,
            self.use_odom_prediction,
            self.imu_yaw_offset,
            self.auto_calibrate_yaw_offset,
            self.auto_calibrate_sample_count,
            self.allow_stale_uwb,
        )

    def uwb_pose_callback(self, msg):
        with self.lock:
            valid, status = self.validate_uwb_pose_locked(msg)
            if not valid:
                self.publish_status(status)
                return
            self.latest_uwb_pose = msg
            self.latest_uwb_time = rospy.Time.now()
            self.last_accepted_uwb_pose = msg
            self.correct_fused_pose_locked(msg, self.latest_uwb_time)
            self.try_auto_calibrate_locked()

    def imu_callback(self, msg):
        yaw = self.yaw_from_imu(msg)
        if yaw is None:
            self.publish_status("IMU_QUATERNION_INVALID")
            return
        if self.invert_imu_yaw:
            yaw = -yaw

        with self.lock:
            self.latest_imu_yaw = normalize_angle(yaw)
            self.latest_imu_time = rospy.Time.now()
            self.try_initial_heading_calibrate_locked()
            self.try_auto_calibrate_locked()

    def odom_callback(self, msg):
        with self.lock:
            self.latest_odom_linear = float(msg.twist.twist.linear.x)
            self.latest_odom_angular = float(msg.twist.twist.angular.z)
            self.latest_odom_time = rospy.Time.now()

    def validate_uwb_pose_locked(self, msg):
        if not all(math.isfinite(value) for value in (msg.x, msg.y, msg.theta)):
            return False, "UWB_POSE_INVALID"
        if not self.pose_inside_soft_bounds(msg):
            return False, "UWB_POSE_OUT_OF_BOUNDS"
        if self.pose_on_solver_boundary(msg):
            return False, "UWB_POSE_BOUNDARY_CLAMP_REJECTED"
        if math.hypot(msg.x, msg.y) < self.invalid_origin_radius:
            return False, "UWB_POSE_ORIGIN_REJECTED"

        reference = self.last_accepted_uwb_pose
        if not self.require_pose_stability:
            return True, "UWB_POSE_OK"
        if reference is None:
            return self.accept_after_stability(msg, "UWB_POSE_STABLE", "UWB_POSE_WAIT_STABLE")

        jump = math.hypot(msg.x - reference.x, msg.y - reference.y)
        if jump <= self.max_pose_jump:
            self.pending_uwb_pose = None
            self.pending_uwb_count = 0
            return True, "UWB_POSE_OK"

        return self.accept_after_stability(msg, "UWB_POSE_RECOVERED", "UWB_POSE_JUMP_WAIT")

    def accept_after_stability(self, msg, accepted_status, waiting_status):
        if self.pending_uwb_pose is None:
            self.pending_uwb_pose = msg
            self.pending_uwb_count = 1
            return False, waiting_status

        jump = math.hypot(msg.x - self.pending_uwb_pose.x, msg.y - self.pending_uwb_pose.y)
        if jump <= self.stable_pose_radius:
            self.pending_uwb_count += 1
        else:
            self.pending_uwb_pose = msg
            self.pending_uwb_count = 1

        if self.pending_uwb_count >= self.stable_pose_samples_required:
            self.pending_uwb_pose = None
            self.pending_uwb_count = 0
            return True, accepted_status
        return False, waiting_status

    def correct_fused_pose_locked(self, uwb_pose, stamp):
        heading = self.heading_from_sources_locked(uwb_pose)
        if self.fused_pose is None:
            self.fused_pose = Pose2D(x=float(uwb_pose.x), y=float(uwb_pose.y), theta=heading)
            self.last_prediction_time = stamp
            return

        alpha = self.clamp(self.uwb_correction_alpha, 0.0, 1.0)
        self.fused_pose.x = alpha * float(uwb_pose.x) + (1.0 - alpha) * self.fused_pose.x
        self.fused_pose.y = alpha * float(uwb_pose.y) + (1.0 - alpha) * self.fused_pose.y

        heading_alpha = self.clamp(self.heading_correction_alpha, 0.0, 1.0)
        heading_error = normalize_angle(heading - self.fused_pose.theta)
        self.fused_pose.theta = normalize_angle(self.fused_pose.theta + heading_alpha * heading_error)
        self.last_prediction_time = stamp

    def heading_from_sources_locked(self, uwb_pose):
        if self.heading_source == "uwb":
            return normalize_angle(float(uwb_pose.theta))
        if self.latest_imu_yaw is not None:
            return normalize_angle(self.latest_imu_yaw + self.imu_yaw_offset)
        return normalize_angle(float(uwb_pose.theta))

    def try_initial_heading_calibrate_locked(self):
        if self.heading_source != "initial_imu" or self.yaw_offset_calibrated:
            return
        if self.latest_imu_yaw is None:
            return
        initial_heading = math.radians(self.initial_heading_deg)
        self.imu_yaw_offset = normalize_angle(initial_heading - self.latest_imu_yaw)
        self.yaw_offset_calibrated = True
        rospy.loginfo(
            "Initial heading calibrated: initial_heading=%.1f deg imu_yaw=%.6f offset=%.6f",
            self.initial_heading_deg,
            self.latest_imu_yaw,
            self.imu_yaw_offset,
        )

    def try_auto_calibrate_locked(self):
        if self.yaw_offset_calibrated:
            return
        if self.heading_source == "initial_imu":
            return
        if self.latest_uwb_pose is None or self.latest_imu_yaw is None:
            return
        offset_sample = normalize_angle(float(self.latest_uwb_pose.theta) - self.latest_imu_yaw)
        self.calibration_samples.append(
            (
                float(self.latest_uwb_pose.x),
                float(self.latest_uwb_pose.y),
                offset_sample,
            )
        )
        if len(self.calibration_samples) > self.auto_calibrate_sample_count:
            self.calibration_samples.pop(0)
        if len(self.calibration_samples) < self.auto_calibrate_sample_count:
            return

        position_std = self.position_std(self.calibration_samples)
        if position_std > self.auto_calibrate_max_position_std:
            self.calibration_samples = self.calibration_samples[-1:]
            rospy.logwarn(
                "Yaw auto-calibration reset: UWB position moved too much (std=%.3f m)",
                position_std,
            )
            return

        sin_sum = sum(math.sin(sample[2]) for sample in self.calibration_samples)
        cos_sum = sum(math.cos(sample[2]) for sample in self.calibration_samples)
        resultant = math.hypot(sin_sum, cos_sum) / float(len(self.calibration_samples))
        if resultant < self.auto_calibrate_min_resultant:
            rospy.logwarn_throttle(
                2.0,
                "Yaw auto-calibration waiting for stable UWB heading (resultant=%.3f)",
                resultant,
            )
            return

        self.imu_yaw_offset = math.atan2(sin_sum, cos_sum)
        self.yaw_offset_calibrated = True
        rospy.loginfo(
            "Auto-calibrated IMU yaw offset: %.6f rad from %d samples (resultant=%.3f, pos_std=%.3f)",
            self.imu_yaw_offset,
            len(self.calibration_samples),
            resultant,
            position_std,
        )

    def timer_callback(self, _event):
        pose, status = self.build_pose()
        if pose is None:
            self.publish_status(status)
            return
        self.pose_pub.publish(pose)
        self.debug_pose_pub.publish(self.to_covariance_pose(pose))
        self.publish_status(status)

    def build_pose(self):
        now = rospy.Time.now()
        with self.lock:
            self.apply_odom_prediction_locked(now)
            uwb_pose = self.latest_uwb_pose
            uwb_time = self.latest_uwb_time
            imu_yaw = self.latest_imu_yaw
            imu_time = self.latest_imu_time
            yaw_offset = self.imu_yaw_offset
            fused_pose = self.copy_pose(self.fused_pose)
            odom_time = self.latest_odom_time

        if uwb_pose is None or uwb_time is None:
            return None, "UWB_TIMEOUT"
        uwb_age = now - uwb_time
        if uwb_age > self.uwb_timeout:
            if not self.allow_stale_uwb or uwb_age > self.max_stale_uwb_age:
                return None, "UWB_TIMEOUT"
            status = "UWB_ODOM_PREDICTED" if self.use_odom_prediction and fused_pose is not None else "UWB_STALE_REUSED"
        else:
            status = "UWB_ODOM_POSE_OK" if self.use_odom_prediction and fused_pose is not None else "UWB_IMU_POSE_OK"

        if self.use_odom_prediction and fused_pose is not None:
            if odom_time is None or now - odom_time > self.odom_timeout:
                status = "UWB_POSE_OK_ODOM_STALE" if uwb_age <= self.uwb_timeout else "ODOM_TIMEOUT"
                if uwb_age > self.uwb_timeout:
                    return None, status
            return fused_pose, status

        if self.heading_source == "uwb":
            theta = normalize_angle(float(uwb_pose.theta))
        else:
            if imu_yaw is None or imu_time is None or now - imu_time > self.imu_timeout:
                return None, "IMU_TIMEOUT"
            if self.heading_source == "initial_imu" and not self.yaw_offset_calibrated:
                return None, "INITIAL_HEADING_CALIBRATING"
            if self.auto_calibrate_yaw_offset and not self.yaw_offset_calibrated:
                return None, "YAW_AUTO_CALIBRATING"
            theta = normalize_angle(imu_yaw + yaw_offset)

        return Pose2D(
            x=float(uwb_pose.x),
            y=float(uwb_pose.y),
            theta=theta,
        ), status

    def apply_odom_prediction_locked(self, now):
        if not self.use_odom_prediction or self.fused_pose is None:
            return
        if self.latest_odom_time is None or now - self.latest_odom_time > self.odom_timeout:
            self.last_prediction_time = now
            return
        if self.last_prediction_time is None:
            self.last_prediction_time = now
            return

        dt = (now - self.last_prediction_time).to_sec()
        self.last_prediction_time = now
        if dt <= 0.0:
            return
        dt = min(dt, self.max_prediction_dt)

        linear = self.latest_odom_linear
        angular = self.latest_odom_angular
        theta_mid = self.fused_pose.theta + 0.5 * angular * dt
        self.fused_pose.x += linear * dt * math.cos(theta_mid)
        self.fused_pose.y += linear * dt * math.sin(theta_mid)
        self.fused_pose.theta = normalize_angle(self.fused_pose.theta + angular * dt)

    @staticmethod
    def copy_pose(pose):
        if pose is None:
            return None
        return Pose2D(x=float(pose.x), y=float(pose.y), theta=float(pose.theta))

    @staticmethod
    def position_std(samples):
        mean_x = sum(sample[0] for sample in samples) / float(len(samples))
        mean_y = sum(sample[1] for sample in samples) / float(len(samples))
        variance = sum(
            (sample[0] - mean_x) ** 2 + (sample[1] - mean_y) ** 2
            for sample in samples
        ) / float(len(samples))
        return math.sqrt(variance)

    @staticmethod
    def clamp(value, lower, upper):
        return max(lower, min(value, upper))

    def pose_inside_soft_bounds(self, pose):
        return (
            self.room_min_x - self.pose_bounds_margin <= pose.x <= self.room_max_x + self.pose_bounds_margin
            and self.room_min_y - self.pose_bounds_margin <= pose.y <= self.room_max_y + self.pose_bounds_margin
        )

    def pose_on_solver_boundary(self, pose):
        if self.boundary_clamp_margin <= 0.0:
            return False
        return (
            pose.x <= self.room_min_x + self.boundary_clamp_margin
            or pose.x >= self.room_max_x - self.boundary_clamp_margin
            or pose.y <= self.room_min_y + self.boundary_clamp_margin
            or pose.y >= self.room_max_y - self.boundary_clamp_margin
        )

    @staticmethod
    def yaw_from_imu(msg):
        q = msg.orientation
        if not all(math.isfinite(value) for value in (q.x, q.y, q.z, q.w)):
            return None
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def to_covariance_pose(self, pose2d):
        msg = PoseWithCovarianceStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = self.frame_id
        msg.pose.pose.position.x = pose2d.x
        msg.pose.pose.position.y = pose2d.y
        msg.pose.pose.position.z = 0.0
        half_yaw = pose2d.theta * 0.5
        msg.pose.pose.orientation.z = math.sin(half_yaw)
        msg.pose.pose.orientation.w = math.cos(half_yaw)
        msg.pose.covariance[0] = 0.05 * 0.05
        msg.pose.covariance[7] = 0.05 * 0.05
        msg.pose.covariance[35] = math.radians(5.0) ** 2
        return msg

    def publish_status(self, status):
        if status != self.last_status:
            rospy.loginfo("uwb_imu_pose_publisher status: %s", status)
            self.last_status = status
        self.status_pub.publish(String(data=status))


if __name__ == "__main__":
    try:
        UwbImuPosePublisher()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
