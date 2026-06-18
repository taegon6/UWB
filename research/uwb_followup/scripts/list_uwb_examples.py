#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF_DIR = ROOT / "original_repos"

DEFINE_RE = re.compile(r"^(//\s*)?#define\s+([A-Za-z0-9_]+)")


def print_header(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def parse_example_selection(path: Path) -> None:
    print_header(f"example_selection.h: {path.relative_to(ROOT)}")
    active = []
    inactive = []

    for line in path.read_text(errors="ignore").splitlines():
        match = DEFINE_RE.match(line.strip())
        if not match:
            continue
        is_commented = bool(match.group(1))
        name = match.group(2)
        if is_commented:
            inactive.append(name)
        else:
            active.append(name)

    print("Active examples:")
    if active:
        for name in active:
            print(f"  - {name}")
    else:
        print("  - none")

    print("\nAvailable but commented examples:")
    for name in inactive:
        print(f"  - {name}")


def list_example_dirs(repo: Path) -> None:
    examples_root = repo / "API" / "Src" / "examples"
    if not examples_root.exists():
        return

    print_header(f"Example directories: {repo.name}")
    for path in sorted(examples_root.iterdir()):
        if path.is_dir():
            c_files = sorted(path.glob("*.c"))
            if c_files:
                files = ", ".join(file.name for file in c_files[:5])
                print(f"  - {path.relative_to(repo)}: {files}")
            else:
                print(f"  - {path.relative_to(repo)}")


def list_readmes(repo: Path) -> None:
    print_header(f"README files: {repo.name}")
    for path in sorted(repo.glob("README*")):
        if path.is_file():
            print(f"  - {path.relative_to(repo)}")


def main() -> None:
    if not REF_DIR.exists():
        print(f"Reference directory does not exist: {REF_DIR}")
        print("Run: bash research/uwb_followup/scripts/bootstrap_reference_repos.sh")
        raise SystemExit(1)

    repos = [path for path in sorted(REF_DIR.iterdir()) if path.is_dir()]
    if not repos:
        print(f"No repositories found under: {REF_DIR}")
        print("Run: bash research/uwb_followup/scripts/bootstrap_reference_repos.sh")
        raise SystemExit(1)

    for repo in repos:
        print_header(f"Repository: {repo.name}")
        print(f"Path: {repo}")
        list_readmes(repo)

        selection_files = sorted(repo.glob("**/example_selection.h"))
        for selection in selection_files:
            parse_example_selection(selection)

        list_example_dirs(repo)


if __name__ == "__main__":
    main()
