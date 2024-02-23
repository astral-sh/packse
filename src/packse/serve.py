import logging
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packse.build import build
from packse.error import RequiresExtra

try:
    import watchfiles
except ImportError:
    pass


logger = logging.getLogger(__name__)


def serve(
    targets: list[Path],
    host: str = "localhost",
    port: int = 3141,
    short_names: bool = False,
    storage_path: Path | None = None,
):
    if not shutil.which("pypi-server"):
        raise RequiresExtra("serve command", "serve")

    try:
        import watchfiles
    except ImportError:
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
            work_dir=storage_path,
        )

    with ThreadPoolExecutor(
        thread_name_prefix="packse-serve-", max_workers=2
    ) as executor:
        executor.submit(rebuild_on_change, targets, short_names, storage_path)
        executor.submit(serve_packages, host, port, storage_path)


def rebuild_on_change(targets, short_names, storage_path):
    for changes in watchfiles.watch(*targets):
        targets = [path for kind, path in changes if kind != watchfiles.Change.deleted]
        targets = [Path(target) for target in targets if Path(target).is_file()]
        print("Detected changes! Rebuilding...")
        build(
            targets,
            rm_destination=True,
            skip_root=False,
            short_names=short_names,
            work_dir=storage_path,
        )


def serve_packages(host, port, storage_path):
    subprocess.run(
        [
            "pypi-server",
            "run",
            "--host",
            host,
            "--port",
            str(port),
            str(storage_path / "dist"),
            "-v",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
