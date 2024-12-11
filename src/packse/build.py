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

import packaging.version

from packse.error import (
    BuildError,
    DestinationAlreadyExists,
    FileNotFound,
    InvalidPackageVersion,
    InvalidScenario,
)
from packse.scenario import (
    Package,
    PackageMetadata,
    Scenario,
    find_scenario_files,
    load_scenarios,
    scenario_hash,
)
from packse.template import TemplateConfig, create_from_template, load_template_config

logger = logging.getLogger(__name__)


def build(
    targets: list[Path],
    rm_destination: bool,
    short_names: bool,
    no_hash: bool,
    skip_root: bool,
    dist_dir: Path | None = None,
    build_dir: Path | None = None,
):
    start_time = time.time()

    # Validate and collect all targets first
    scenarios = []
    dist_dir = dist_dir or (Path.cwd() / "dist")
    build_dir = build_dir or (Path.cwd() / "build")

    for target in targets:
        if not target.exists():
            raise FileNotFound(target)

        if target.is_dir():
            for target in find_scenario_files(target):
                try:
                    logger.debug("Loading %s", target)
                    scenarios.extend(load_scenarios(target))
                except Exception as exc:
                    invalid = InvalidScenario(target, reason=str(exc))
                    print(f"Skipping file: {invalid}")
        else:
            try:
                logger.debug("Loading %s", target)
                scenarios.extend(load_scenarios(target))
            except Exception as exc:
                raise InvalidScenario(target, reason=str(exc)) from exc

    # Then build each one
    with ThreadPoolExecutor(thread_name_prefix="packse-scenario-") as executor:
        futures = [
            executor.submit(
                build_scenario,
                scenario,
                rm_destination,
                short_names,
                no_hash,
                skip_root,
                build_dir,
                dist_dir,
            )
            for scenario in scenarios
        ]

        wait_for_futures(futures)

    results = [future.result() for future in futures]
    for result in sorted(results):
        print(result)

    logger.info(
        "Built %s scenarios in %.2fs",
        len(results),
        time.time() - start_time,
    )


def build_scenario(
    scenario: Scenario,
    rm_destination: bool,
    short_names: bool,
    no_hash: bool,
    skip_root: bool,
    build_dir: Path,
    dist_dir: Path,
) -> str:
    """
    Build the scenario defined at the given path.

    Returns the scenario's entrypoint package name.
    """

    hash = scenario_hash(scenario)
    name = scenario.name
    if not no_hash:
        name = f"{name}-{hash}"

    build_destination = build_dir / name
    dist_destination = dist_dir / name
    start_time = time.time()

    logger.info(
        "Building '%s' in directory '%s'",
        name,
        build_destination,
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
                scenario_version=hash,
                name=name,
                package=package,
                build_destination=build_destination,
                dist_destination=dist_destination,
                short_names=short_names,
                no_hash=no_hash,
            )
            for name, package in scenario.packages.items()
        ]

        if not skip_root:
            futures.append(
                executor.submit(
                    build_scenario_package,
                    scenario=scenario,
                    scenario_version=hash,
                    name=scenario.name,
                    package=make_root_package(scenario),
                    build_destination=build_destination,
                    dist_destination=dist_destination,
                    short_names=short_names,
                    no_hash=no_hash,
                )
            )

        wait_for_futures(futures)
        for future in futures:
            # TODO(zanieb): Display _all_ of the errors to the user
            future.result()

    logger.info(
        "Built scenario '%s' in %.2fs",
        name,
        time.time() - start_time,
    )
    return name


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
    scenario_version: str,
    name: str,
    package: Package,
    build_destination: Path,
    dist_destination: Path,
    short_names: bool,
    no_hash: bool,
):
    package_name = name
    if not no_hash:
        package_name = f"{package_name}-{scenario_version}"
    if not short_names and name != scenario.name:
        package_name = f"{scenario.name}-{package_name}"

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
                    requirement.with_unique_name(
                        scenario, scenario_version, short_names, no_hash
                    )
                    for requirement in package_version.requires
                ],
                "optional-dependencies": [
                    {
                        "name": extra,
                        "dependencies": [
                            requirement.with_unique_name(
                                scenario, scenario_version, short_names, no_hash
                            )
                            for requirement in depends
                        ],
                    }
                    for extra, depends in package_version.extras.items()
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
            logger.debug("Linked distribution to %s", shared_path)
            shared_path.hardlink_to(dist)

        if package_version.yanked:
            with dist_destination.with_suffix(".yanked").open("a+") as yanked:
                yanked.write(f"{package_name}-{version}")
                yanked.write("\n")
            logger.info("Marked %s-%s as yanked", package_name, version)


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
            raise BuildError("No wheel found with tag `py3-none-any`", "")

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
    requires_python: str | None,
    wheel_tags: list[str],
    rm_destination: bool,
):
    """
    Build a package without a scenario
    """

    try:
        packaging.version.Version(version)
    except Exception:
        raise InvalidPackageVersion(version) from None

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
    extra = {}
    if requires_python is not None:
        extra["requires_python"] = requires_python
    package_version = PackageMetadata(
        sdist=not no_sdist, wheel=not no_wheel, wheel_tags=wheel_tags, **extra
    )
    module_name = package_name.replace("-", "_")

    template_config = load_template_config("package")

    logger.debug("Generating project for '%s-%s'", package_name, version)

    package_destination = create_from_template(
        build_destination,
        template_name="package",
        variables={
            "package-name": package_name,
            "module-name": module_name,
            "version": version,
            "dependencies": [],
            "optional-dependencies": [],
            "requires-python": package_version.requires_python,
            "description": package_version.description,
        },
    )

    logger.info(
        "Generated project for '%s-%s'in %.2fms",
        package_name,
        version,
        (time.time() - start_time) * 1000.0,
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
