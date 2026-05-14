# System Architecture

ROS topics:

- `/uwb/ranges`: raw UWB ranges.
- `/uwb_pose`: estimated robot pose in the UWB coordinate frame.
- `/target_charger`: selected charger coordinate.
- `/scan`: LiDAR scan.
- `/cmd_vel`: velocity command.
- `/lidar_state`: local planner state.
- `/near_charger`: handoff flag for final docking.
- `/uwb_path`, `/uwb_markers`: RViz visualization.
