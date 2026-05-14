% Basic MATLAB-side view of a UWB log.

inputFile = fullfile('data', 'raw', 'uwb_log_latest.csv');
T = readtable(inputFile);

if all(ismember({'true_x','true_y','uwb_x','uwb_y'}, T.Properties.VariableNames))
    valid = ~isnan(T.true_x) & ~isnan(T.true_y) & ~isnan(T.uwb_x) & ~isnan(T.uwb_y);
    err = hypot(T.uwb_x(valid) - T.true_x(valid), T.uwb_y(valid) - T.true_y(valid));
    fprintf('UWB position error mean: %.3f m\n', mean(err));
    fprintf('UWB position error std : %.3f m\n', std(err));
end

if all(ismember({'uwb_x','uwb_y'}, T.Properties.VariableNames))
    figure;
    plot(T.uwb_x, T.uwb_y, '.-');
    axis equal;
    grid on;
    title('UWB pose path');
    xlabel('x [m]');
    ylabel('y [m]');
end
