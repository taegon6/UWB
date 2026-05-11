#!/usr/bin/env python3

import rospy
from geometry_msgs.msg import Pose2D
from std_msgs.msg import Int32, String


class ChargerTargetSelector:
    def __init__(self):
        rospy.init_node("charger_target_selector")

        self.chargers = self.load_chargers()
        self.target_pub = rospy.Publisher("/target_charger", Pose2D, queue_size=1, latch=True)
        self.status_pub = rospy.Publisher("/charger_target_status", String, queue_size=10)

        rospy.Subscriber("/selected_charger_id", Int32, self.selected_callback)
        rospy.loginfo("charger_target_selector ready. chargers=%s", sorted(self.chargers.keys()))

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
            if len(item) < 3:
                rospy.logwarn("Ignoring invalid charger entry: %s", item)
                continue

            charger_id = int(item[0])
            chargers[charger_id] = Pose2D(x=float(item[1]), y=float(item[2]), theta=0.0)

        return chargers

    def selected_callback(self, msg):
        charger_id = int(msg.data)
        target = self.chargers.get(charger_id)

        if target is None:
            status = "UNKNOWN_CHARGER_ID: {}".format(charger_id)
            rospy.logwarn(status)
            self.status_pub.publish(String(data=status))
            return

        self.target_pub.publish(target)
        self.status_pub.publish(String(data="TARGET_SELECTED: {}".format(charger_id)))
        rospy.loginfo("Selected charger %d at x=%.2f y=%.2f", charger_id, target.x, target.y)


if __name__ == "__main__":
    try:
        ChargerTargetSelector()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
