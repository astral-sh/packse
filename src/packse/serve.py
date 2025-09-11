import logging
import shutil
import threading
import time
from pathlib import Path

from packse import __development_base_path__
from packse.build import build
from packse.error import PackseError, RequiresExtra
from packse.index import render_index, run_index_server

try:
    import watchfiles
except ImportError:
    watchfiles = None
    pass


logger = logging.getLogger(__name__)


def serve(
    targets: list[Path],
    build_dir: Path,
    dist_dir: Path,
    index_dir: Path,
    host: str = "localhost",
    port: int = 3141,
    short_names: bool = False,
    no_hash: bool = False,
):
    if watchfiles is None:
        raise RequiresExtra("serve command", "serve")

    build_scenarios(
        targets,
        short_names,
        no_hash,
        dist_dir,
        build_dir,
        index_dir,
    )

    rebuild = threading.Thread(
        target=watch_scenarios,
        args=(
            targets,
            short_names,
            no_hash,
            dist_dir,
            build_dir,
            index_dir,
        ),
        name="serve-build-scenarios",
        daemon=True,
    )
    serve = threading.Thread(
        target=run_index_server,
        args=(index_dir, host, port),
        name="serve-package-index",
    )
    rebuild.start()

    try:
        serve.start()
    finally:
        serve.join()


def build_scenarios(
    targets: list[Path],
    short_names: bool,
    no_hash: bool,
    dist_dir: Path,
    build_dir: Path,
    index_dir: Path,
) -> None:
    print("Performing initial build...")
    start = time.time()
    build(
        targets,
        rm_destination=True,
        skip_root=False,
        short_names=short_names,
        no_hash=no_hash,
        dist_dir=dist_dir,
        build_dir=build_dir,
    )
    if index_dir.exists():
        shutil.rmtree(index_dir)
    render_index(
        targets,
        no_hash=no_hash,
        short_names=short_names,
        dist_dir=dist_dir,
        exist_ok=False,
        index_dir=index_dir,
    )

    # Copy the vendored build dependencies
    if (index_dir / "vendor").exists():
        shutil.rmtree(index_dir / "vendor")
    shutil.copytree(__development_base_path__ / "vendor", index_dir / "vendor")

    logger.info(
        f"Built scenarios and populated templates in {time.time() - start:.2f}s."
    )


def watch_scenarios(
    targets: list[Path],
    short_names: bool,
    no_hash: bool,
    dist_dir: Path,
    build_dir: Path,
    index_dir: Path,
) -> None:
    for changes in watchfiles.watch(*targets):
        # When trying to render a (temporarily) invalid file, print errors and retry on the next change.
        try:
            targets = [
                path for kind, path in changes if kind != watchfiles.Change.deleted
            ]
            targets = [Path(target) for target in targets if Path(target).is_file()]
            logger.info("Detected changes! Rebuilding...")
            start = time.time()
            build(
                targets,
                rm_destination=True,
                skip_root=False,
                short_names=short_names,
                no_hash=no_hash,
                dist_dir=dist_dir,
                build_dir=build_dir,
            )
            render_index(
                targets,
                no_hash=no_hash,
                short_names=short_names,
                dist_dir=dist_dir,
                exist_ok=True,
                index_dir=index_dir,
            )

            logger.info(
                f"Rebuilt scenarios and populated templates in {time.time() - start:.2f}s."
            )
        except PackseError:
            logger.exception("Failed to rebuild")
