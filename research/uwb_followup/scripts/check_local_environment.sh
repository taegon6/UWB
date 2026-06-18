#!/usr/bin/env bash
set -euo pipefail

check_cmd() {
  local cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "[ok] $cmd: $(command -v "$cmd")"
  else
    echo "[missing] $cmd"
  fi
}

echo "== Basic tools =="
check_cmd git
check_cmd python
check_cmd python3
check_cmd pip
check_cmd make
check_cmd gcc
check_cmd g++

echo
echo "== Optional embedded / hardware tools =="
check_cmd arm-none-eabi-gcc
check_cmd JLinkExe
check_cmd nrfjprog
check_cmd minicom
check_cmd picocom

echo
echo "== Notes =="
echo "Codex cloud can prepare and inspect examples, but it cannot access USB/UART/SPI hardware."
echo "Board flashing and UART verification must be done on a local PC or lab machine."
