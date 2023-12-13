import json
import logging
from pathlib import Path
from typing import Any

from packse.templates import __templates_path__

TEMPLATE_VERSION = ".template-version"

logger = logging.getLogger(__name__)


def get_template_version(template_name: str) -> str:
    template_path = __templates_path__ / template_name
    version_path = template_path / TEMPLATE_VERSION
    if version_path.exists():
        return version_path.read_text()
    else:
        return "0"


def create_from_template(
    destination: Path, template_name: str, variables: dict[str, Any]
) -> Path:
    template_path = __templates_path__ / template_name
    first_root = None
    for root, _, files in template_path.walk():
        # Determine the new directory path in the destination
        new_root = destination / Path(
            replace_placeholders(str(root), variables)
        ).relative_to(template_path)

        if new_root == destination:
            continue

        if not first_root:
            first_root = new_root

        # Create the new directory
        logger.info("Creating %s", new_root.relative_to(destination))
        new_root.mkdir()

        for file in files:
            file_path = root / file

            # Determine the new file path
            new_file_path = new_root / replace_placeholders(file, variables)
            logger.info("Creating %s", new_file_path.relative_to(destination))

            new_file_path.write_text(
                replace_placeholders(file_path.read_text(), variables)
            )

    return first_root


def replace_placeholders(target: str, variables: dict[str, Any]):
    for key, value in variables.items():
        target = target.replace(f"{{{{ {key} }}}}", stringify(value))
    return target


def stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    else:
        # TOOD(zanieb): Consider inferring the format from the file extension
        return json.dumps(value)
