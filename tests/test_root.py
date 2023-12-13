import pytest

from .common import snapshot_command


def test_root_shows_help(snapshot):
    assert snapshot_command([]) == snapshot


@pytest.mark.parametrize("flag", ("-v", "--verbose"))
def test_root_verbose(snapshot, flag):
    assert snapshot_command([flag]) == snapshot
