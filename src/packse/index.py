import errno
import hashlib
import importlib
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Generator

from packse import __development_base_path__
from packse.build import build
from packse.error import (
    RequiresExtra,
    ServeAddressInUse,
    ServeAlreadyRunning,
    ServeCommandError,
)
from packse.inspect import inspect
from packse.template import create_from_template

logger = logging.getLogger(__name__)


def index_up(
    host: str = "localhost",
    port: int = 3141,
    background: bool = False,
    dist_dir: Path | None = None,
    reset: bool = False,
    offline: bool = False,
):
    try:
        importlib.import_module("pypiserver")
    except ImportError:
        raise RequiresExtra("index commands", "index")

    if not dist_dir:
        dist_dir = Path.cwd() / "dist"
    else:
        dist_dir = Path(dist_dir).resolve()

    if background:
        if pid := get_server_pid():
            if is_running(pid):
                raise ServeAlreadyRunning()

    if reset:
        logger.info("Clearing existing server data...")
        if dist_dir.exists():
            shutil.rmtree(dist_dir)

    state_path = get_packse_state_path()

    logger.debug("Storing server metadata at %s", state_path)
    server_log_path = state_path / "server.log" if background else None
    index_url = f"http://{host}:{port}"
    index_note = "offline index" if offline else "local index with PyPI fallback"
    logger.info("Starting %s at %s", index_note, index_url)
    with start_index_server(
        dist_dir,
        host,
        port,
        server_log_path,
        offline=offline,
    ) as server_process:
        # Copy build dependencies over
        add_vendored_build_deps(dist_dir, offline)

        if background:
            logger.info("Running in background with pid %s", server_process.pid)
            logger.info("Stop index server with `packse index down`.")
            print(index_url)

        else:
            debug = logger.getEffectiveLevel() <= logging.DEBUG
            if not debug:
                logger.info("Hiding server output, use `-v` to stream server logs")

            logger.info("Ready! [Stop with Ctrl-C]")

            line = ""
            while True:
                line = server_process.stdout.readline().decode()
                if debug:
                    print(line, end="")


def index_down() -> bool:
    state_path = get_packse_state_path(create=False)

    if not state_path.exists():
        logger.warning("No server detected!")
        return False

    if pid := get_server_pid():
        if not is_running(pid):
            logger.info("Server looks shutdown already.")
            reset_pidfile()
            return

        logger.info("Stopping server with pid %s...", pid)
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            # Just move on if it's already dead
            pass

        # Wait for the server to exit for 10s
        limit = 10
        start_time = time.time()
        while time.time() - start_time < limit:
            if not is_running(pid):
                break
            time.sleep(0.1)
        else:
            # After the limit is reached, send a stronger signal...
            logger.info("Server has not stopped after %ds, sending kill...", limit)
            os.kill(pid, signal.SIGKILL)

            while is_running(pid):
                time.sleep(0.1)

        reset_pidfile()
        logger.info("Stopped server!")
        return True
    else:
        logger.warning("No server detected!")
        return False


@contextmanager
def start_index_server(
    dist_dir: Path,
    host: str,
    port: int,
    server_log_path: Path | None,
    offline: bool,
) -> Generator[subprocess.Popen, None, None]:
    server_url = f"http://{host}:{port}"
    dist_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-m",
        "pypiserver",
        "run",
        "--host",
        host,
        "--port",
        str(port),
        "-v",
        # Disable auth
        "-P",
        ".",
        "-a",
        ".",
        str(dist_dir),
    ]

    if offline:
        command.append("--disable-fallback")

    logger.debug("Running: %s", " ".join(command))

    server_process = subprocess.Popen(
        command,
        stderr=subprocess.STDOUT,
        stdout=server_log_path.open("wb") if server_log_path else subprocess.PIPE,
    )

    try:
        # Wait for server to be ready
        with (
            server_log_path.open("rb")
            if server_log_path
            else nullcontext(server_process.stdout) as server_output
        ):
            line = ""
            lines = []

            # Watch for startup
            # TODO: Use a healthceck instead?
            while "Serving on" not in line and "Listening on" not in line:
                try:
                    server_process.wait(0)
                except subprocess.TimeoutExpired:
                    pass
                else:
                    # The process stopped already
                    if (
                        logger.getEffectiveLevel() > logging.DEBUG
                        and server_output.seekable()
                    ):
                        server_output.seek(0)
                    err_output = (
                        "\n".join(lines) + server_output.read().decode().strip()
                    )
                    raise ServeCommandError("Failed to start server!", err_output)

                line = server_output.readline().decode()
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    print(line, end="")
                elif not server_output.seekable():
                    # Track the lines if we'll never be able to get them back
                    lines.append(line)
                if "Address already in use" in line:
                    raise ServeAddressInUse(server_url)

        # Server started!
        write_server_pid(server_process.pid)

        if server_log_path:
            logger.info("Writing server logs to %s", server_log_path)

        try:
            display_path = f"./{dist_dir.relative_to(Path.cwd())}"
        except Exception:
            display_path = dist_dir

        logger.info(f"Serving distributions from {display_path}")

        yield server_process

    except BaseException as exc:
        server_process.terminate()

        stdout, _ = server_process.communicate(timeout=1)
        if logger.getEffectiveLevel() <= logging.DEBUG:
            print(stdout.decode())

        server_process.kill()

        stdout, _ = server_process.communicate(timeout=1)
        if logger.getEffectiveLevel() <= logging.DEBUG:
            print(stdout.decode())

        # Do not reset the pidfile when a server was already running!
        if not isinstance(exc, ServeAddressInUse):
            reset_pidfile()

        raise


def add_vendored_build_deps(dist_dir: Path, offline: bool):
    build_directory = __development_base_path__ / "vendor" / "build"
    if build_directory.exists():
        logger.debug("Copying vendored build dependencies...")
        shutil.copytree(build_directory, dist_dir / "build", dirs_exist_ok=True)
    else:
        logger.warning("No vendored build dependencies found at %s" % build_directory)
        if offline:
            logger.error(
                "Server has no fallback PyPI access and source distribution builds are likely to fail"
            )


def get_packse_state_path(create: bool = True) -> Path:
    path = Path(os.environ.get("PACKSE_STATE_PATH") or (Path.home() / ".packse"))
    if create:
        path.mkdir(exist_ok=True)
    return path


def get_pidfile_path() -> Path:
    return get_packse_state_path() / "server.pid"


def get_server_pid() -> int | None:
    pidfile = get_pidfile_path()
    if not pidfile.exists():
        return None
    else:
        logger.debug("Found existing pid at %s", pidfile)
        return int(pidfile.read_text())


def write_server_pid(pid: int) -> None:
    pidfile = get_pidfile_path()
    pidfile.write_text(str(pid))


def reset_pidfile():
    pidfile = get_pidfile_path()
    pidfile.unlink(missing_ok=True)


def is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError as err:
        # ESRCH: pid not exist
        if err.errno == errno.ESRCH:
            return False
    return True


def sha256_file(path: Path):
    h = hashlib.sha256()

    with open(path, "rb") as file:
        while True:
            # Reading is buffered, so we can read smaller chunks.
            chunk = file.read(h.block_size)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def build_index(
    targets: list[Path],
    no_hash: bool,
    short_names: bool,
    dist_dir: Path | None,
):
    out_path = Path("./index")
    if out_path.exists():
        shutil.rmtree(out_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        if not dist_dir:
            logger.info("Building distributions...")
            build(
                targets,
                rm_destination=True,
                skip_root=False,
                short_names=short_names,
                no_hash=no_hash,
                dist_dir=tmpdir / "dist",
                build_dir=tmpdir / "build",
            )
            dist_dir = tmpdir / "dist"

        out_path.mkdir()
        (out_path / "files").mkdir()

        variables = inspect(targets, short_names=short_names, no_hash=no_hash)
        for scenario in variables["scenarios"]:
            for package in scenario["packages"]:
                # Create a new distributions section
                package["dists"] = []
                for version in package["versions"]:
                    for file in Path(
                        dist_dir
                        / (
                            scenario["name"]
                            if no_hash
                            else f"{scenario['name']}-{scenario['version']}"
                        )
                    ).iterdir():
                        if package["name"].replace("-", "_") + "-" + version[
                            "version"
                        ] not in str(file):
                            continue

                        # Include all the version information to start
                        dist = version.copy()
                        # Then add a sha256
                        dist["sha256"] = sha256_file(file)
                        dist["file"] = file.name
                        package["dists"].append(dist)
                        logger.info(
                            "Found distribution %s",
                            file.name,
                        )
                        file.rename(out_path / "files" / file.name)

        logger.info("Populating template...")
        create_from_template(
            out_path,
            "index",
            variables=variables,
        )

    logger.info("Built static index at ./%s", out_path)
