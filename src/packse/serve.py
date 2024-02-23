import logging
import shutil
import subprocess
import sys
import threading
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

    rebuild = threading.Thread(
        target=rebuild_on_change,
        args=(targets, short_names, no_hash, storage_path),
        daemon=True,
    )
    serve = threading.Thread(
        target=serve_packages, args=(host, port, storage_path, offline)
    )
    rebuild.start()

    try:
        serve.start()
    finally:
        serve.join()


def rebuild_on_change(
    targets: list[Path], short_names: bool, no_hash: bool, storage_path: Path
) -> None:
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


def serve_packages(host: str, port: int, storage_path: Path, offline: bool):
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
