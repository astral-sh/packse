import importlib
import logging
import shutil
import threading
import time
from pathlib import Path

from packse.build import build
from packse.error import PackseError, RequiresExtra
from packse.index import add_vendored_build_deps, render_index, start_index_server

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
    offline: bool = False,
):
    try:
        importlib.import_module("pypiserver")
    except ImportError:
        raise RequiresExtra("index commands", "index")
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
        target=serve_packages,
        args=(host, port, dist_dir, offline),
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
    if not targets:
        print("Warning: No targets provided, automatic rebuilds not enabled.")
        return

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


def serve_packages(host: str, port: int, dist_dir: Path, offline: bool):
    index_url = f"http://{host}:{port}"
    index_note = "offline index" if offline else "local index with PyPI fallback"

    logger.info("Starting %s at %s", index_note, index_url)
    with start_index_server(
        dist_dir=dist_dir, host=host, port=port, offline=offline, server_log_path=None
    ) as process:
        debug = logger.getEffectiveLevel() <= logging.DEBUG
        if not debug:
            logger.info("Hiding server output, use `-v` to stream server logs")

        add_vendored_build_deps(dist_dir, offline)

        logger.info("Ready! [Stop with Ctrl-C]")
        while True:
            line = process.stdout.readline().decode()
            if debug:
                print(line, end="")
