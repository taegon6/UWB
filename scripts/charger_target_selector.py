#!/usr/bin/env python3

import math

import rospy
from geometry_msgs.msg import Pose2D
from std_msgs.msg import Int32, String


class ChargerTargetSelector:
    def __init__(self):
        rospy.init_node("charger_target_selector")

        self.chargers = self.load_chargers()
        self.default_charger_id = rospy.get_param("~default_charger_id", 0)
        self.auto_publish_nearest = rospy.get_param("~auto_publish_nearest", False)
        self.auto_publish_rate = rospy.get_param("~auto_publish_rate", 1.0)
        self.latch_auto_target = rospy.get_param("~latch_auto_target", True)
        self.robot_pose_timeout = rospy.Duration(rospy.get_param("~robot_pose_timeout", 2.0))
        self.last_robot_pose = None
        self.last_robot_pose_time = None
        self.last_auto_charger_id = None
        self.selected_charger_id = None

        self.target_pub = rospy.Publisher("/target_charger", Pose2D, queue_size=1, latch=True)
        self.status_pub = rospy.Publisher("/charger_target_status", String, queue_size=10)

        rospy.Subscriber("/selected_charger_id", Int32, self.selected_callback)
        rospy.Subscriber("/uwb_pose", Pose2D, self.uwb_pose_callback)
        rospy.loginfo(
            "charger_target_selector ready. chargers=%s auto_publish_nearest=%s",
            sorted(self.chargers.keys()),
            self.auto_publish_nearest,
        )
        if self.default_charger_id:
            rospy.Timer(rospy.Duration(0.5), self.default_timer_callback, oneshot=True)
        if self.auto_publish_nearest:
            rospy.Timer(rospy.Duration(1.0 / max(self.auto_publish_rate, 0.1)), self.auto_timer_callback)

    def load_chargers(self):
        raw_chargers = rospy.get_param(
            "~chargers",
            [
                [1, 4.0, 1.2],
                [2, 4.0, 3.8],
            ],
        )

        chargers = {}
        for item in raw_chargers:
            try:
                if isinstance(item, dict):
                    charger_id = int(item.get("charger_id", item.get("id")))
                    x = float(item["x"])
                    y = float(item["y"])
                else:
                    if len(item) < 3:
                        rospy.logwarn("Ignoring invalid charger entry: %s", item)
                        continue
                    charger_id = int(item[0])
                    x = float(item[1])
                    y = float(item[2])
            except (TypeError, ValueError, KeyError) as exc:
                rospy.logwarn("Ignoring invalid charger entry %s: %s", item, exc)
                continue

            chargers[charger_id] = Pose2D(x=x, y=y, theta=0.0)

        return chargers

    def selected_callback(self, msg):
        charger_id = int(msg.data)
        self.publish_target(charger_id)

    def uwb_pose_callback(self, msg):
        self.last_robot_pose = msg
        self.last_robot_pose_time = rospy.Time.now()

    def default_timer_callback(self, _event):
        self.publish_target(int(self.default_charger_id))

    def auto_timer_callback(self, _event):
        if self.latch_auto_target and self.selected_charger_id is not None:
            return
        if self.last_robot_pose is None or self.last_robot_pose_time is None:
            self.status_pub.publish(String(data="AUTO_WAIT_UWB_POSE"))
            return
        if rospy.Time.now() - self.last_robot_pose_time > self.robot_pose_timeout:
            self.status_pub.publish(String(data="AUTO_UWB_POSE_TIMEOUT"))
            return

        charger_id = self.nearest_charger_id(self.last_robot_pose)
        if charger_id is None:
            self.status_pub.publish(String(data="AUTO_NO_VALID_CHARGER"))
            return

        self.publish_target(charger_id, reason="AUTO_NEAREST")

    def nearest_charger_id(self, robot_pose):
        if not self.chargers:
            return None
        return min(
            self.chargers.keys(),
            key=lambda charger_id: math.hypot(
                self.chargers[charger_id].x - robot_pose.x,
                self.chargers[charger_id].y - robot_pose.y,
            ),
        )

    def publish_target(self, charger_id, reason="MANUAL"):
        target = self.chargers.get(charger_id)

        if target is None:
            status = "UNKNOWN_CHARGER_ID: {}".format(charger_id)
            rospy.logwarn(status)
            self.status_pub.publish(String(data=status))
            return

        self.target_pub.publish(target)
        self.status_pub.publish(String(data="TARGET_SELECTED: {} reason={}".format(charger_id, reason)))
        if charger_id != self.last_auto_charger_id or reason != "AUTO_NEAREST":
            rospy.loginfo(
                "Selected charger %d at x=%.2f y=%.2f reason=%s",
                charger_id,
                target.x,
                target.y,
                reason,
            )
        self.last_auto_charger_id = charger_id
        self.selected_charger_id = charger_id


if __name__ == "__main__":
    try:
        ChargerTargetSelector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
