import fnmatch
import logging
import re
from pathlib import Path
from typing import Any

import chevron_blue
import msgspec

from packse.templates import __templates_path__

TEMPLATE_CONFIG = "template.toml"

logger = logging.getLogger(__name__)


class TemplateConfig(msgspec.Struct):
    version: int
    build_base: list[str]
    build_sdist: list[str]
    build_wheel: list[str]


def load_template_config(template_name: str) -> TemplateConfig:
    template_path = __templates_path__ / template_name
    config = template_path / TEMPLATE_CONFIG
    if not config.exists():
        raise RuntimeError(f"Template {template_name} missing config file.")
    return msgspec.toml.decode(config.read_text(), type=TemplateConfig)


def create_from_template(
    destination: Path, template_name: str, variables: dict[str, Any]
) -> Path:
    template_path = __templates_path__ / template_name
    first_root = None
    ignore_files = ["*.pyc"]
    for root, _, files in template_path.walk():
        for ignore in ignore_files:
            files = [file for file in files if not fnmatch.fnmatch(file, ignore)]

        for loop_root, scope in parse_loop(root, variables):
            # Determine the new directory path in the destination
            new_root = destination / Path(
                chevron_blue.render(str(loop_root), scope, no_escape=True)
            ).relative_to(template_path)

            if new_root == destination:
                continue

            if not first_root:
                first_root = new_root

            # Create the new directory
            logger.debug("Creating %s", new_root.relative_to(destination))
            new_root.mkdir()

            for file in files:
                file_path = root / file

                # Determine the new file path
                new_file_path = new_root / chevron_blue.render(
                    file, scope, no_escape=True
                )
                logger.debug("Creating %s", new_file_path.relative_to(destination))

                new_file_path.write_text(
                    chevron_blue.render(file_path.read_text(), scope, no_escape=True)
                )

    return first_root


def parse_loop(path: Path, variables: dict[str, Any]):
    # This implementation is pretty dubious and certain to fail on edge-cases
    scope = variables
    scopes = []
    matches = re.findall(r"\[\[(.*?)\]\]", str(path))
    if not matches:
        return [(path, variables)]

    scopes = variables[matches[0].strip()]
    for match in matches[1:]:
        match: str = match.strip()
        scopes = [scope[match] for scope in scopes if match in scope]

    results = []
    for scope in scopes:
        for inner in scope:
            results.append(
                (
                    Path(re.sub(r"\[\[(.*?)\]\]", "", str(path))),
                    inner,
                )
            )
    return results
