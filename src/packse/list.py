"""
List all scenarios.
"""
import json
import logging
from pathlib import Path
from typing import Literal, cast

from packse.error import FileNotFound, InvalidScenario
from packse.scenario import (
    Scenario,
    load_scenarios,
    scenario_prefix,
)

logger = logging.getLogger(__name__)


def list(
    targets: list[Path],
    no_versions: bool = False,
    skip_invalid: bool = False,
    no_sources: bool = False,
    format: Literal["json", "pretty"] = "pretty",
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

    # Then list each one
    result = {"scenarios": []}
    for source, scenarios in scenarios_by_path.items():
        prefix = "" if no_sources else " " * 4
        if not no_sources and format == "pretty":
            print(to_display_path(source))

        for scenario in scenarios:
            scenario = cast(Scenario, scenario)

            raw = scenario.dict()
            raw["source"] = str(source)
            raw["prefix"] = scenario_prefix(scenario)
            result["scenarios"].append(raw)

            if no_versions:
                name = scenario.name
            else:
                name = scenario_prefix(scenario)

            if format == "pretty":
                print(prefix + name)

    if format == "json":
        print(json.dumps(result, indent=2))


def to_display_path(path: Path | str, relative_to: Path | str | None = None) -> str:
    """
    Convert a path to a displayable path. The absolute path or relative path to the
    current (or given) directory will be returned, whichever is shorter.
    """
    path, relative_to = (
        Path(path).resolve(),
        Path(relative_to or ".").resolve(),
    )

    absolute_path = str(path)

    try:
        relative_path = str(path.relative_to(relative_to))
    except ValueError:
        # Not a child path, use the other one
        return absolute_path

    return relative_path if len(relative_path) < len(absolute_path) else absolute_path
