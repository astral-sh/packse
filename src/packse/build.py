"""
Build packages for the given scenarios.
"""
import logging
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Generator

from packse.error import (
    BuildError,
    DestinationAlreadyExists,
    InvalidScenario,
    ScenarioNotFound,
)
from packse.scenario import (
    Package,
    PackageVersion,
    Scenario,
    load_scenarios,
    scenario_prefix,
)
from packse.template import TemplateConfig, create_from_template, load_template_config

logger = logging.getLogger(__name__)


def build(targets: list[Path], rm_destination: bool):
    # Validate and collect all targets first
    scenarios = []

    for target in targets:
        if not target.exists():
            raise ScenarioNotFound(target)

        try:
            logger.debug("Loading %s", target)
            scenarios.extend(load_scenarios(target))
        except Exception as exc:
            raise InvalidScenario(target, reason=str(exc)) from exc

    # Then build each one
    for scenario in scenarios:
        result = build_scenario(scenario, rm_destination)
        print(result)


def build_scenario(scenario: Scenario, rm_destination: bool) -> str:
    """
    Build the scenario defined at the given path.

    Returns the scenario's entrypoint package name.
    """
    prefix = scenario_prefix(scenario)

    work_dir = Path.cwd()
    build_destination = work_dir / "build" / prefix
    dist_destination = work_dir / "dist" / prefix
    start_time = time.time()

    logger.info(
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

    build_scenario_package(
        scenario=scenario,
        prefix=prefix,
        name="",
        package=make_entrypoint_package(scenario),
        work_dir=work_dir,
        build_destination=build_destination,
        dist_destination=dist_destination,
    )

    logger.info(
        "Built scenario '%s' in %.2fs",
        prefix,
        time.time() - start_time,
    )
    return prefix


def make_entrypoint_package(scenario: Scenario) -> Package:
    """
    Generate an entrypoint `Package` for a scenario that just requires the scenario root package.
    """
    return Package(
        versions={
            "0.0.0": PackageVersion(
                requires=[scenario.root],
                # Do not build wheels for the root package
                wheel=False,
                # The scenario's description is used for the entrypoint package
                description=scenario.description,
            )
        }
    )


def build_scenario_package(
    scenario: Scenario,
    prefix: str,
    name: str,
    package: Package,
    work_dir: Path,
    build_destination: Path,
    dist_destination: Path,
):
    # Only allow the name to be empty for entrypoint packages
    assert name or list(package.versions.keys()) == ["0.0.0"]

    package_name = f"{prefix}-{name}" if name else prefix

    # Generate a Python module name
    module_name = package_name.replace("-", "_")

    template_config = load_template_config(scenario.template)

    for version, package_version in package.versions.items():
        start_time = time.time()

        logger.debug("Generating project for '%s-%s'", package_name, version)
        package_destination = create_from_template(
            build_destination,
            template_name=scenario.template,
            variables={
                "scenario-name": scenario.name,
                "package-name": package_name,
                "module-name": module_name,
                "version": version,
                "dependencies": [
                    f"{prefix}-{spec}" for spec in package_version.requires
                ],
                "requires-python": package_version.requires_python,
                "description": package_version.description,
            },
        )

        logger.info(
            "Generated project for '%s-%s' in %.2fms",
            package_name,
            version,
            (time.time() - start_time) * 1000.0,
        )

        for dist in build_package_distributions(
            template_config, package_version, package_destination
        ):
            shared_path = dist_destination / dist.name
            logger.debug("Linked distribution to %s", shared_path.relative_to(work_dir))
            shared_path.hardlink_to(dist)


def build_package_distributions(
    template_config: TemplateConfig, package_version: PackageVersion, target: Path
) -> Generator[Path, None, None]:
    """
    Build package distributions, yield each built distribution path, then delete the distribution folder.
    """
    command = template_config.build_base

    if package_version.sdist:
        command.extend(template_config.build_sdist)
    if package_version.wheel:
        command.extend(template_config.build_wheel)

    start_time = time.time()

    try:
        output = subprocess.check_output(command, cwd=target, stderr=subprocess.STDOUT)

    except subprocess.CalledProcessError as exc:
        raise BuildError(
            f"Building {target.name} with hatch failed",
            exc.output.decode(),
        )
    else:
        logs = (
            (":\n\n" + textwrap.indent(output.decode(), " " * 4))
            if logger.getEffectiveLevel() <= logging.DEBUG
            else ""
        )
        logger.info(
            "Built package '%s' in %.2fs%s",
            target.name,
            time.time() - start_time,
            logs,
        )

    yield from sorted((target / "dist").iterdir())
    shutil.rmtree(target / "dist")
