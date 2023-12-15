"""
Serve the given
"""
import subprocess
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory
import logging
from contextlib import nullcontext

from packse.error import ServeAddressInUse


logger = logging.getLogger(__name__)


def serve(
    targets: list[Path],
    host: str = "localhost",
    port: int = 3141,
    storage_path: Path | None = None,
):
    # `targets` are optional, if not provided we just won't build and publish them

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
            logger.info("Index available at http://127.0.0.1:3141/packages/all")
            logger.info("Ready!")

            # TODO(zanieb): Stream logs from this process
            server_process.wait()

        except BaseException:
            server_process.kill()
            raise
