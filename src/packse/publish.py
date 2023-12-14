"""
Publish package distributions.
"""
import logging
import subprocess
import textwrap
import time
from pathlib import Path

from packse.error import (
    InvalidPublishTarget,
    PublishAlreadyExists,
    PublishRateLimit,
    PublishToolError,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_RETRY_TIME = 10
RETRY_BACKOFF_FACTOR = 2


def publish(targets: list[Path], skip_existing: bool, dry_run: bool):
    for target in targets:
        if not target.is_dir():
            raise InvalidPublishTarget(target, reason="Not a directory.")

    s = "" if len(targets) == 1 else "s"
    logger.info("Publishing %s target%s...", len(targets), s)
    for target in targets:
        logger.info("Publishing '%s'...", target.name)
        for distfile in sorted(target.iterdir()):
            publish_package_distribution_with_retries(distfile, skip_existing, dry_run)


def publish_package_distribution_with_retries(
    target: Path, skip_existing: bool, dry_run: bool
):
    retries = 0
    retry_time = INITIAL_RETRY_TIME
    while retries < MAX_RETRIES:
        retry_time = retry_time * RETRY_BACKOFF_FACTOR
        retries += 1
        try:
            publish_package_distribution(target, dry_run)
        except PublishAlreadyExists:
            if not skip_existing:
                raise
            logger.info("Skipped '%s': already published.", target.name)
        except PublishRateLimit:
            if retries >= MAX_RETRIES:
                raise
            logger.warning(
                "Encountered rate limit publishing '%s', retrying in %d seconds",
                target.name,
                retry_time,
            )
            time.sleep(retry_time)
        else:
            logger.info("Published '%s'", target.name)
            break


def publish_package_distribution(target: Path, dry_run: bool) -> None:
    """
    Publish package distribution.
    """
    command = ["twine", "upload", "-r", "testpypi", str(target.resolve())]
    if dry_run:
        print("Would execute: " + " ".join(command))
        return

    start_time = time.time()
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        output = exc.output.decode()
        if "File already exists" in output:
            raise PublishAlreadyExists(target.name)
        if "HTTPError: 429 Too Many Requests" in output:
            raise PublishRateLimit(target.name)
        raise PublishToolError(
            f"Publishing {target} with twine failed",
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
