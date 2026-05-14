# Project Context

This repository is for a TurtleBot3 Waffle autonomous wireless charging project.

The original student project guide defines the full system goal as an autonomous TurtleBot charging sequence:

1. Monitor battery status.
2. Estimate TurtleBot position using four UWB anchors.
3. Select the nearest of two charging stations.
4. Navigate near the selected charging station using LiDAR.
5. Detect a QR marker near the charger using a camera.
6. Align with the charger using OpenCV.
7. Use a mechanical guide for final docking.
8. Start wireless charging.
9. Resume operation after charging.

The guide assigns these sensor roles:

- UWB: indoor robot localization and charger selection.
- LiDAR: navigation and obstacle avoidance.
- Camera: QR detection and visual alignment.
- Mechanical guide: final physical positioning.

The expected final docking tolerance is about 10 cm after the camera and mechanical guide stages.

## Current Repository Scope

This repository currently focuses on the UWB-LiDAR approach phase before final QR docking.

The current implementation deliberately differs from the original guide in one important way:

- Original guide: perform SLAM once, save a map, then use the stored map for navigation.
- Current implementation: do not depend on a SLAM map for the first approach phase. UWB provides the robot pose and charger target coordinate, while LiDAR is used as a real-time local obstacle avoidance sensor.

Current implemented sequence:

1. Receive robot pose from `/uwb_pose`, or estimate it from `/uwb/ranges` plus `/odom`.
2. Receive/select charger target coordinate as `/target_charger`.
3. Drive toward the target using UWB heading error.
4. Use `/scan` to avoid simple box-like obstacles in real time.
5. Stop when the robot is within 1.0 m of the charger target.
6. Publish `/near_charger=true` so the future QR docking stage can take over.

## Research Framing

The research angle is not only "make the robot move." The intended research workflow is:

```text
MATLAB/ROS measurement logs
  -> UWB bias and stability analysis
  -> calibration YAML generation
  -> ROS UWB estimator update
  -> offline/Gazebo/rosbag validation
  -> low-speed TurtleBot experiment
  -> evidence pack for report or paper writing
```

This means the report should describe a data-driven calibration workflow for UWB-assisted mapless local approach toward a wireless charging station, with LiDAR providing local collision avoidance before QR-based final docking.

## What AI Writing Must Preserve

When using GPT/Codex to draft a report or paper:

- Do not claim that final QR docking is implemented unless it has been added and tested.
- Do not claim that wireless charging is completed unless hardware charging tests are recorded.
- Do not claim global map-based navigation if the experiment used the current mapless planner.
- Clearly state that the current local planner is suitable for simple avoidable obstacles, not U-shaped traps or dead ends.
- Use measured metrics from `summary_metrics.csv`, experiment manifests, and figures only.
