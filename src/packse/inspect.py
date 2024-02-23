"""
Get details for all scenarios.
"""
import json
import logging
from pathlib import Path
from typing import cast

from packse.error import FileNotFound, InvalidScenario
from packse.scenario import (
    Requirement,
    Scenario,
    load_scenarios,
    scenario_hash,
)
from packse.view import dependency_tree

logger = logging.getLogger(__name__)


def inspect(
    targets: list[Path],
    skip_invalid: bool = False,
    short_names: bool = False,
    no_hash: bool = False,
):
    scenarios_by_path: dict[Path, list[Scenario]] = {}

    # Validate and collect all targets first
    for target in sorted(targets):
        if not target.exists():
            raise FileNotFound(target)

        try:
            logger.debug("Loading %s", target)
            scenarios_by_path[target] = load_scenarios(target)
        except Exception as exc:
            if not skip_invalid:
                raise InvalidScenario(target, reason=str(exc)) from exc

    # Collect a JSON-compatible representation for each scenario
    result = {"scenarios": []}
    for source, scenarios in scenarios_by_path.items():
        for scenario in scenarios:
            scenario = cast(Scenario, scenario)

            raw = scenario.dict()
            raw["source"] = str(source)
            raw["version"] = scenario_hash(scenario)
            raw["tree"] = dependency_tree(scenario).splitlines()
            result["scenarios"].append(raw)

            # Convert dictionaries to lists for easier templating
            raw["packages"] = [
                {
                    "name": str(
                        Requirement(name).with_unique_name(
                            scenario,
                            raw["version"],
                            short_names,
                            no_hash=no_hash,
                        )
                    ),
                    "versions": [
                        {
                            **package_metadata.dict(),
                            "version": version,
                            "requires": [
                                str(
                                    requirement.with_unique_name(
                                        scenario,
                                        raw["version"],
                                        short_names,
                                        no_hash=no_hash,
                                    )
                                )
                                for requirement in package_metadata.requires
                            ],
                            "extras": [
                                {
                                    "name": extra,
                                    "requires": [
                                        str(
                                            requirement.with_unique_name(
                                                scenario,
                                                raw["version"],
                                                short_names,
                                                no_hash=no_hash,
                                            )
                                        )
                                        for requirement in extra_requires
                                    ],
                                }
                                for extra, extra_requires in package_metadata.extras.items()
                            ],
                        }
                        for version, package_metadata in package.versions.items()
                    ],
                }
                for name, package in scenario.packages.items()
            ]
            raw["expected"]["packages"] = [
                {
                    "name": str(
                        Requirement(name).with_unique_name(
                            scenario,
                            raw["version"],
                            short_names,
                            no_hash=no_hash,
                        )
                    ),
                    "version": version,
                }
                for name, version in scenario.expected.packages.items()
            ]
            raw["root"]["requires"] = [
                {
                    "requirement": str(requirement),
                    "name": requirement.name,
                    "module_name": requirement.name.replace("-", "_"),
                }
                for requirement in (
                    requirement.with_unique_name(
                        scenario,
                        raw["version"],
                        short_names,
                        no_hash=no_hash,
                    )
                    for requirement in scenario.root.requires
                )
            ]

            # Ensure a module name is available for testing import of packages
            for package in raw["expected"]["packages"]:
                package["module_name"] = package["name"].replace("-", "_")

            raw["module_name"] = raw["name"].replace("-", "_")

    print(json.dumps(result, indent=2))
