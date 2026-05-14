% Export a short text summary that can be pasted into Codex.

inputFile = fullfile('data', 'raw', 'uwb_log_latest.csv');
summaryFile = fullfile('data', 'processed', 'codex_uwb_summary.txt');

T = readtable(inputFile);
lines = strings(0);
lines(end + 1) = "UWB log summary";
lines(end + 1) = "Rows: " + height(T);
lines(end + 1) = "Columns: " + strjoin(string(T.Properties.VariableNames), ", ");

if all(ismember({'uwb_x','uwb_y'}, T.Properties.VariableNames))
    lines(end + 1) = sprintf("uwb_x std: %.3f", std(T.uwb_x, 'omitnan'));
    lines(end + 1) = sprintf("uwb_y std: %.3f", std(T.uwb_y, 'omitnan'));
end

if ~exist(fullfile('data', 'processed'), 'dir')
    mkdir(fullfile('data', 'processed'));
end

writelines(lines, summaryFile);
disp("Wrote " + summaryFile);
