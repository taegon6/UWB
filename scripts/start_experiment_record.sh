#!/usr/bin/env bash
set -euo pipefail

source /opt/ros/noetic/setup.bash
source "$HOME/catkin_ws/devel/setup.bash"

export ROS_MASTER_URI="${ROS_MASTER_URI:-http://172.20.10.8:11311}"
export ROS_IP="${ROS_IP:-172.20.10.8}"

bag_dir="$HOME/catkin_ws/src/turtlebot_charging_project/data/rosbag"
mkdir -p "$bag_dir"

label="${1:-uwb_lidar_charging}"
stamp="$(date +%Y%m%d_%H%M%S)"
bag_name="${stamp}_${label}"

echo "Recording experiment rosbag:"
echo "  output: $bag_dir/$bag_name*.bag"
echo "  stop:   Ctrl+C"

exec rosbag record \
  --buffsize=512 \
  --split \
  --duration=10m \
  -O "$bag_dir/$bag_name" \
  /uwb/pose_raw \
  /uwb/pose \
  /uwb_pose \
  /uwb_pose_status \
  /target_charger \
  /charger_target_status \
  /scan \
  /odom \
  /imu \
  /cmd_vel \
  /lidar_state \
  /near_charger \
  /battery_state \
  /joint_states \
  /tf \
  /tf_static
