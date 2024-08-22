import pytest

from packse import __development_base_path__

from .common import snapshot_command


def test_view_no_target(snapshot):
    assert (
        snapshot_command(["view"], snapshot_stderr=False, snapshot_stdout=False)
        == snapshot
    )


def test_view_target_does_not_exist(snapshot):
    assert snapshot_command(["view", "foo"]) == snapshot


@pytest.mark.usefixtures("tmpcwd")
def test_view_one_target_does_not_exist(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target), "foo"]) == snapshot


def test_view_invalid_target(snapshot, tmpcwd):
    target = tmpcwd / "test.json"
    target.touch()
    assert snapshot_command(["view", str(target)]) == snapshot


def test_view_example(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target)]) == snapshot


def test_view_example_short_names(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target), "--short-names"]) == snapshot


def test_view_example_name(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target), "--name", "example"]) == snapshot
