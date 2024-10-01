import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from packse import __development_base_path__

from .common import snapshot_command


@pytest.fixture(scope="module")
def scenario_dist() -> Generator[Path, None, None]:
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"

    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.check_call(
            ["packse", "build", str(target)],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        dists = list((Path(tmpdir) / "dist").iterdir())
        assert len(dists) == 1
        dist = dists[0]

        yield dist


@pytest.fixture
def credentials(tmpenviron) -> None:
    os.environ["PACKSE_PUBLISH_USERNAME"] = "username"
    os.environ["PACKSE_PUBLISH_PASSWORD"] = "password"
    yield


class MockBinary:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.callback = None
        self._update_bin("")

    def _prepare_text(self, text: str = None):
        if not text:
            return ""
        # Escape single quotes
        return text.replace("'", "\\'")

    def _update_bin(self, content: str):
        self.path.write_text("#!/usr/bin/env sh\n\n" + content + "\n")
        self.path.chmod(self.path.stat().st_mode | stat.S_IEXEC)

    def set_success(self, text: str | None = None):
        text = self._prepare_text(text)
        self._update_bin(f"echo '{text}'")

    def set_error(self, text: str | None = None):
        text = self._prepare_text(text)
        self._update_bin(f"echo '{text}'; exit 1")


@pytest.fixture
def mock_uv(monkeypatch: pytest.MonkeyPatch) -> Generator[MockBinary, None, None]:
    # Create a temp directory to register as a bin
    with tempfile.TemporaryDirectory() as tmpdir:
        mock = MockBinary(Path(tmpdir) / "uv")
        mock.set_success("<mock uv logs>")

        # Add to the path
        monkeypatch.setenv("PATH", tmpdir, prepend=":")
        assert shutil.which("uv").startswith(tmpdir)

        yield mock


@pytest.mark.usefixtures("credentials")
def test_publish_example_dry_run(snapshot, scenario_dist: Path):
    assert (
        snapshot_command(
            ["publish", "--dry-run", scenario_dist],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )


@pytest.mark.usefixtures("credentials")
def test_publish_example_uv_succeeds(
    snapshot, scenario_dist: Path, mock_uv: MockBinary
):
    mock_uv.set_success("<uv happy message>")

    assert (
        snapshot_command(
            ["publish", scenario_dist, "-v", "--workers", "1"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )


@pytest.mark.usefixtures("credentials")
def test_publish_example_uv_succeeds_parallel(
    snapshot, scenario_dist: Path, mock_uv: MockBinary
):
    mock_uv.set_success("<uv happy message>")

    assert (
        snapshot_command(
            ["publish", scenario_dist, "-v"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
            # Cannot record stderr when running in parallel
            snapshot_stderr=False,
        )
        == snapshot
    )


@pytest.mark.usefixtures("credentials")
def test_publish_example_uv_fails_with_unknown_error(
    snapshot, scenario_dist: Path, mock_uv: MockBinary
):
    mock_uv.set_error("<uv error message>")

    assert (
        snapshot_command(
            ["publish", scenario_dist, "-v", "--workers", "1"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )


@pytest.mark.usefixtures("credentials")
def test_publish_example_uv_fails_with_rate_limit(
    snapshot, scenario_dist: Path, mock_uv: MockBinary
):
    mock_uv.set_error(
        """
Uploading distributions to https://test.pypi.org/legacy/
Uploading
requires_transitive_incompatible_with_root_version_5c1b7dc1_c-1.0.0-py3-none-any
.whl
25l
    0% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0.0/4.1 kB • --:-- • ?
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.1/4.1 kB • 00:00 • ?
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.1/4.1 kB • 00:00 • ?
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.1/4.1 kB • 00:00 • ?
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 4.1/4.1 kB • 00:00 • ?
25hWARNING  Error during upload. Retry with the --verbose option for more details.
ERROR    HTTPError: 429 Too Many Requests from https://test.pypi.org/legacy/
            Too many new projects created
        """
    )

    assert (
        snapshot_command(
            ["publish", scenario_dist, "--workers", "1"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )


@pytest.mark.usefixtures("credentials")
def test_publish_example_uv_fails_with_already_exists(
    snapshot, scenario_dist: Path, mock_uv: MockBinary
):
    mock_uv.set_error(
        """
Uploading distributions to https://test.pypi.org/legacy/
Uploading example_9e723676_a-1.0.0.tar.gz
100% ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3.1/3.1 kB • 00:00 • ?
WARNING  Error during upload. Retry with the --verbose option for more details.
ERROR    HTTPError: 400 Bad Request from https://test.pypi.org/legacy/
         File already exists. See https://test.pypi.org/help/#file-name-reuse for more information.
        """
    )

    assert (
        snapshot_command(
            ["publish", scenario_dist, "-v", "--workers", "1"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )


@pytest.mark.usefixtures("tmpenviron")
def test_publish_example_no_credentials(
    snapshot,
    scenario_dist: Path,
    mock_uv: MockBinary,
):
    # Ensure these do not exist
    if "PACKSE_PUBLISH_PASSWORD" in os.environ:
        os.environ.pop("PACKSE_PUBLISH_PASSWORD")
    if "UV_PASSWORD" in os.environ:
        os.environ.pop("UV_PASSWORD")

    mock_uv.set_error(
        """
        Should not be reached!
        """
    )

    assert (
        snapshot_command(
            ["publish", scenario_dist, "-v", "--workers", "1"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )


@pytest.mark.usefixtures("credentials")
def test_publish_example_no_username_defaults_to_token(
    snapshot,
    scenario_dist: Path,
    mock_uv: MockBinary,
):
    # Ensure these do not exist
    if "PACKSE_PUBLISH_USERNAME" in os.environ:
        os.environ.pop("PACKSE_PUBLISH_USERNAME")
    if "UV_USERNAME" in os.environ:
        os.environ.pop("UV_USERNAME")

    assert (
        snapshot_command(
            ["publish", scenario_dist, "-v", "--workers", "1"],
            extra_filters=[(re.escape(str(scenario_dist.resolve())), "[DISTDIR]")],
        )
        == snapshot
    )
