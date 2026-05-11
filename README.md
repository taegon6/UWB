# UWB Charging TurtleBot

This ROS1 package contains a LiDAR local planner for a TurtleBot wireless charging project.

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
roslaunch uwb_charging lidar_local_planner.launch
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
