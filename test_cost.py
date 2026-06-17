import numpy as np
import math
from scipy.optimize import least_squares

anchors = np.array([[0.0, 0.0], [5.0, 0.0], [0.0, 5.0]])
HEIGHT_DIFF = 0.42
TAG_DISTANCE = 0.15
B = TAG_DISTANCE / 2.0

def compensate_height(d):
    return math.sqrt(d**2 - HEIGHT_DIFF**2) if d > HEIGHT_DIFF else 0.0

def compensate_distances(raw):
    return np.array([compensate_height(d) for d in raw])

def normalize_angle_rad(a):
    return math.atan2(math.sin(a), math.cos(a))

def rigid_body_error(params, df, db):
    cx, cy, theta = params
    c = np.array([cx, cy])
    u = np.array([math.cos(theta), math.sin(theta)])
    pf, pb = c + B * u, c - B * u
    mf, mb = compensate_distances(df), compensate_distances(db)
    ef = np.linalg.norm(anchors - pf, axis=1) - mf
    eb = np.linalg.norm(anchors - pb, axis=1) - mb
    return np.concatenate([ef, eb])

def get_best_initial_guess(df, db, sx, sy):
    best, min_cost = [sx, sy, 0.0], float('inf')
    for deg in range(-180, 180, 15):
        th = math.radians(deg)
        cost = np.sum(np.square(rigid_body_error([sx, sy, th], df, db)))
        if cost < min_cost:
            min_cost = cost
            best = [sx, sy, th]
    return np.array(best)

df = [3.57, 3.56, 3.58] # T2 (Front)
db = [3.64, 3.39, 3.62] # T1 (Back)

ROOM_MIN_X, ROOM_MAX_X = 0.0, 5.0
ROOM_MIN_Y, ROOM_MAX_Y = 0.0, 5.0

ig = get_best_initial_guess(df, db, 2.5, 2.5)
print(f"Initial guess: {ig[0]}, {ig[1]}, {math.degrees(ig[2])} deg")

result = least_squares(
    rigid_body_error, ig, args=(df, db),
    bounds=([ROOM_MIN_X, ROOM_MIN_Y, -np.pi],
            [ROOM_MAX_X, ROOM_MAX_Y,  np.pi]),
    loss='soft_l1', f_scale=0.1, max_nfev=50
)
rx, ry, rt = result.x
rt = normalize_angle_rad(rt)
print(f"Result: {rx}, {ry}, {math.degrees(rt)} deg, cost {result.cost}")
