"""Raw serial data reader - extended wait, try both ports"""
import serial
import time

ports = ['COM5', 'COM7']
sers = {}
for p in ports:
    try:
        s = serial.Serial(p, 115200, timeout=1.0)
        sers[p] = s
        print(f"[OK] {p} opened")
    except Exception as e:
        print(f"[FAIL] {p}: {e}")

time.sleep(2.0)
for s in sers.values():
    s.reset_input_buffer()

print("Waiting 30 seconds for data...")
print("=" * 70)

start = time.time()
count = 0
while time.time() - start < 30:
    for p, s in sers.items():
        try:
            if s.in_waiting > 0:
                raw = s.readline()
                line = raw.decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"[{p}] {line}")
                    count += 1
        except Exception as e:
            print(f"[ERR] {p}: {e}")
    time.sleep(0.005)

for s in sers.values():
    s.close()
print("=" * 70)
print(f"[DONE] {count} lines read in 30s")
