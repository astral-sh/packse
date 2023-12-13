"""
Publish package distributions.
"""
import logging
import subprocess
import textwrap
from pathlib import Path

from packse.error import (
    InvalidPublishTarget,
    PublishAlreadyExists,
    PublishError,
)

logger = logging.getLogger(__name__)


def publish(targets: list[Path], skip_existing: bool, dry_run: bool):
    for target in targets:
        if not target.is_dir():
            raise InvalidPublishTarget(target, reason="Not a directory.")

    s = "" if len(targets) == 1 else "s"
    logger.info("Publishing %s target%s...", len(targets), s)
    for target in targets:
        logger.info("Publishing '%s'...", target.name)
        for distfile in sorted(target.iterdir()):
            try:
                publish_package_distribution(distfile, dry_run)
            except PublishAlreadyExists:
                if not skip_existing:
                    raise
                logger.info("Skipped '%s': already published.", distfile.name)
            else:
                logger.info("Published '%s'", distfile.name)


def publish_package_distribution(target: Path, dry_run: bool) -> None:
    """
    Publish package distribution.
    """
    command = ["twine", "upload", "-r", "testpypi", str(target.resolve())]
    if dry_run:
        print("Would execute: " + " ".join(command))
        return

    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        output = exc.output.decode()
        if "File already exists" in output:
            raise PublishAlreadyExists(target.name)
        raise PublishError(
            f"Publishing {target} with twine failed",
            output,
        )
    else:
        logger.debug(
            "Publishing %s:\n\n%s",
            target.name,
            textwrap.indent(output.decode(), " " * 4),
        )
