#!/usr/bin/env python3
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "reference_repos.json"

OWNER = "FastTurtle7892"
SEARCH_TERMS = ["UWB", "DW3000", "DW3110", "DW1000", "AoA", "Ranging", "RTLS"]
PREFERRED_NAMES = [
    "UWB-Ranging-Optimization",
    "UWB_AoA_Project",
    "UWB-Autonomous-Robot",
]


def github_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "uwb-followup-setup",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def search_repositories() -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    for term in SEARCH_TERMS:
        query = urllib.parse.quote(f"user:{OWNER} {term}")
        url = f"https://api.github.com/search/repositories?q={query}&per_page=20"
        try:
            data = github_get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] GitHub search failed for term={term!r}: {exc}")
            continue

        for item in data.get("items", []):
            full_name = item.get("full_name")
            if not full_name:
                continue
            name = item.get("name", "")
            description = item.get("description") or ""
            haystack = f"{name} {description}".lower()
            if any(keyword.lower() in haystack for keyword in SEARCH_TERMS):
                found[full_name] = item

    # Exact fallback for repositories we already know are relevant.
    for name in PREFERRED_NAMES:
        full_name = f"{OWNER}/{name}"
        if full_name in found:
            continue
        url = f"https://api.github.com/repos/{OWNER}/{name}"
        try:
            found[full_name] = github_get_json(url)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Could not fetch preferred repo {full_name}: {exc}")

    repos = list(found.values())
    repos.sort(key=lambda item: (item.get("name") not in PREFERRED_NAMES, item.get("name", "")))
    return repos


def main() -> None:
    repos = search_repositories()
    if not repos:
        raise SystemExit("No UWB-related repositories found.")

    output = []
    for repo in repos:
        output.append(
            {
                "name": repo["name"],
                "full_name": repo["full_name"],
                "clone_url": repo["clone_url"],
                "html_url": repo["html_url"],
                "description": repo.get("description"),
                "default_branch": repo.get("default_branch", "main"),
            }
        )

    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")

    print(f"Discovered {len(output)} repository/repositories.")
    print(f"Wrote: {OUT_PATH}")
    for repo in output:
        print(f"- {repo['full_name']} -> {repo['clone_url']}")


if __name__ == "__main__":
    main()
