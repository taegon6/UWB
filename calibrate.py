"""Calibration: collect 50 samples from each tag and compute per-anchor offset"""
import serial, time, math
import numpy as np

anchors = np.array([[0.0,0.0],[5.0,0.0],[0.0,5.0]])
REAL = np.array([2.5, 2.5])
HEIGHT_DIFF = 0.42

# Theoretical 3D distance from (2.5,2.5) at height diff 0.42
theo_3d = np.array([math.sqrt((REAL[0]-a[0])**2 + (REAL[1]-a[1])**2 + HEIGHT_DIFF**2) for a in anchors])
print(f"Theoretical 3D distances: {theo_3d}")

ser1 = serial.Serial('COM7', 115200, timeout=0.5)
ser2 = serial.Serial('COM5', 115200, timeout=0.5)
time.sleep(1.5)
ser1.reset_input_buffer()
ser2.reset_input_buffer()

t1_data = []  # list of [d1,d2,d3]
t2_data = []
TARGET = 60

print(f"Collecting {TARGET} samples per tag...")
start = time.time()
while (len(t1_data) < TARGET or len(t2_data) < TARGET) and time.time()-start < 60:
    for port, tag_id, store in [(ser1,1,t1_data),(ser2,2,t2_data)]:
        if port.in_waiting > 0:
            line = port.readline().decode('utf-8',errors='ignore').strip()
            if line.startswith(f"DIST,{tag_id}"):
                parts = line.split(',')
                if len(parts)==5:
                    try:
                        d = [float(parts[2]),float(parts[3]),float(parts[4])]
                        # reject obvious outliers
                        if all(0.5 < x < 8.0 for x in d):
                            store.append(d)
                            if len(store) % 10 == 0:
                                print(f"  Tag{tag_id}: {len(store)}/{TARGET}")
                    except: pass
    time.sleep(0.01)

ser1.close()
ser2.close()

t1 = np.array(t1_data)
t2 = np.array(t2_data)

print(f"\nTag1 samples: {len(t1)}, Tag2 samples: {len(t2)}")
print("="*60)

for tag_name, data in [("Tag1(COM7)", t1), ("Tag2(COM5)", t2)]:
    if len(data) == 0:
        continue
    mean = np.mean(data, axis=0)
    std = np.std(data, axis=0)
    offset = theo_3d - mean
    print(f"\n{tag_name}:")
    print(f"  Mean raw : A1={mean[0]:.3f}  A2={mean[1]:.3f}  A3={mean[2]:.3f}")
    print(f"  Std      : A1={std[0]:.3f}  A2={std[1]:.3f}  A3={std[2]:.3f}")
    print(f"  Offset   : A1={offset[0]:.3f}  A2={offset[1]:.3f}  A3={offset[2]:.3f}")
    print(f"  Corrected: A1={mean[0]+offset[0]:.3f}  A2={mean[1]+offset[1]:.3f}  A3={mean[2]+offset[2]:.3f}")
    print(f"  Theo 3D  : {theo_3d}")

print("\n" + "="*60)
avg_t1_offset = theo_3d - np.mean(t1, axis=0) if len(t1)>0 else [0,0,0]
avg_t2_offset = theo_3d - np.mean(t2, axis=0) if len(t2)>0 else [0,0,0]
global_offset = (avg_t1_offset + avg_t2_offset) / 2
print(f"\nRecommended global offset per anchor:")
print(f"  OFFSET_A1 = {global_offset[0]:.3f}")
print(f"  OFFSET_A2 = {global_offset[1]:.3f}")
print(f"  OFFSET_A3 = {global_offset[2]:.3f}")
