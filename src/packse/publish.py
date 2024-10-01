"""
Publish package distributions.
"""

import logging
import os
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_for_futures
from pathlib import Path

from packse.error import (
    InvalidPublishTarget,
    PublishAlreadyExists,
    PublishConnectionError,
    PublishError,
    PublishNoCredentials,
    PublishRateLimit,
    PublishToolError,
)

logger = logging.getLogger(__name__)


# Rate limits are defined at https://github.com/pypi/warehouse/blob/d858a996fe543131931955d8e8cc96b8aa7261a1/warehouse/config.py#L352-L369
# At the time of writing, rate limits enforce a maximum of 20 new projects / hour.
# Generally, retries aren't going to help.
MAX_ATTEMPTS = 3
RETRY_TIME = 1  # Start with one second
RETRY_BACKOFF_FACTOR = 1.5


def publish(
    targets: list[Path],
    index_url: str,
    skip_existing: bool,
    dry_run: bool,
    workers: int,
    anonymous: bool,
):
    start_time = time.time()

    if not anonymous and not (
        "UV_PUBLISH_PASSWORD" in os.environ or "PACKSE_PUBLISH_PASSWORD" in os.environ
    ):
        raise PublishNoCredentials()

    # Skip yanked markers
    targets = [target for target in targets if not str(target).endswith(".yanked")]

    for target in targets:
        if not target.is_dir():
            raise InvalidPublishTarget(target, reason="Not a directory.")

    s = "" if len(targets) == 1 else "s"
    logger.info("Publishing %s target%s to %s...", len(targets), s, index_url)
    for target in sorted(targets):
        logger.info("Publishing '%s'...", target.name)

    # Publish each directory
    with ThreadPoolExecutor(
        thread_name_prefix="packse-scenario-", max_workers=workers
    ) as executor:
        futures = [
            executor.submit(
                publish_package_distributions,
                target,
                index_url,
                skip_existing=skip_existing,
                dry_run=dry_run,
                anonymous=anonymous,
            )
            for target in targets
        ]

        wait_for_futures(futures)

    # All the futures are done since the executor context has exited; check if any failed
    incomplete = 0
    for future in futures:
        if (exc := future.exception()) is None:
            continue
        incomplete += 1
        print(f"{exc}.", file=sys.stderr)

    if incomplete:
        s = "" if targets == 1 else "s"
        raise PublishError(f"Failed to publish {incomplete}/{len(targets)} target{s}")

    total_files = 0
    for name, files in sorted(future.result() for future in futures):
        print(name)
        total_files += files

    for target in targets:
        yankfile = target.with_suffix(".yanked")
        if yankfile.exists():
            print()
            print(f"{target.name} has versions that must be yanked:")
            for package_version in yankfile.read_text().splitlines():
                package, version = package_version.rsplit("-", 1)
                url = (
                    index_url.replace("/legacy/", "/")
                    + f"manage/project/{package}/release/{version}/#yank_version-modal"
                )
                print(f"\t{package_version}: {url}")

    logger.info(
        "Published %s targets (%s new files) in %.2fs",
        len(futures),
        total_files,
        time.time() - start_time,
    )


def publish_package_distributions(
    target: Path,
    index_url: str,
    skip_existing: bool,
    dry_run: bool,
    anonymous: bool,
) -> tuple[str, int]:
    """
    Publish a directory of package distribution files.
    """
    files = 0
    for distfile in sorted(target.iterdir()):
        if publish_package_distribution_with_retries(
            distfile,
            index_url,
            skip_existing=skip_existing,
            dry_run=dry_run,
            anonymous=anonymous,
            max_attempts=MAX_ATTEMPTS,
        ):
            files += 1

    return (target.name, files)


def publish_package_distribution_with_retries(
    target: Path,
    index_url: str,
    skip_existing: bool,
    dry_run: bool,
    anonymous: bool,
    max_attempts: int,
) -> bool:
    """
    Publish a package distribution file with retries and error handling.
    """
    attempts = 0
    retry_time = RETRY_TIME
    while attempts < max_attempts:
        retry_time = retry_time * RETRY_BACKOFF_FACTOR
        attempts += 1
        try:
            publish_package_distribution(
                target, index_url, anonymous=anonymous, dry_run=dry_run
            )
        except PublishAlreadyExists:
            if not skip_existing:
                raise
            logger.info("Skipped '%s': already published.", target.name)
            return False
        except PublishConnectionError:
            if attempts >= max_attempts:
                raise
            logger.warning(
                "Encountered connection error publishing '%s', retrying in %ds",
                target.name,
                retry_time,
            )
            time.sleep(retry_time)
        else:
            logger.info("Published '%s'", target.name)
            break

    return True


def publish_package_distribution(
    target: Path, index_url: str, anonymous: bool, dry_run: bool
) -> None:
    """
    Publish a package distribution file.
    """
    command = ["uv", "publish", "--publish-url", index_url, str(target.resolve())]
    if dry_run:
        print("Would execute: " + " ".join(command))
        return

    start_time = time.time()
    try:
        env = os.environ.copy()

        # Pass the publish username through to twine
        if publish_username := os.environ.get("PACKSE_PUBLISH_USERNAME"):
            env["UV_PUBLISH_USERNAME"] = publish_username

        # Configure the username for tokens by default
        env.setdefault("UV_PUBLISH_USERNAME", "__token__")

        # Pass the publish token through to twine
        if publish_token := os.environ.get("PACKSE_PUBLISH_PASSWORD"):
            env["UV_PUBLISH_PASSWORD"] = publish_token

        # Provide a username and password even if we don't want to use them
        if anonymous:
            env["UV_PUBLISH_USERNAME"] = "ANON"
            env["UV_PUBLISH_PASSWORD"] = "ANON"

        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT, env=env, timeout=60
        )
    except subprocess.TimeoutExpired:
        raise PublishError(f"Publish of {target.name} timed out.")
    except subprocess.CalledProcessError as exc:
        output = exc.output.decode()
        if "File already exists" in output or "409 Conflict" in output:
            raise PublishAlreadyExists(target.name)
        if "HTTPError: 429 Too Many Requests" in output:
            raise PublishRateLimit(target.name)
        if "ConnectionError" in output:
            raise PublishConnectionError(target.name)
        raise PublishToolError(
            f"Publishing {target.name} with uv failed",
            output,
        )
    else:
        logs = (
            (":\n\n" + textwrap.indent(output.decode(), " " * 4))
            if logger.getEffectiveLevel() <= logging.DEBUG
            else ""
        )
        logger.debug(
            "Published %s in %.2fs%s",
            target.name,
            time.time() - start_time,
            logs,
        )
