import pytest

from packse import __development_base_path__

from .common import snapshot_command


def test_inspect_no_target_finds_all_valid_scenarios(snapshot):
    assert (
        # Just assert it succeeds, we don't want to include all these targets in the snap
        snapshot_command(["inspect"], snapshot_stdout=False, snapshot_stderr=False)
        == snapshot
    )


def test_inspect_target_does_not_exist(snapshot):
    assert snapshot_command(["inspect", "foo"]) == snapshot


@pytest.mark.usefixtures("tmpcwd")
def test_inspect_one_target_does_not_exist(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["inspect", str(target), "foo"]) == snapshot


def test_inspect_invalid_target(snapshot, tmpcwd):
    bad_target = tmpcwd / "test.json"
    bad_target.touch()
    good_target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["inspect", str(bad_target), str(good_target)]) == snapshot


def test_inspect_invalid_target_skip_invalid(snapshot, tmpcwd):
    bad_target = tmpcwd / "test.json"
    bad_target.touch()
    good_target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert (
        snapshot_command(
            ["inspect", str(bad_target), str(good_target), "--skip-invalid"]
        )
        == snapshot
    )


def test_inspect_json(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["inspect", str(target)]) == snapshot


def test_inspect_toml(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.toml"
    assert snapshot_command(["inspect", str(target)]) == snapshot


def test_inspect_yaml(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.yaml"
    assert snapshot_command(["inspect", str(target)]) == snapshot
