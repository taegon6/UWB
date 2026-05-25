#!/usr/bin/env python3

import argparse
import time

import serial


def read_port(port, baud, lines, warmup):
    print("--- {}".format(port), flush=True)
    try:
        ser = serial.Serial(port, baud, timeout=0.2)
        time.sleep(warmup)
        for _ in range(lines):
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                print(line, flush=True)
        ser.close()
    except Exception as exc:
        print("ERROR: {}".format(exc), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ports", nargs="+")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--lines", type=int, default=20)
    parser.add_argument("--warmup", type=float, default=1.0)
    args = parser.parse_args()

    for port in args.ports:
        read_port(port, args.baud, args.lines, args.warmup)


if __name__ == "__main__":
    main()
