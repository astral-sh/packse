from .common import snapshot_command


def test_fetch(snapshot, tmpcwd):
    assert (
        # Include a ref for reproducibility
        snapshot_command(
            ["fetch", "--ref", "df20b898fdf1fd242cc19acc2a3148d72aa4d89f"],
            snapshot_filesystem=True,
            working_directory=tmpcwd,
        )
        == snapshot
    )


def test_fetch_dest(snapshot, tmpcwd):
    assert (
        snapshot_command(
            [
                "fetch",
                "--dest",
                "foo",
                "--ref",
                "df20b898fdf1fd242cc19acc2a3148d72aa4d89f",
            ],
            snapshot_filesystem=True,
            working_directory=tmpcwd,
        )
        == snapshot
    )


def test_fetch_dest_exists(snapshot, tmpcwd):
    (tmpcwd / "foo").mkdir()
    assert (
        snapshot_command(
            [
                "fetch",
                "--dest",
                "foo",
                "--ref",
                "df20b898fdf1fd242cc19acc2a3148d72aa4d89f",
            ],
            snapshot_filesystem=True,
            working_directory=tmpcwd,
        )
        == snapshot
    )


def test_fetch_dest_exists_force(snapshot, tmpcwd):
    (tmpcwd / "foo").mkdir()
    assert (
        snapshot_command(
            [
                "fetch",
                "--dest",
                "foo",
                "--force",
                "--ref",
                "df20b898fdf1fd242cc19acc2a3148d72aa4d89f",
            ],
            snapshot_filesystem=True,
            working_directory=tmpcwd,
        )
        == snapshot
    )


def test_fetch_tag(snapshot, tmpcwd):
    assert (
        snapshot_command(
            ["fetch", "--ref", "0.1.0"],
            snapshot_filesystem=True,
            working_directory=tmpcwd,
        )
        == snapshot
    )
