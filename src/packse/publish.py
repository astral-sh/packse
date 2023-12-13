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


def publish(targets: list[Path], skip_existing: bool = True):
    for target in targets:
        if not target.is_dir():
            raise InvalidPublishTarget(target, reason="Not a directory.")

    logger.info("Publishing %s targets...", len(targets))
    for target in targets:
        logger.info("Publishing '%s'...", target.name)
        for distfile in target.iterdir():
            try:
                publish_package_distribution(distfile)
            except PublishAlreadyExists:
                if not skip_existing:
                    raise
                logger.info("Skipped '%s': already published.", distfile.name)
            else:
                logger.info("Published '%s'", distfile.name)


def publish_package_distribution(target: Path) -> None:
    """
    Publish package distribution.
    """
    try:
        output = subprocess.check_output(
            ["twine", "upload", "-r", "testpypi", str(target.resolve())],
            stderr=subprocess.STDOUT,
        )
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
