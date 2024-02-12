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
RETRY_TIME = 60 * 2  # Start with two minutes
RETRY_BACKOFF_FACTOR = 1.5


def publish(
    targets: list[Path],
    index_url: str,
    skip_existing: bool,
    dry_run: bool,
    retry_on_rate_limit: bool,
    workers: int,
    anonymous: bool,
):
    if not anonymous and not (
        "TWINE_PASSWORD" in os.environ or "PACKSE_PUBLISH_PASSWORD" in os.environ
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
                retry_on_rate_limit=retry_on_rate_limit,
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

    for result in sorted(future.result() for future in futures):
        print(result)

    for target in targets:
        yankfile = target.with_suffix(".yanked")
        if yankfile.exists():
            url = (
                index_url.replace("/legacy/", "/")
                + f"manage/project/{target.name}/release"
            )
            print()
            print(f"{target.name} has versions that must be yanked:")
            for version in yankfile.read_text().splitlines():
                print(f"\t{version}: {url}/{version}/#yank_version-modal")


def publish_package_distributions(
    target: Path,
    index_url: str,
    skip_existing: bool,
    dry_run: bool,
    anonymous: bool,
    retry_on_rate_limit: bool,
) -> str:
    """
    Publish a directory of package distribution files.
    """
    for distfile in sorted(target.iterdir()):
        publish_package_distribution_with_retries(
            distfile,
            index_url,
            skip_existing=skip_existing,
            dry_run=dry_run,
            anonymous=anonymous,
            max_attempts=MAX_ATTEMPTS if retry_on_rate_limit else 1,
        )

    return target.name


def publish_package_distribution_with_retries(
    target: Path,
    index_url: str,
    skip_existing: bool,
    dry_run: bool,
    anonymous: bool,
    max_attempts: int,
):
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


def publish_package_distribution(
    target: Path, index_url: str, anonymous: bool, dry_run: bool
) -> None:
    """
    Publish a package distribution file.
    """
    command = ["twine", "upload", "--repository-url", index_url, str(target.resolve())]
    if dry_run:
        print("Would execute: " + " ".join(command))
        return

    start_time = time.time()
    try:
        env = os.environ.copy()
        # Ensure twine does not prompt for credentials
        env["TWINE_NON_INTERACTIVE"] = "1"

        # Pass the publish username through to twine
        if publish_username := os.environ.get("PACKSE_PUBLISH_USERNAME"):
            env["TWINE_USERNAME"] = publish_username

        # Configure the username for tokens by default
        env.setdefault("TWINE_USERNAME", "__token__")

        # Pass the publish token through to twine
        if publish_token := os.environ.get("PACKSE_PUBLISH_PASSWORD"):
            env["TWINE_PASSWORD"] = publish_token

        # Twine requires a username and password even if we don't want to use them
        if anonymous:
            env["TWINE_USERNAME"] = "ANON"
            env["TWINE_PASSWORD"] = "ANON"

        output = subprocess.check_output(
            command, stderr=subprocess.STDOUT, env=env, timeout=60
        )
    except subprocess.TimeoutExpired:
        raise PublishError(f"Publish of {target.name} timed out.")
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
