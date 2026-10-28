#!/usr/bin/env python3
"""Verify the repository contains the files the pipeline and reviewers rely on.

Runs under pytest, and can also be run directly (``python tests/test_required_files.py``)
as a fast pre-check that exits non-zero when anything is missing. It deliberately uses only
the standard library so the pre-check works before any dependencies are installed.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "website.html",
    "bucketPolicy.json",
    "infrastructure/site.yaml",
    ".github/workflows/TestsPackage.yml",
    ".github/workflows/deploy.yml",
]


def find_missing(base_dir: Path, required_files: list[str]) -> list[str]:
    return [name for name in required_files if not (base_dir / name).is_file()]


def test_required_files_present():
    missing = find_missing(REPO_ROOT, REQUIRED_FILES)
    assert not missing, f"Missing required file(s): {missing}"


def test_required_files_not_empty():
    empty = [name for name in ("README.md", "LICENSE") if not (REPO_ROOT / name).read_text(encoding="utf-8").strip()]
    assert not empty, f"Empty file(s): {empty}"


def main() -> int:
    missing = find_missing(REPO_ROOT, REQUIRED_FILES)
    if missing:
        print("ERROR: Missing required file(s) in", REPO_ROOT)
        for name in missing:
            print(f"  - {name}")
        return 1

    print("All required files are present in", REPO_ROOT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
