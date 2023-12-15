import logging
import secrets
import subprocess
import os
import signal
import time
from contextlib import nullcontext
import errno
from pathlib import Path
from tempfile import TemporaryDirectory

from packse.error import ServeAddressInUse

logger = logging.getLogger(__name__)


def get_storage_directory() -> Path:
    path = os.environ.get("PACKSE_STORAGE_PATH", Path.home() / ".packse")
    path.mkdir(exist_ok=True)
    return path


def get_pidfile_path() -> Path:
    return get_storage_directory() / "server.pid"


def get_server_pid() -> int | None:
    pidfile = get_pidfile_path()
    if not pidfile.exists():
        return None
    else:
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
        # ESRCH: PID not exist
        if err.errno == errno.ESRCH:
            return False
    return True


def start_server(
    host: str = "localhost",
    port: int = 3141,
    storage_path: Path | None = None,
    background: bool = False,
):
    storage_context = (
        nullcontext(storage_path)
        if storage_path is not None
        else TemporaryDirectory(prefix="packse-serve-")
    )
    with storage_context as storage_path:
        # Ensure we have the right type, tmpdir returns a string
        storage_path = Path(storage_path)
        server_storage = storage_path / "server"
        client_storage = storage_path / "client"

        logger.debug("Storing data at %s", storage_path)

        logger.info("Initializing server...")
        subprocess.check_output(
            ["devpi-init", "--serverdir", str(server_storage)], stderr=subprocess.STDOUT
        )

        server_url = f"http://{host}:{port}"
        logger.info("Starting server at %s...", server_url)
        # TODO(zanieb): Check if server port is in use already
        server_process = subprocess.Popen(
            [
                "devpi-server",
                "--serverdir",
                str(server_storage),
                # Future default, let's just opt-in now for better output
                "--absolute-urls",
                "--host",
                host,
                "--port",
                str(port),
            ],
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,
        )

        # TODO(zanieb): Factor this into a utility
        try:
            line = ""
            while "Serving on" not in line:
                line = server_process.stdout.readline().decode()
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    print(line, end="")
                if "Address already in use" in line:
                    raise ServeAddressInUse(server_url)

            # Server started!
            write_server_pid(server_process.pid)

            logger.info("Configuring client...")
            subprocess.check_output(
                ["devpi", "use", "--clientdir", str(client_storage), server_url],
                stderr=subprocess.STDOUT,
            )

            logger.debug("Generating password...")
            password = secrets.token_urlsafe()
            username = "packages"

            logger.debug("Creating user %r...", username)
            subprocess.check_output(
                [
                    "devpi",
                    "user",
                    "--clientdir",
                    str(client_storage),
                    "-c",
                    username,
                    "email=null",
                    f"password={password}",
                ],
                stderr=subprocess.STDOUT,
            )

            logger.debug("Logging in...")
            subprocess.check_output(
                [
                    "devpi",
                    "login",
                    "--clientdir",
                    str(client_storage),
                    username,
                    f"--password={password}",
                ],
                stderr=subprocess.STDOUT,
            )

            index = "packages/all"
            logger.info("Creating package index %r...", index)
            subprocess.check_output(
                [
                    "devpi",
                    "index",
                    "--clientdir",
                    str(client_storage),
                    "-c",
                    index,
                    "bases=root/pypi",  # TODO(zanieb): Allow users to disable pull from real PyPI
                    "volatile=False",
                    "acl_upload=:ANONYMOUS:",  # Do not require auth to upload packages
                ],
                stderr=subprocess.STDOUT,
            )

            index_url = f"http://{host}:{port}/{index}"
            logger.info("Index available at %s", index_url)
            logger.info("Ready!")

            if background:
                logger.info("Running in background with PID %s", server_process.pid)
                logger.info("Stop server with `packse server stop`.")
                print(index_url)
            else:
                # TODO(zanieb): Stream logs from this process
                logger.info("[Stop with Ctrl-C]")
                server_process.wait()
                reset_pidfile()

        except BaseException as exc:
            server_process.kill()

            # Do not reset the pidfile when a server was already running!
            if not isinstance(exc, ServeAddressInUse):
                reset_pidfile()

            raise


def stop_server():
    if pid := get_server_pid():
        logger.info("Stopping server at PID %s...", pid)
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
    else:
        logger.warning("No server detected!")
