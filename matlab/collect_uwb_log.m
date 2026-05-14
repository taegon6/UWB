% Collect ROS topics and export a MATLAB-friendly UWB log CSV.
% Run this from MATLAB after connecting to the ROS master.

durationSec = 30;
outputFile = fullfile('data', 'raw', ['uwb_log_' datestr(now, 'yyyymmdd_HHMMSS') '.csv']);

uwbPoseSub = rossubscriber('/uwb_pose', 'geometry_msgs/Pose2D');
odomSub = rossubscriber('/odom', 'nav_msgs/Odometry');
cmdSub = rossubscriber('/cmd_vel', 'geometry_msgs/Twist');
stateSub = rossubscriber('/lidar_state', 'std_msgs/String');
nearSub = rossubscriber('/near_charger', 'std_msgs/Bool');

rows = {};
tic;
while toc < durationSec
    uwbPose = uwbPoseSub.LatestMessage;
    odom = odomSub.LatestMessage;
    cmd = cmdSub.LatestMessage;
    state = stateSub.LatestMessage;
    near = nearSub.LatestMessage;

    if isempty(uwbPose) || isempty(odom) || isempty(cmd)
        pause(0.05);
        continue;
    end

    q = odom.Pose.Pose.Orientation;
    yaw = atan2(2.0 * (q.W * q.Z + q.X * q.Y), 1.0 - 2.0 * (q.Y * q.Y + q.Z * q.Z));
    lidarState = "";
    nearCharger = false;
    if ~isempty(state)
        lidarState = string(state.Data);
    end
    if ~isempty(near)
        nearCharger = near.Data;
    end

    rows(end + 1, :) = { ...
        string(datetime('now', 'Format', 'yyyy-MM-dd''T''HH:mm:ss.SSS')), ...
        NaN, NaN, ...
        odom.Pose.Pose.Position.X, odom.Pose.Pose.Position.Y, yaw, ...
        NaN, NaN, NaN, NaN, ...
        uwbPose.X, uwbPose.Y, ...
        cmd.Linear.X, cmd.Angular.Z, ...
        lidarState, nearCharger, NaN}; %#ok<SAGROW>

    pause(0.05);
end

header = {'time','true_x','true_y','odom_x','odom_y','odom_yaw', ...
    'range_a0','range_a1','range_a2','range_a3', ...
    'uwb_x','uwb_y','cmd_linear','cmd_angular', ...
    'lidar_state','near_charger','selected_charger_id'};

if ~exist(fullfile('data', 'raw'), 'dir')
    mkdir(fullfile('data', 'raw'));
end

writecell([header; rows], outputFile);
disp("Wrote " + outputFile);
