import os
from pathlib import Path

import pytest

from packse import __development_base_path__
from packse.scenario import load_scenario, scenario_hash

from .common import snapshot_command


def test_build_no_target(snapshot):
    assert snapshot_command(["build"]) == snapshot


def test_build_target_does_not_exist(snapshot):
    assert snapshot_command(["build", "foo"]) == snapshot


def test_build_invalid_target(snapshot, tmpcwd):
    target = tmpcwd / "test.json"
    target.touch()
    assert snapshot_command(["build", str(target)]) == snapshot


@pytest.mark.usefixtures("tmpcwd")
def test_build_example(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert (
        snapshot_command(
            ["build", str(target)], snapshot_filesystem=True, snapshot_stderr=False
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpcwd")
def test_build_example_short_names(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert (
        snapshot_command(
            ["build", str(target), "--short-names"],
            snapshot_filesystem=True,
            snapshot_stderr=False,
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpcwd")
@pytest.mark.usefixtures("tmpenviron")
def test_build_example_with_seed(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    os.environ["PACKSE_VERSION_SEED"] = "foo"
    assert (
        snapshot_command(
            ["build", str(target)], snapshot_filesystem=True, snapshot_stderr=False
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpcwd")
def test_build_example_already_exists(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    scenario = load_scenario(target)
    name = f"{scenario.name}-{scenario_hash(scenario)}"
    (Path.cwd() / "build" / name).mkdir(parents=True)
    assert snapshot_command(["build", target], snapshot_filesystem=True) == snapshot


@pytest.mark.usefixtures("tmpcwd")
def test_build_example_already_exists_with_rm_flag(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    (Path(".") / "build").mkdir()
    assert (
        snapshot_command(["build", target, "--rm"], snapshot_stderr=False) == snapshot
    )
