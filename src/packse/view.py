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
    scenario_prefix,
)

logger = logging.getLogger(__name__)


def view(targets: list[Path], name: str | None = None):
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
            # Allow user to provide the name with or without the prefix
            and scenario.name != name
            and scenario_prefix(scenario) != name
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

        view_scenario(scenario)


def view_scenario(scenario: Scenario):
    prefix = scenario_prefix(scenario)

    print(prefix)
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
            versions = [
                version
                for version in versions
                if for_requirement.specifier.contains(version)
            ]

            if not versions:
                yield prefix + last + "unsatisfied: no matching version"
                return

        pointers = [tee] * (len(versions) - 1) + [last]
        for pointer, version in zip(pointers, versions):
            message = "satisfied by " if for_requirement and package else ""
            yield prefix + pointer + message + f"{package}-{version}"

            if not for_requirement:
                extension = branch if pointer == tee else space
                yield from render_requirements(
                    versions[version].requires
                    + [f"python{versions[version].requires_python}"],
                    prefix=prefix + extension,
                )

    def render_requirements(requirements: list[str], prefix: str = ""):
        pointers = [tee] * (len(requirements) - 1) + [last]
        for pointer, requirement in zip(pointers, sorted(requirements)):
            parsed_requirement = Requirement(requirement)
            suffix = ""

            if parsed_requirement.name == "python":
                # Display `requires python` incompatibilities
                if not parsed_requirement.specifier.contains(
                    scenario.environment.python
                ):
                    suffix = " (incompatible with environment)"

            yield prefix + pointer + "requires " + requirement + suffix

            if parsed_requirement.name == "python":
                # Do not display more information about Python requirements
                continue

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
