# Experiment Protocol

Use this protocol before the TurtleBot is connected.

## Offline Logic Test

Run only ROS core plus fake topics:

```bash
roslaunch turtlebot_charging_project offline_research_test.launch
```

Expected:

```bash
rostopic echo /uwb_pose
rostopic echo /target_charger
rostopic echo /scan
rostopic echo /lidar_state
rostopic echo /cmd_vel
```

Set `obstacle_distance:=0.40` to force avoidance:

```bash
roslaunch turtlebot_charging_project offline_research_test.launch obstacle_distance:=0.40
```

Set `obstacle_distance:=2.0` to test target-following behavior.

## Gazebo Test

```bash
roslaunch turtlebot_charging_project gazebo_mapless_test.launch
```

Check:

```bash
rostopic echo /lidar_state
rostopic echo /near_charger
rostopic echo /cmd_vel
```

## Real Robot Entry Criteria

Do not run real driving until all are true:

- `python3 -m py_compile scripts/*.py tools/*.py` passes.
- `catkin_make` passes.
- `/scan` exists and has a stable rate near 9-10 Hz.
- `/uwb_pose` updates at least once every 2 seconds.
- `/target_charger` has the intended charger coordinate.
- `goal_radius` is set to 1.0 m for first tests.
- `max_linear` is reduced to 0.06 m/s for first floor tests.

## First Real Test

1. Lift the TurtleBot wheels off the ground.
2. Run `real_robot.launch`.
3. Confirm `/cmd_vel` direction and magnitude.
4. Put the robot on the floor only after a person is ready to stop it.
5. Record a rosbag.

Emergency stop:

```bash
rostopic pub /cmd_vel geometry_msgs/Twist "{}" -1
```
