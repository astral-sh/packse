import os
import subprocess

import psutil
import pytest
from packse.index import write_server_pid

from .common import snapshot_command

FILTERS = [
    (r"pid \d+", "pid [PID]"),
    (r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d,\d\d\d", "[TIMESTAMP]"),
    ("uuid: .*", "uuid: [UUID]"),
]


@pytest.fixture(autouse=True)
def check_for_leaked_servers():
    yield

    leak = False
    for p in psutil.process_iter():
        try:
            if "devpi" in p.name() or "devpi" in " ".join(p.cmdline()):
                print("Killing devpi server with pid", p.pid)
                p.terminate()
                p.wait()
                leak = True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

    if leak:
        raise RuntimeError("Leaked package index server(s)")


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


def test_index_up_with_storage_path(snapshot, tmpcwd):
    try:
        assert (
            snapshot_command(
                ["index", "up", "--storage-path", str(tmpcwd), "--bg"],
                extra_filters=FILTERS,
            )
            == snapshot
        )
    finally:
        subprocess.call(["packse", "index", "down", "--storage-path", str(tmpcwd)])


def test_index_down_with_storage_path(snapshot, tmpcwd):
    subprocess.check_call(
        ["packse", "index", "up", "--storage-path", str(tmpcwd), "--bg"]
    )
    assert (
        snapshot_command(
            ["index", "down", "--storage-path", str(tmpcwd)],
            extra_filters=FILTERS,
        )
        == snapshot
    )


def test_index_down_no_server_found(snapshot, tmpcwd):
    assert (
        snapshot_command(
            ["index", "down", "--storage-path", str(tmpcwd)],
            extra_filters=FILTERS,
        )
        == snapshot
    )


def test_index_down_server_stopped(snapshot, tmpcwd):
    write_server_pid(tmpcwd, 99999)
    assert (
        snapshot_command(
            ["index", "down", "--storage-path", str(tmpcwd)],
            extra_filters=FILTERS,
        )
        == snapshot
    )
