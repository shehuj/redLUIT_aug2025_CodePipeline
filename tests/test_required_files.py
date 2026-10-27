#!/usr/bin/env python3
"""Verify the repository contains the files the pipeline and reviewers rely on.

Runs under pytest, and can also be run directly (``python tests/test_required_files.py``)
as a fast pre-check that exits non-zero when anything is missing.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    ".gitignore",
    "website.html",
    "myResume.html",
    "bucketPolicy.json",
    "buildspec.yml",
    "infrastructure/pipeline.yaml",
]


def find_missing(base_dir: Path, required_files: list[str]) -> list[str]:
    return [name for name in required_files if not (base_dir / name).is_file()]


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_required_file_present(filename):
    assert (REPO_ROOT / filename).is_file(), f"Missing required file: {filename}"


@pytest.mark.parametrize("filename", ["README.md", "LICENSE"])
def test_required_file_not_empty(filename):
    assert (REPO_ROOT / filename).read_text(encoding="utf-8").strip(), f"{filename} is empty"


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
