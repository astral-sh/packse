"""
Build packages for the given scenarios.
"""
import logging
import shutil
import subprocess
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as wait_for_futures
from pathlib import Path
from typing import Generator

from packse.error import (
    BuildError,
    DestinationAlreadyExists,
    FileNotFound,
    InvalidScenario,
)
from packse.scenario import (
    Package,
    PackageMetadata,
    Scenario,
    load_scenarios,
    scenario_prefix,
)
from packse.template import TemplateConfig, create_from_template, load_template_config

logger = logging.getLogger(__name__)


def build(targets: list[Path], rm_destination: bool, short_names: bool):
    # Validate and collect all targets first
    scenarios = []

    for target in targets:
        if not target.exists():
            raise FileNotFound(target)

        try:
            logger.debug("Loading %s", target)
            scenarios.extend(load_scenarios(target))
        except Exception as exc:
            raise InvalidScenario(target, reason=str(exc)) from exc

    # Then build each one
    with ThreadPoolExecutor(thread_name_prefix="packse-scenario-") as executor:
        futures = [
            executor.submit(build_scenario, scenario, rm_destination, short_names)
            for scenario in scenarios
        ]

        wait_for_futures(futures)

    results = [future.result() for future in futures]
    for result in sorted(results):
        print(result)


def build_scenario(scenario: Scenario, rm_destination: bool, short_names: bool) -> str:
    """
    Build the scenario defined at the given path.

    Returns the scenario's entrypoint package name.
    """
    prefix = scenario_prefix(scenario, short_names)

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

    with ThreadPoolExecutor(thread_name_prefix="packse-build-") as executor:
        futures = [
            executor.submit(
                build_scenario_package,
                scenario=scenario,
                prefix=prefix,
                name=name,
                package=package,
                work_dir=work_dir,
                build_destination=build_destination,
                dist_destination=dist_destination,
            )
            for name, package in scenario.packages.items()
        ]

        futures.append(
            executor.submit(
                build_scenario_package,
                scenario=scenario,
                prefix=prefix,
                name="",
                package=make_root_package(scenario),
                work_dir=work_dir,
                build_destination=build_destination,
                dist_destination=dist_destination,
            )
        )

        wait_for_futures(futures)
        for future in futures:
            # TODO(zanieb): Display _all_ of the errors to the user
            future.result()

    logger.info(
        "Built scenario '%s' in %.2fs",
        prefix,
        time.time() - start_time,
    )
    return prefix


def make_root_package(scenario: Scenario) -> Package:
    """
    Generate a full package from the root package of the scenario.
    """
    return Package(
        versions={
            "0.0.0": PackageMetadata(
                requires=scenario.root.requires,
                requires_python=scenario.root.requires_python,
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
    template_config: TemplateConfig, package_version: PackageMetadata, target: Path
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

    # Create wheels with other tags if requested
    if package_version.wheel and package_version.wheel_tags:
        default_tag_wheel = None
        for dist in (target / "dist").iterdir():
            if dist.name.endswith("py3-none-any.whl"):
                default_tag_wheel = dist
                break
        if not default_tag_wheel:
            raise BuildError("No wheel found with tag `py3-none-any`.")

        # Since we always build a universal wheel, we just create copies of it for other platforms
        # which means we're lying about the compatibility of the wheel but it will always be installable
        # on the given platform.
        for tag in package_version.wheel_tags:
            if tag == "py3-none-any":
                continue

            new_tag_wheel = (
                target / "dist" / default_tag_wheel.name.replace("py3-none-any", tag)
            )
            new_tag_wheel.hardlink_to(default_tag_wheel)
            logger.debug("Created wheel %s", new_tag_wheel.name)

        # Delete the default wheel if not requested
        if "py3-none-any" not in package_version.wheel_tags:
            default_tag_wheel.unlink()

    yield from sorted((target / "dist").iterdir())
    shutil.rmtree(target / "dist")


def build_package(
    name: str,
    version: str,
    no_wheel: bool,
    no_sdist: bool,
    wheel_tags: list[str],
    rm_destination: bool,
):
    """
    Build a package without a scenario
    """

    work_dir = Path.cwd()
    build_destination = work_dir / "build" / name
    dist_destination = work_dir / "dist" / name
    start_time = time.time()

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
    package_name = name
    package_version = PackageMetadata(
        sdist=not no_sdist, wheel=not no_wheel, wheel_tags=wheel_tags
    )
    module_name = package_name.replace("-", "_")

    template_config = load_template_config("simple")

    logger.debug("Generating project for '%s-%s'", package_name, version)

    package_destination = create_from_template(
        build_destination,
        template_name="simple",
        variables={
            "package-name": package_name,
            "module-name": module_name,
            "version": version,
            "dependencies": [],
            "requires-python": package_version.requires_python,
            "description": package_version.description,
        },
    )

    logger.info(
        "Generated project for '%s-%s'",
        package_name,
        version,
    )

    for dist in build_package_distributions(
        template_config, package_version, package_destination
    ):
        shared_path = dist_destination / dist.name
        logger.info("Linked distribution to %s", shared_path.relative_to(work_dir))
        shared_path.hardlink_to(dist)

    logger.info(
        "Done in %.2fms",
        (time.time() - start_time) * 1000.0,
    )
