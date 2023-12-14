"""
View package tree for the given scenarios.
"""
import logging
from pathlib import Path

from packaging.requirements import Requirement

from packse.error import InvalidScenario, ScenarioNotFound
from packse.scenario import Scenario, load_scenarios, scenario_prefix

logger = logging.getLogger(__name__)


def view(targets: list[Path]):
    scenarios = []

    # Validate and collect all targets first
    for target in targets:
        if not target.exists():
            raise ScenarioNotFound(target)

        try:
            logger.debug("Loading %s", target)
            scenarios.extend(load_scenarios(target))
        except Exception as exc:
            raise InvalidScenario(target, reason=str(exc)) from exc

    # Then view each one
    for scenario in scenarios:
        logger.debug("Viewing %s", scenario.name)
        view_scenario(scenario)


def view_scenario(scenario: Scenario):
    prefix = scenario_prefix(scenario)

    print(prefix)
    print(dependency_tree(scenario))


def dependency_tree(scenario: Scenario):
    """
    Generate a dependency tree for a scenario
    """

    space = "    "
    branch = "│   "
    tee = "├── "
    last = "└── "
    buffer = ""

    def render_package_versions(
        package: str,
        prefix: str = "",
        for_requirement: Requirement | None = None,
    ):
        versions = scenario.packages[package].versions

        pointers = [tee] * (len(versions) - 1) + [last]
        satisfied = False
        for pointer, version in zip(pointers, versions):
            if for_requirement and not for_requirement.specifier.contains(version):
                continue

            satisfied = True
            message = "satisfied by " if for_requirement else ""
            yield prefix + pointer + message + f"{package}-{version}"

            extension = branch if pointer == tee else space
            yield from render_requirements_for(
                package, version, prefix=prefix + extension
            )

        if for_requirement and not satisfied:
            yield prefix + last + "unsatisfied"

    def render_requirements_for(package: str, version: str, prefix: str = ""):
        requirements = list(scenario.packages[package].versions[version].requires)

        pointers = [tee] * (len(requirements) - 1) + [last]
        for pointer, requirement in zip(pointers, sorted(requirements)):
            yield prefix + pointer + "requires " + requirement

            parsed_requirement = Requirement(requirement)
            if parsed_requirement.name in scenario.packages:
                extension = branch if pointer == tee else space
                yield from render_package_versions(
                    parsed_requirement.name,
                    prefix=prefix + extension,
                    for_requirement=parsed_requirement,
                )
            else:
                yield prefix + space + last + "unsatisfied"

    for line in render_package_versions(scenario.root):
        buffer += line + "\n"

    for package in sorted(scenario.packages):
        if package == scenario.root:
            continue
        for line in render_package_versions(package):
            buffer += line + "\n"

    return buffer
