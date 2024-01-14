"""
View package tree for the given scenarios.
"""
import logging
from pathlib import Path

from packaging.requirements import Requirement

from packse.error import FileNotFound, InvalidScenario
from packse.scenario import (
    Package,
    Scenario,
    load_scenarios,
    scenario_version,
)

logger = logging.getLogger(__name__)


def view(targets: list[Path], name: str | None = None, short_names: bool = False):
    scenarios = []

    # Validate and collect all targets first
    for target in targets:
        if not target.exists():
            raise FileNotFound(target)

        try:
            logger.debug("Loading %s", target)
            scenarios.extend(load_scenarios(target))
        except Exception as exc:
            raise InvalidScenario(target, reason=str(exc)) from exc

    # Then view each one
    for scenario in scenarios:
        if (
            name is not None
            # Allow user to provide the name with or without the version / name
            and scenario.name != name
            and f"{scenario.name}-{scenario_version(scenario)}" != name
            and scenario_version(scenario) != name
        ):
            logging.debug("Skipping %s", scenario.name)
            continue

        # When viewing a single scenario, show the name and description
        if name is not None:
            print(scenario.name)
            print()
            print(scenario.description)
            print()
        else:
            logging.debug("Viewing %s", scenario.name)

        view_scenario(scenario, short_names)


def view_scenario(scenario: Scenario, short_names: bool):
    name = scenario_version(scenario)
    if not short_names:
        name = f"{scenario.name}-{name}"

    print(name)
    print(dependency_tree(scenario))


def dependency_tree(scenario: Scenario) -> str:
    """
    Generate a dependency tree for a scenario
    """

    space = "    "
    branch = "│   "
    tee = "├── "
    last = "└── "
    buffer = ""

    packages = scenario.packages.copy()
    packages["root"] = Package(versions={"0.0.0": scenario.root})

    def render_versions(
        package: str,
        prefix: str = "",
        for_requirement: Requirement | None = None,
    ):
        versions = packages[package].versions
        if for_requirement:
            versions = {
                version: metadata
                for version, metadata in versions.items()
                if for_requirement.specifier.contains(version)
            }

            if not versions:
                yield prefix + last + "unsatisfied: no matching version"
                return

        show_versions = []
        for version, version_metadata in versions.items():
            show_versions.append(
                (
                    version,
                    version_metadata.requires
                    + [f"python{version_metadata.requires_python}"],
                )
            )
            extras = version_metadata.extras

            for extra, extra_depends in extras.items():
                show_versions.append((f"{version}[{extra}]", extra_depends))

        pointers = [tee] * (len(show_versions) - 1) + [last]
        for pointer, (version, requirements) in zip(pointers, show_versions):
            message = "satisfied by " if for_requirement and package else ""
            yield prefix + pointer + message + f"{package}-{version}"

            if not for_requirement:
                extension = branch if pointer == tee else space
                yield from render_requirements(
                    requirements,
                    prefix=prefix + extension,
                )

    def render_requirements(requirements: list[str], prefix: str = ""):
        for index, requirement in enumerate(requirements):
            # TODO: Consider avoiding parsing the requirement twice
            parsed_requirement = Requirement(requirement)

            # Skip display of Python requirements that are satisfied and not complex
            # We do this before the following iteration so the pointers are correct
            if (
                parsed_requirement.name == "python"
                and parsed_requirement.specifier.contains(scenario.environment.python)
                and len(parsed_requirement.specifier) == 1
                and next(iter(parsed_requirement.specifier)).version
                == scenario.environment.python
            ):
                requirements = requirements.copy()
                requirements.pop(index)

        pointers = [tee] * (len(requirements) - 1) + [last]
        for pointer, requirement in zip(pointers, sorted(requirements)):
            parsed_requirement = Requirement(requirement)

            # Display `requires-python`
            if parsed_requirement.name == "python":
                suffix = (
                    " (incompatible with environment)"
                    if not parsed_requirement.specifier.contains(
                        scenario.environment.python
                    )
                    else ""
                )
                yield prefix + pointer + "requires " + requirement + suffix
                continue

            yield prefix + pointer + "requires " + requirement

            if parsed_requirement.name in packages:
                extension = branch if pointer == tee else space
                yield from render_versions(
                    parsed_requirement.name,
                    prefix=prefix + extension,
                    for_requirement=parsed_requirement,
                )
            else:
                yield prefix + space + last + "unsatisfied: no versions for package"

    # Print the environment first
    pointer = tee
    buffer += pointer + "environment\n"
    prefix = branch
    buffer += prefix + last + f"python{scenario.environment.python}\n"

    # Print the root package first
    pointer = tee if scenario.packages else last
    buffer += pointer + "root\n"
    prefix = branch if pointer == tee else space

    # Then render versions for the root package
    for line in render_requirements(
        scenario.root.requires,
        prefix=prefix,
    ):
        buffer += line + "\n"

    # Then render all the other provided packages
    pointers = [tee] * (len(scenario.packages) - 1) + [last]
    for pointer, package in zip(pointers, sorted(scenario.packages)):
        # Print each package section
        buffer += pointer + package + "\n"

        prefix = branch if pointer == tee else space
        for line in render_versions(package, prefix=prefix):
            buffer += line + "\n"

    return buffer
