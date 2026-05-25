# Experiment Logging

Use this when running the UWB-LiDAR charging workflow and you want data that can be replayed or analyzed later.

## Automatic Recording

The real robot workflow starts rosbag recording automatically:

```bash
roslaunch turtlebot_charging_project real_uwb_mapless_charging.launch
```

To run without recording:

```bash
roslaunch turtlebot_charging_project real_uwb_mapless_charging.launch record_experiment:=false
```

To change the log label:

```bash
roslaunch turtlebot_charging_project real_uwb_mapless_charging.launch record_label:=test01
```

## Start Recording

Use this only when you want to record separately from the main launch:

```bash
rosrun turtlebot_charging_project start_experiment_record.sh test01
```

The bag is saved under:

```text
~/catkin_ws/src/turtlebot_charging_project/data/rosbag
```

Stop recording with `Ctrl+C`.

## Launch Alternative

```bash
mkdir -p ~/catkin_ws/src/turtlebot_charging_project/data/rosbag
roslaunch turtlebot_charging_project record_experiment.launch bag_name:=test01
```

## Recorded Topics

```text
/uwb/pose_raw
/uwb/pose
/uwb_pose
/uwb_pose_status
/target_charger
/charger_target_status
/scan
/odom
/imu
/cmd_vel
/lidar_state
/near_charger
/battery_state
/joint_states
/tf
/tf_static
```

## Inspect A Bag

```bash
rosbag info ~/catkin_ws/src/turtlebot_charging_project/data/rosbag/test01*.bag
```

## Replay A Bag

```bash
rosbag play ~/catkin_ws/src/turtlebot_charging_project/data/rosbag/test01*.bag
```
