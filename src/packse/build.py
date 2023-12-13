"""
Build packages for the given scenarios.
"""
import logging
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Generator

from packse.error import (
    BuildError,
    DestinationAlreadyExists,
    InvalidScenario,
    ScenarioNotFound,
)
from packse.scenario import Package, Scenario, load_scenario, scenario_prefix
from packse.template import create_from_template

logger = logging.getLogger(__name__)


def build(targets: list[Path], rm_destination: bool):
    # Validate all targets first
    for target in targets:
        if not target.exists():
            raise ScenarioNotFound(target)

        try:
            load_scenario(target)
        except Exception as exc:
            raise InvalidScenario(target, reason=str(exc)) from exc

    # Then build each one
    for target in targets:
        result = build_scenario(target, rm_destination)
        print(result)


def build_scenario(target: Path, rm_destination: bool) -> str:
    """
    Build the scenario defined at the given path.

    Returns the scenario's root package name.
    """
    scenario = load_scenario(target)
    prefix = scenario_prefix(scenario)

    work_dir = Path.cwd()
    build_destination = work_dir / "build" / prefix
    dist_destination = work_dir / "dist" / prefix

    logging.info(
        "Building '%s' in directory '%s'",
        prefix,
        build_destination.relative_to(work_dir),
    )

    if build_destination.exists():
        if rm_destination:
            shutil.rmtree(build_destination)
        else:
            raise DestinationAlreadyExists(build_destination)

    build_destination.mkdir(parents=True)

    if dist_destination.exists():
        if rm_destination:
            shutil.rmtree(dist_destination)
        else:
            raise DestinationAlreadyExists(dist_destination)

    dist_destination.mkdir(parents=True)

    for name, package in scenario.packages.items():
        build_scenario_package(
            scenario=scenario,
            prefix=prefix,
            name=name,
            package=package,
            work_dir=work_dir,
            build_destination=build_destination,
            dist_destination=dist_destination,
        )

    return f"{prefix}-{scenario.root}"


def build_scenario_package(
    scenario: Scenario,
    prefix: str,
    name: str,
    package: Package,
    work_dir: Path,
    build_destination: Path,
    dist_destination: Path,
):
    package_name = f"{prefix}-{name}"

    # Generate a Python module name
    module_name = package_name.replace("-", "_")

    for version, specification in package.versions.items():
        package_destination = create_from_template(
            build_destination,
            template_name=scenario.template,
            variables={
                "scenario-name": scenario.name,
                "package-name": package_name,
                "module-name": module_name,
                "version": version,
                "dependencies": [f"{prefix}-{spec}" for spec in specification.requires],
                "requires-python": specification.requires_python,
            },
        )

        logger.info(
            "Building %s with hatch",
            package_destination.relative_to(work_dir),
        )

        for dist in build_package_distributions(package_destination):
            shared_path = dist_destination / dist.name
            logger.info("Linked distribution to %s", shared_path.relative_to(work_dir))
            shared_path.hardlink_to(dist)


def build_package_distributions(target: Path) -> Generator[Path, None, None]:
    """
    Build package distributions, yield each built distribution path, then delete the distribution folder.
    """
    try:
        output = subprocess.check_output(
            ["hatch", "build"],
            cwd=target,
            stderr=subprocess.STDOUT,
        )

        yield from sorted((target / "dist").iterdir())
        shutil.rmtree(target / "dist")

    except subprocess.CalledProcessError as exc:
        raise BuildError(
            f"Building {target.name} with hatch failed",
            exc.output.decode(),
        )
    else:
        logger.debug(
            "Building %s:\n\n%s",
            target.name,
            textwrap.indent(output.decode(), " " * 4),
        )
