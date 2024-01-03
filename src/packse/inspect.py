"""
Get details for all scenarios.
"""
import json
import logging
from pathlib import Path
from typing import cast

from packse.error import FileNotFound, InvalidScenario
from packse.scenario import (
    Scenario,
    load_scenarios,
    scenario_prefix,
)
from packse.view import dependency_tree

logger = logging.getLogger(__name__)


def inspect(targets: list[Path], skip_invalid: bool = False):
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
            raw["prefix"] = scenario_prefix(scenario)
            raw["tree"] = dependency_tree(scenario).splitlines()
            result["scenarios"].append(raw)

    print(json.dumps(result, indent=2))
