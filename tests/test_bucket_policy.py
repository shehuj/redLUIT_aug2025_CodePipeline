"""Guard rails for the S3 bucket policy so it never grants more than public read."""
import json
from pathlib import Path

import pytest

POLICY_PATH = Path(__file__).resolve().parent.parent / "bucketPolicy.json"


@pytest.fixture(scope="module")
def policy():
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _as_list(value):
    return value if isinstance(value, list) else [value]


def test_policy_version(policy):
    assert policy["Version"] == "2012-10-17"


def test_statements_have_sid(policy):
    assert policy["Statement"]
    for statement in policy["Statement"]:
        assert statement.get("Sid")


def test_public_statements_are_read_only(policy):
    for statement in policy["Statement"]:
        if statement["Effect"] != "Allow":
            continue
        assert _as_list(statement["Action"]) == ["s3:GetObject"], statement


def test_resources_scoped_to_objects(policy):
    for statement in policy["Statement"]:
        for resource in _as_list(statement["Resource"]):
            assert resource.startswith("arn:aws:s3:::"), resource
            assert resource.endswith("/*"), f"Policy must target objects, not the bucket: {resource}"
            assert resource != "arn:aws:s3:::*/*", "Policy must not target every bucket"
