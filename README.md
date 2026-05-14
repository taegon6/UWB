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

## Gazebo Verification

You can verify the mapless planner in Gazebo before running the real TurtleBot.

Install TurtleBot3 Gazebo packages if they are missing:

```bash
sudo apt update
sudo apt install -y ros-noetic-turtlebot3-gazebo
```

Then run:

```bash
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
export TURTLEBOT3_MODEL=waffle_pi
roslaunch turtlebot_charging_project gazebo_mapless_test.launch
```

This launch starts:

- TurtleBot3 Waffle Pi in Gazebo
- a 5 m x 5 m style test world with two box obstacles and two charger markers
- `sim_uwb_pose_from_odom.py`, which publishes fake `/uwb_pose` from Gazebo `/odom`
- `charger_target_selector.py`, which automatically selects charger 1
- `lidar_local_planner.py`, which publishes `/cmd_vel`

Expected checks:

```bash
rostopic hz /scan
rostopic echo /uwb_pose
rostopic echo /target_charger
rostopic echo /lidar_state
rostopic echo /near_charger
```

Expected state flow:

```text
GO_TO_TARGET
AVOID_LEFT or AVOID_RIGHT when a box is in front
GO_TO_TARGET after the front sector clears
NEAR_CHARGER when the robot enters the 1.0 m charger radius
```

To test charger 2 instead:

```bash
roslaunch turtlebot_charging_project gazebo_mapless_test.launch default_charger_id:=2
```

If Gazebo is too heavy over VNC, run without the GUI:

```bash
roslaunch turtlebot_charging_project gazebo_mapless_test.launch gui:=false
```

## Mapless Charging Flow

Use this package for the mapless UWB-LiDAR mode:

1. `/selected_charger_id` chooses charger 1 or 2.
2. `charger_target_selector.py` converts the selected ID to `/target_charger`.
3. `uwb_pose_estimator.py` converts `/uwb/ranges` plus `/odom` yaw to `/uwb_pose`.
4. `lidar_local_planner.py` uses `/scan`, `/uwb_pose`, and `/target_charger` to publish `/cmd_vel`.
5. When the robot is within `goal_radius` (default 1.0 m), it stops and publishes `/near_charger=true`.
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

## MATLAB Log Calibration Workflow

The UWB estimator can be calibrated from measured logs:

```bash
python3 tools/analyze_uwb_log.py \
  --input data/raw/uwb_log_2026_05_13_test01.csv \
  --output config/uwb_calibration.yaml
```

The analyzer expects the preferred MATLAB CSV columns when available:

```text
time,true_x,true_y,odom_x,odom_y,odom_yaw,
range_a0,range_a1,range_a2,range_a3,
uwb_x,uwb_y,cmd_linear,cmd_angular,
lidar_state,near_charger,selected_charger_id
```

It also tolerates the current experimental `cx_raw/cy_raw/cx_filtered/cy_filtered` logs, but those logs cannot calculate anchor range bias unless `true_x`, `true_y`, and `range_a*` columns are present.

`config/uwb_calibration.yaml` is loaded by `mapless_charging.launch` and controls:

- `anchor_bias`
- `smoothing_alpha`
- `max_range_jump`
- `max_pose_jump`
- `residual_threshold`
- `max_range`
- `min_valid_anchors`

## TurtleBot3 Waffle Pi Flow

Keep these running first:

- `roscore`
- `roslaunch turtlebot3_bringup turtlebot3_robot.launch`
- this package's `mapless_charging.launch`

The LiDAR local planner runs from charger selection until the robot is within `goal_radius` of the target charger. The default is 1.0 m, so the robot stops about 1 m before the charger target. At that point it stops `/cmd_vel`, publishes `/near_charger=true`, and the camera plus UWB docking process can take over.

During driving, `/uwb_pose` is read repeatedly. Each new UWB pose updates the robot's estimated `x`, `y`, and `theta`, and the planner recalculates the heading to `/target_charger`. Between UWB updates, the planner keeps using the latest valid pose. If UWB pose is not refreshed within `uwb_timeout` seconds, the planner stops with `STALE_INPUT`.

Recommended first test layout for a 5 m x 5 m space:

- one obstacle near the start area
- one obstacle near the charger area
- avoid U-shaped or dead-end obstacle layouts for this local-only planner
