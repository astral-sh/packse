import errno
import logging
import os
import secrets
import shutil
import signal
import subprocess
import time
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory

from packse.error import ServeAddressInUse, ServeAlreadyRunning

logger = logging.getLogger(__name__)


def index_up(
    host: str = "localhost",
    port: int = 3141,
    background: bool = False,
    storage_path: Path | None = None,
    reset: bool = False,
):
    server_url = f"http://{host}:{port}"

    if background:
        if pid := get_server_pid(storage_path):
            if is_running(pid):
                raise ServeAlreadyRunning()

    storage_context = (
        nullcontext(storage_path)
        if storage_path is not None
        else (
            get_storage_directory(storage_path)
            if background
            else TemporaryDirectory(prefix="packse-serve-")
        )
    )
    with storage_context as storage_path:
        # Ensure we have the right type, tmpdir returns a string
        storage_path = Path(storage_path)
        server_storage = storage_path / "server"
        client_storage = storage_path / "client"

        if reset:
            logger.info("Clearing existing server data...")
            if server_storage.exists():
                shutil.rmtree(server_storage)
            if client_storage.exists():
                shutil.rmtree(client_storage)

        logger.debug("Storing data at %s", storage_path)

        if not server_storage.exists():
            init_server(server_storage)

        server_log_path = storage_path / "server.log" if background else None

        logger.info("Starting server at %s...", server_url)
        with start_index_server(
            storage_path, server_storage, host, port, server_log_path
        ) as server_process:
            init_client(client_storage, server_url)

            password = create_or_read_password(storage_path)

            username = "packages"
            create_user(
                username,
                client_storage,
                password,
                exists_ok=background,
            )

            logger.debug("Logging in...")
            login_user(username, password, client_storage)

            index = "packages/all"
            create_index(index, client_storage, exists_ok=background)

            index_url = f"{server_url}/{index}"
            logger.info("Index available at %s", index_url)

            if background:
                logger.info("Running in background with pid %s", server_process.pid)
                logger.info("Stop index server with `packse index down`.")
                print(index_url)
            else:
                logger.info("Ready! [Stop with Ctrl-C]")

                line = ""
                while True:
                    line = server_process.stdout.readline().decode()
                    if logger.getEffectiveLevel() <= logging.DEBUG:
                        print(line, end="")


def index_down(storage_path: Path | None) -> bool:
    storage_path = get_storage_directory(storage_path, create=False)

    if not storage_path.exists():
        logger.warning("No server detected!")
        return False

    if pid := get_server_pid(storage_path):
        if not is_running(pid):
            logger.info("Server looks shutdown already.")
            reset_pidfile(storage_path)
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

        reset_pidfile(storage_path)
        logger.info("Stopped server!")
        return True
    else:
        logger.warning("No server detected!")
        return False


@contextmanager
def start_index_server(
    storage_path: Path,
    server_storage: Path,
    host: str,
    port: int,
    server_log_path: Path,
) -> subprocess.Popen:
    server_url = f"http://{host}:{port}"

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
        stdout=server_log_path.open("wb") if server_log_path else subprocess.PIPE,
    )

    try:
        # Wait for server to be ready
        with server_log_path.open("rb") if server_log_path else nullcontext(
            server_process.stdout
        ) as server_output:
            line = ""
            while "Serving on" not in line:
                line = server_output.readline().decode()
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    print(line, end="")
                if "Address already in use" in line:
                    raise ServeAddressInUse(server_url)

        # Server started!
        write_server_pid(storage_path, server_process.pid)

        yield server_process

    except BaseException as exc:
        server_process.kill()

        # Do not reset the pidfile when a server was already running!
        if not isinstance(exc, ServeAddressInUse):
            reset_pidfile(storage_path)

        raise


def create_or_read_password(storage_path: Path) -> str:
    password_path = storage_path / "password"
    if password_path.exists():
        logger.debug("Using previously generated password...")
        password = password_path.read_text()
    else:
        logger.debug("Generating password...")
        password = secrets.token_urlsafe()
        password_path.write_text(password)
    return password


def init_server(server_storage: Path):
    logger.info("Initializing server...")
    subprocess.check_output(
        ["devpi-init", "--serverdir", str(server_storage)],
        stderr=subprocess.STDOUT,
    )


def init_client(client_storage: Path, server_url: str):
    logger.info("Configuring client...")
    subprocess.check_output(
        ["devpi", "use", "--clientdir", str(client_storage), server_url],
        stderr=subprocess.STDOUT,
    )


def create_index(name: str, client_storage: Path, exists_ok: bool = False):
    logger.info("Creating package index %r...", name)
    try:
        subprocess.check_output(
            [
                "devpi",
                "index",
                "--clientdir",
                str(client_storage),
                "-c",
                name,
                "bases=root/pypi",  # TODO(zanieb): Allow users to disable pull from real PyPI
                "volatile=False",
                "acl_upload=:ANONYMOUS:",  # Do not require auth to upload packages
            ],
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as exc:
        # TODO(zanieb): Improve these error handling cases
        if not exists_ok and "409 Conflict" not in exc.stdout.decode():
            raise


def create_user(
    username: str, client_storage: Path, password: str, exists_ok: bool = False
):
    logger.debug("Creating user %r...", username)
    try:
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
    except subprocess.CalledProcessError as exc:
        if (
            not exists_ok
            and "409 Conflict: user already exists" not in exc.stdout.decode()
        ):
            raise


def login_user(username: str, password: str, client_storage: Path):
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


def get_storage_directory(storage_path: Path | None, create: bool = True) -> Path:
    path = (
        storage_path
        or os.environ.get("PACKSE_STORAGE_PATH")
        or (Path.home() / ".packse")
    )
    if create:
        path.mkdir(exist_ok=True)
    return path


def get_pidfile_path(storage_path: Path | None) -> Path:
    return get_storage_directory(storage_path) / "server.pid"


def get_server_pid(storage_path: Path | None) -> int | None:
    pidfile = get_pidfile_path(storage_path)
    if not pidfile.exists():
        return None
    else:
        return int(pidfile.read_text())


def write_server_pid(storage_path: Path | None, pid: int) -> None:
    pidfile = get_pidfile_path(storage_path)
    pidfile.write_text(str(pid))


def reset_pidfile(storage_path: Path | None):
    pidfile = get_pidfile_path(storage_path)
    pidfile.unlink(missing_ok=True)


def is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError as err:
        # ESRCH: pid not exist
        if err.errno == errno.ESRCH:
            return False
    return True
