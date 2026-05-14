# Remote Codex Workflow

This workflow is for Windows Codex plus a future TurtleBot Ubuntu machine.

## Current No-Robot Phase

Use offline launch:

```bash
roslaunch turtlebot_charging_project offline_research_test.launch
```

Use Gazebo launch if the Ubuntu machine has Gazebo:

```bash
roslaunch turtlebot_charging_project gazebo_mapless_test.launch
```

## Future TurtleBot Phase

On the TurtleBot:

```bash
cd ~/catkin_ws/src
git clone https://github.com/taegon6/UWB.git turtlebot_charging_project
cd ~/catkin_ws
catkin_make
source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
```

Run the real robot pipeline:

```bash
export ROS_MASTER_URI=http://172.20.10.8:11311
export ROS_IP=172.20.10.8
export TURTLEBOT3_MODEL=waffle_pi
roslaunch turtlebot_charging_project real_robot.launch
```

Keep code changes on GitHub. The robot should pull and rebuild:

```bash
cd ~/catkin_ws/src/turtlebot_charging_project
git pull
cd ~/catkin_ws
catkin_make
```

Do not let Codex run physical driving unattended. Codex can build, launch, monitor topics, and analyze bags, but a person should be next to the robot during motion tests.
