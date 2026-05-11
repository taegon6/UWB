# TurtleBot Charging Project

This ROS1 Noetic package contains a LiDAR local planner for a TurtleBot3 Waffle Pi wireless charging project.

The planner does not build a SLAM map. UWB provides the robot pose and selected charger target, while LiDAR is used for real-time local obstacle avoidance.

In practice, keep the LiDAR sensor driver running and stop only the local-planner behavior when the robot reaches the charger area. Repeatedly power-cycling the LiDAR can add boot delay and unstable scan timing.

## Topics

Inputs:

- `/scan` (`sensor_msgs/LaserScan`)
- `/uwb_pose` (`geometry_msgs/Pose2D`)
- `/target_charger` (`geometry_msgs/Pose2D`)

Outputs:

- `/cmd_vel` (`geometry_msgs/Twist`)
- `/lidar_state` (`std_msgs/String`)
- `/near_charger` (`std_msgs/Bool`)

When `/near_charger` becomes `true`, the local planner publishes zero velocity and the next stage can take over with camera alignment plus UWB distance checks.

## States

- `WAIT`
- `GO_TO_TARGET`
- `AVOID_LEFT`
- `AVOID_RIGHT`
- `EMERGENCY_STOP`
- `NEAR_CHARGER`

## Run

```bash
cd ~/catkin_ws
catkin_make
source devel/setup.bash
export ROS_MASTER_URI=http://172.20.10.8:11311
export ROS_IP=172.20.10.8
export TURTLEBOT3_MODEL=waffle_pi
roslaunch turtlebot_charging_project lidar_local_planner.launch
```

## Manual UWB Test

```bash
rostopic pub /uwb_pose geometry_msgs/Pose2D "x: 0.5
y: 0.5
theta: 0.0" -r 10
```

```bash
rostopic pub /target_charger geometry_msgs/Pose2D "x: 4.0
y: 1.2
theta: 0.0" -r 1
```

Check state:

```bash
rostopic echo /lidar_state
```

## TurtleBot3 Waffle Pi Flow

Keep these running first:

- `roscore`
- `roslaunch turtlebot3_bringup turtlebot3_robot.launch`
- this package's `lidar_local_planner.launch`

The LiDAR local planner runs from charger selection until the robot is within `goal_radius` of the target charger. At that point it stops `/cmd_vel`, publishes `/near_charger=true`, and the camera plus UWB docking process can take over.

Recommended first test layout for a 5 m x 5 m space:

- one obstacle near the start area
- one obstacle near the charger area
- avoid U-shaped or dead-end obstacle layouts for this local-only planner
