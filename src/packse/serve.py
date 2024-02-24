import importlib
import logging
import threading
from pathlib import Path

from packse.build import build
from packse.error import RequiresExtra, ServeThreadError
from packse.index import add_vendored_build_deps, start_index_server

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

    dist_dir = Path(dist_dir)
    build_dir = Path(build_dir)

    build_ready = threading.Event()
    rebuild = threading.Thread(
        target=build_scenarios,
        args=(targets, short_names, no_hash, dist_dir, build_dir, build_ready),
        name="serve-build-scenarios",
        daemon=True,
    )
    serve = threading.Thread(
        target=serve_packages,
        args=(host, port, dist_dir, offline),
        name="serve-package-index",
    )
    rebuild.start()

    # Wait up to 60 seconds for the build to complete
    for _ in range(60):
        if build_ready.wait(1):
            break
        if not rebuild.is_alive():
            raise ServeThreadError("Build thread failed.")

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
    ready: threading.Event,
) -> None:
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
            dist_dir=dist_dir,
            build_dir=build_dir,
        )

    ready.set()

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
            dist_dir=dist_dir,
            build_dir=build_dir,
        )


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
        line = ""
        while True:
            line = process.stdout.readline().decode()
            if debug:
                print(line, end="")
