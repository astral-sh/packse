"""
Tests all included scenarios
"""

import pytest
from packse import __development_base_path__

from .common import snapshot_command

EXCLUDE = frozenset(("example.json",))
ALL_SCENARIOS = tuple(
    sorted(
        path
        for path in (__development_base_path__ / "scenarios").iterdir()
        if path.is_file() and path.name.endswith(".json") and path.name not in EXCLUDE
    )
)
ALL_SCENARIO_IDS = tuple(path.name.removesuffix(".json") for path in ALL_SCENARIOS)


@pytest.mark.parametrize(
    "target",
    ALL_SCENARIOS,
    ids=ALL_SCENARIO_IDS,
)
@pytest.mark.usefixtures("tmpcwd")
def test_build_all_scenarios(snapshot, target):
    assert (
        snapshot_command(["build", str(target)], snapshot_filesystem=True) == snapshot
    )


@pytest.mark.parametrize("target", ALL_SCENARIOS, ids=ALL_SCENARIO_IDS)
@pytest.mark.usefixtures("tmpcwd")
def test_view_all_scenarios(snapshot, target):
    assert snapshot_command(["view", str(target)], snapshot_filesystem=True) == snapshot
