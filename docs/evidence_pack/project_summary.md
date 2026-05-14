# Project Summary

This project implements a mapless TurtleBot3 Waffle Pi wireless charging approach.

System sequence:

1. UWB estimates robot pose and provides charger target coordinates.
2. LiDAR local planner drives toward the target while avoiding nearby obstacles.
3. The robot stops approximately 1 m before the charger target.
4. Vision and UWB docking can take over for final alignment.

Code version:

```text
b07368febd506028e5bd76d176124619acccaf2c
```
