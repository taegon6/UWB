# TurtleBot Charging Project

This ROS1 Noetic package contains a LiDAR local planner for a TurtleBot3 Waffle Pi wireless charging project.

The planner does not build a SLAM map. UWB provides the robot pose and selected charger target, while LiDAR is used for real-time local obstacle avoidance.

In practice, keep the LiDAR sensor driver running and stop only the local-planner behavior when the robot reaches the charger area. Repeatedly power-cycling the LiDAR can add boot delay and unstable scan timing.

## Topics

Inputs:

- `/scan` (`sensor_msgs/LaserScan`)
- `/uwb_pose` (`geometry_msgs/Pose2D`)
- `/target_charger` (`geometry_msgs/Pose2D`)
- `/selected_charger_id` (`std_msgs/Int32`)
- `/uwb/ranges` (`std_msgs/Float32MultiArray`)

Outputs:

- `/cmd_vel` (`geometry_msgs/Twist`)
- `/lidar_state` (`std_msgs/String`)
- `/near_charger` (`std_msgs/Bool`)
- `/charger_target_status` (`std_msgs/String`)
- `/uwb_pose_status` (`std_msgs/String`)

When `/near_charger` becomes `true`, the local planner publishes zero velocity and the next stage can take over with camera alignment plus UWB distance checks.

## States

- `WAIT`
- `GO_TO_TARGET`
- `AVOID_LEFT`
- `AVOID_RIGHT`
- `EMERGENCY_STOP`
- `NEAR_CHARGER`
- `STALE_INPUT`

## Run

```bash
cd ~/catkin_ws
catkin_make
source devel/setup.bash
export ROS_MASTER_URI=http://172.20.10.8:11311
export ROS_IP=172.20.10.8
export TURTLEBOT3_MODEL=waffle_pi
roslaunch turtlebot_charging_project mapless_charging.launch
```

## Mapless Charging Flow

Use this package for the mapless UWB-LiDAR mode:

1. `/selected_charger_id` chooses charger 1 or 2.
2. `charger_target_selector.py` converts the selected ID to `/target_charger`.
3. `uwb_pose_estimator.py` converts `/uwb/ranges` plus `/odom` yaw to `/uwb_pose`.
4. `lidar_local_planner.py` uses `/scan`, `/uwb_pose`, and `/target_charger` to publish `/cmd_vel`.
5. When the robot is within `goal_radius`, it stops and publishes `/near_charger=true`.
6. Vision plus UWB docking takes over.

The LiDAR driver should stay running. The planner stops using LiDAR for driving after `NEAR_CHARGER`, but the physical LiDAR sensor does not need to be power-cycled.

## UWB Data Input

Recommended UWB raw input:

```text
/uwb/ranges: std_msgs/Float32MultiArray
data: [distance_to_anchor_0, distance_to_anchor_1, distance_to_anchor_2, distance_to_anchor_3]
```

Default anchor coordinates for the 5 m x 5 m test area are in `mapless_charging.launch`:

```text
anchor_0 = (0.0, 0.0)
anchor_1 = (5.0, 0.0)
anchor_2 = (0.0, 5.0)
anchor_3 = (5.0, 5.0)
```

If your UWB device already publishes robot pose directly, publish this instead and launch without the estimator:

```bash
roslaunch turtlebot_charging_project mapless_charging.launch use_uwb_estimator:=false
```

Then publish:

```text
/uwb_pose: geometry_msgs/Pose2D
x, y: UWB-estimated robot position
theta: odometry yaw or fused heading
```

## Manual Pose Test

If you want to bypass the UWB range estimator and inject pose directly, run:

```bash
roslaunch turtlebot_charging_project mapless_charging.launch use_uwb_estimator:=false
```

Then publish a fake UWB pose:

```bash
rostopic pub /uwb_pose geometry_msgs/Pose2D "x: 0.5
y: 0.5
theta: 0.0" -r 10
```

Check state:

```bash
rostopic echo /lidar_state
```

Manual selected charger test:

```bash
rostopic pub /selected_charger_id std_msgs/Int32 "data: 1" -1
```

## Manual UWB Range Test

If `use_uwb_estimator:=true`, publish fake distances to the four anchors:

```bash
rostopic pub /uwb/ranges std_msgs/Float32MultiArray "data: [0.71, 4.53, 4.53, 6.36]" -r 5
```

The example above is roughly a robot pose near `(0.5, 0.5)` when the anchors are at the four corners of a 5 m x 5 m area.

## TurtleBot3 Waffle Pi Flow

Keep these running first:

- `roscore`
- `roslaunch turtlebot3_bringup turtlebot3_robot.launch`
- this package's `mapless_charging.launch`

The LiDAR local planner runs from charger selection until the robot is within `goal_radius` of the target charger. At that point it stops `/cmd_vel`, publishes `/near_charger=true`, and the camera plus UWB docking process can take over.

Recommended first test layout for a 5 m x 5 m space:

- one obstacle near the start area
- one obstacle near the charger area
- avoid U-shaped or dead-end obstacle layouts for this local-only planner
