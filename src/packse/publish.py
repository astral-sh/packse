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


# Rate limits are defined at https://github.com/pypi/warehouse/blob/d858a996fe543131931955d8e8cc96b8aa7261a1/warehouse/config.py#L352-L369
# At the time of writing, rate limits enforce a maximum of 20 new projects / hour.
# Generally, retries aren't going to help.
MAX_ATTEMPTS = 3
RETRY_TIME = 60 * 2  # Start with two minutes
RETRY_BACKOFF_FACTOR = 1.5


def publish(
    targets: list[Path], skip_existing: bool, dry_run: bool, retry_on_rate_limit: bool
):
    for target in targets:
        if not target.is_dir():
            raise InvalidPublishTarget(target, reason="Not a directory.")

    s = "" if len(targets) == 1 else "s"
    logger.info("Publishing %s target%s...", len(targets), s)
    for target in targets:
        logger.info("Publishing '%s'...", target.name)
        for distfile in sorted(target.iterdir()):
            publish_package_distribution_with_retries(
                distfile,
                skip_existing=skip_existing,
                dry_run=dry_run,
                max_attempts=MAX_ATTEMPTS if retry_on_rate_limit else 1,
            )


def publish_package_distribution_with_retries(
    target: Path,
    skip_existing: bool,
    dry_run: bool,
    max_attempts: int,
):
    attempts = 0
    retry_time = RETRY_TIME
    while attempts < max_attempts:
        retry_time = retry_time * RETRY_BACKOFF_FACTOR
        attempts += 1
        try:
            publish_package_distribution(target, dry_run)
        except PublishAlreadyExists:
            if not skip_existing:
                raise
            logger.info("Skipped '%s': already published.", target.name)
        except PublishRateLimit:
            if attempts >= max_attempts:
                raise
            logger.warning(
                "Encountered rate limit publishing '%s', retrying in ~%d minutes",
                target.name,
                retry_time // 60,
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
        import os

        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT, env=os.environ
        )
    except subprocess.CalledProcessError as exc:
        output = exc.output.decode()
        if "File already exists" in output:
            raise PublishAlreadyExists(target.name)
        if "HTTPError: 429 Too Many Requests" in output:
            raise PublishRateLimit(target.name)
        raise PublishToolError(
            f"Publishing {target.name} with twine failed",
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
