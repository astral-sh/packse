import logging
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packse import __development_base_path__
from packse.build import build
from packse.error import RequiresExtra

try:
    import watchfiles
except ImportError:
    watchfiles = None
    pass


logger = logging.getLogger(__name__)


def serve(
    targets: list[Path],
    storage_path: Path,
    host: str = "localhost",
    port: int = 3141,
    short_names: bool = False,
    no_hash: bool = False,
    offline: bool = False,
):
    if not shutil.which("pypi-server"):
        raise RequiresExtra("serve command", "serve")

    if watchfiles is None:
        raise RequiresExtra("serve command", "serve")

    if not targets:
        print("Warning: No targets provided, automatic rebuilds not enabled.")

    else:
        print("Performing initial build...")
        build(
            targets,
            rm_destination=True,
            skip_root=False,
            short_names=short_names,
            no_hash=no_hash,
            work_dir=storage_path,
        )

    build_directory = __development_base_path__ / "vendor" / "build"
    if build_directory.exists():
        logger.debug("Copying vendored build dependencies...")
        shutil.copytree(
            build_directory, storage_path / "dist" / "build", dirs_exist_ok=True
        )
    else:
        logger.warning("No vendored build dependencies found at %s" % build_directory)

    with ThreadPoolExecutor(
        thread_name_prefix="packse-serve-", max_workers=2
    ) as executor:
        executor.submit(rebuild_on_change, targets, short_names, no_hash, storage_path)
        executor.submit(serve_packages, host, port, storage_path, offline)


def rebuild_on_change(targets, short_names, no_hash, storage_path):
    for changes in watchfiles.watch(*targets):
        targets = [path for kind, path in changes if kind != watchfiles.Change.deleted]
        targets = [Path(target) for target in targets if Path(target).is_file()]
        print("Detected changes! Rebuilding...")
        build(
            targets,
            rm_destination=True,
            skip_root=False,
            short_names=short_names,
            no_hash=no_hash,
            work_dir=storage_path,
        )


def serve_packages(host, port, storage_path, offline):
    command = [
        "pypi-server",
        "run",
        "--host",
        host,
        "--port",
        str(port),
        str(storage_path / "dist"),
        "-v",
    ]
    if offline:
        command.append("--disable-fallback")
    subprocess.run(
        command,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
