# Algorithm Description

The UWB pose estimator applies anchor bias correction, range jump rejection, residual-based outlier rejection, pose jump rejection, and smoothing.

The LiDAR local planner divides LaserScan data into front, front-left, front-right, left, and right sectors. It drives toward the UWB target when the front sector is clear, turns toward the side with more free space when an obstacle is detected, and stops when the target is within `goal_radius`.
