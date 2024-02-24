import os
import subprocess

from packse.index import write_server_pid

from .common import snapshot_command

FILTERS = [
    (r"pid \d+", "pid [PID]"),
    (r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d,\d\d\d", "[TIMESTAMP]"),
    ("uuid: .*", "uuid: [UUID]"),
]


def test_index_up_background(snapshot, tmpcwd, tmpenviron):
    tmpenviron["HOME"] = str(tmpcwd)

    try:
        assert (
            snapshot_command(
                ["index", "up", "--bg"],
                extra_filters=FILTERS,
            )
            == snapshot
        )
    finally:
        subprocess.call(["packse", "index", "down"], env=tmpenviron)


def test_index_up_foreground(snapshot, tmpcwd, tmpenviron):
    tmpenviron["HOME"] = str(tmpcwd)

    assert (
        snapshot_command(
            ["index", "up"],
            extra_filters=FILTERS,
            # Send a keyboard interrupt after a bit — use a longer delay for slow CI machines
            interrupt_after=15 if os.environ.get("CI") else 5,
        )
        == snapshot
    )


def test_index_down(snapshot, tmpcwd, tmpenviron):
    tmpenviron["HOME"] = str(tmpcwd)
    subprocess.check_call(["packse", "index", "up", "--bg"])
    assert (
        snapshot_command(
            ["index", "down"],
            extra_filters=FILTERS,
        )
        == snapshot
    )


def test_index_down_no_server_found(snapshot, tmpcwd):
    assert (
        snapshot_command(
            ["index", "down"],
            extra_filters=FILTERS,
            env={"PACKSE_STATE_PATH": str(tmpcwd)},
        )
        == snapshot
    )


def test_index_down_server_stopped(snapshot, tmpcwd, tmpenviron):
    tmpenviron["PACKSE_STATE_PATH"] = str(tmpcwd)
    write_server_pid(99999)

    assert (
        snapshot_command(
            ["index", "down"],
            extra_filters=FILTERS,
            env={"PACKSE_STATE_PATH": str(tmpcwd)},
        )
        == snapshot
    )
