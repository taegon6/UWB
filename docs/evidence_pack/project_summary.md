# Project Summary

This project implements the UWB-LiDAR approach phase of a TurtleBot3 Waffle Pi autonomous wireless charging system.

System sequence:

1. UWB estimates robot pose and selects one of two charging stations.
2. LiDAR local planner drives toward the selected charger while avoiding nearby obstacles.
3. The robot stops approximately 1 m before the charger target.
4. Future QR vision alignment and mechanical guidance can take over for final 10 cm docking.

Code version:

```text
c267adbeeadd8aca1641bcbc0b1e617cb46f7e68
```
