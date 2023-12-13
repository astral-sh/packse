import pytest
import subprocess

from packse import __development_base_path__
from .common import snapshot_command
from pathlib import Path


def test_publish_example(snapshot, tmpcwd: Path):
    target = __development_base_path__ / "scenarios" / "example.json"

    # Build first
    # TODO(zanieb): Since we're doing a dry run consider just constructing some fake files?
    subprocess.check_call(
        ["packse", "build", str(target)],
        cwd=tmpcwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    dists = list((tmpcwd / "dist").iterdir())
    assert len(dists) == 1
    dist = dists[0]

    assert snapshot_command(["publish", "--dry-run", dist]) == snapshot
