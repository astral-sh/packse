import importlib.metadata
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from packse.error import DestinationAlreadyExists

logger = logging.getLogger(__name__)


def fetch(
    dest: Path | None = None,
    ref: str | None = None,
    repo_url: str = "https://github.com/astral-sh/packse",
    repo_subdir: str = "scenarios",
    force: bool = False,
):
    start_time = time.time()
    dest = dest or (Path.cwd() / "scenarios")

    if dest.exists() and not force:
        raise DestinationAlreadyExists(dest)

    if not ref:
        ref = importlib.metadata.version("packse")
        if ref == "0.0.0":
            ref = "HEAD"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Perform a sparse checkout where we only grab the `scenarios` folder
        logger.info("Cloning repository %s", repo_url)
        subprocess.check_call(
            [
                "git",
                "clone",
                "-n",
                "--filter=tree:0",
                repo_url,
                "repo",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=tmpdir,
        )

        logger.info("Checking out directory '%s' at ref %s", repo_subdir, ref)
        subprocess.check_call(
            ["git", "sparse-checkout", "set", "--no-cone", repo_subdir],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=Path(tmpdir) / "repo",
        )
        subprocess.check_call(
            ["git", "fetch", "origin", ref],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=Path(tmpdir) / "repo",
        )
        subprocess.check_call(
            ["git", "checkout", ref],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            cwd=Path(tmpdir) / "repo",
        )

        src = Path(tmpdir) / "repo" / repo_subdir
        file_count = 0
        for file in sorted(src.iterdir()):
            file_count += 1
            logger.debug("Found %s", file.name)

        logger.info("Copying files into '%s'", dest)
        shutil.copytree(src, dest, dirs_exist_ok=True)

    logger.info(
        "Fetched %s files in %.2fs",
        file_count,
        time.time() - start_time,
    )
