import pytest

from .common import snapshot_command


def test_build_pkg_no_name(snapshot):
    assert snapshot_command(["build-pkg"]) == snapshot


def test_build_pkg_no_version(snapshot):
    assert snapshot_command(["build-pkg", "foo"]) == snapshot


def test_build_pkg_invalid_version(snapshot, tmpcwd):
    target = tmpcwd / "test.json"
    target.touch()
    assert snapshot_command(["build-pkg", "foo", "bar"]) == snapshot


@pytest.mark.usefixtures("tmpcwd")
def test_build_pkg(snapshot):
    assert (
        snapshot_command(
            ["build-pkg", "foo", "1.0.0"],
            snapshot_filesystem=True,
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpcwd")
def test_build_pkg_no_wheel(snapshot):
    assert (
        snapshot_command(
            ["build-pkg", "foo", "1.0.0", "--no-wheel"],
            snapshot_filesystem=True,
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpcwd")
def test_build_pkg_no_sdist(snapshot):
    assert (
        snapshot_command(
            ["build-pkg", "foo", "1.0.0", "--no-sdist"],
            snapshot_filesystem=True,
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpcwd")
def test_build_pkg_wheel_tags(snapshot):
    assert (
        snapshot_command(
            ["build-pkg", "foo", "1.0.0", "-t", "tag1", "--wheel-tag", "tag2"],
            snapshot_filesystem=True,
        )
        == snapshot
    )
