"""
Tests a subset of included scenarios
"""

import pytest

from packse import __development_base_path__

from .common import snapshot_command

TEST_SCENARIOS = tuple(
    sorted(
        path
        for path in (__development_base_path__ / "scenarios" / "examples").iterdir()
    )
)
TEST_SCENARIO_IDS = tuple(path.with_suffix("").name for path in TEST_SCENARIOS)


@pytest.mark.parametrize(
    "target",
    TEST_SCENARIOS,
    ids=TEST_SCENARIO_IDS,
)
@pytest.mark.usefixtures("tmpcwd")
def test_build_test_scenarios(snapshot, target):
    assert (
        snapshot_command(
            ["build", str(target)], snapshot_stderr=False, snapshot_filesystem=True
        )
        == snapshot
    )


@pytest.mark.parametrize("target", TEST_SCENARIOS, ids=TEST_SCENARIO_IDS)
@pytest.mark.usefixtures("tmpcwd")
def test_view_test_scenarios(snapshot, target):
    assert snapshot_command(["view", str(target)], snapshot_filesystem=True) == snapshot
