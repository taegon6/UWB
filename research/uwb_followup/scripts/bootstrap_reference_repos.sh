#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF_DIR="$ROOT_DIR/original_repos"

mkdir -p "$REF_DIR"
cd "$REF_DIR"

clone_or_update() {
  local url="$1"
  local dir="$2"

  if [ -d "$dir/.git" ]; then
    echo "[update] $dir"
    git -C "$dir" fetch --depth 1 origin main || true
    git -C "$dir" pull --ff-only || true
  else
    echo "[clone] $url -> $dir"
    git clone --depth 1 "$url" "$dir"
  fi
}

clone_or_update "https://github.com/FastTurtle7892/UWB-Ranging-Optimization.git" "UWB-Ranging-Optimization"
clone_or_update "https://github.com/FastTurtle7892/UWB_AoA_Project.git" "UWB_AoA_Project"
clone_or_update "https://github.com/FastTurtle7892/UWB-Autonomous-Robot.git" "UWB-Autonomous-Robot"

echo
echo "Reference repositories are ready under:"
echo "  $REF_DIR"
