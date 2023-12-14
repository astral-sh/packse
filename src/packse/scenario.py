import hashlib
import os
from pathlib import Path

import msgspec

from packse.template import get_template_version


class PackageVersion(msgspec.Struct):
    requires_python: str | None = ">=3.7"
    requires: list[str] = []
    sdist: bool = True
    wheel: bool = True
    description: str = ""

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update((self.requires_python or "").encode())
        for require in self.requires:
            hasher.update(require.encode())
        return hasher.hexdigest()


class Package(msgspec.Struct):
    versions: dict[str, PackageVersion]

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        for name, version in self.versions.items():
            hasher.update(name.encode())
            hasher.update(version.hash().encode())
        return hasher.hexdigest()


class Scenario(msgspec.Struct):
    name: str
    """
    The name of the scenario.
    """

    packages: dict[str, Package]
    """
    The packages available in the scenario.
    """

    root: str
    """
    The root package of the scenario.

    The scenario entrypoint package will require this package.
    """

    template: str = "simple"
    """
    The template to use for scenario packages.
    """

    description: str | None = None
    """
    The description of the scenario.
    """

    def hash(self) -> str:
        """
        Return a hash of the scenario contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update(self.name.encode())
        hasher.update(self.template.encode())
        for name, package in self.packages.items():
            hasher.update(name.encode())
            hasher.update(package.hash().encode())
        return hasher.hexdigest()


def load_scenario(target: Path) -> Scenario:
    """
    Loads a scenario
    """
    return msgspec.json.decode(target.read_text(), type=Scenario)


def load_many_scenarios(target: Path) -> list[Scenario]:
    """
    Loads a file with many scenarios
    """
    return msgspec.json.decode(target.read_text(), type=list[Scenario])


def load_scenarios(target: Path) -> list[Scenario]:
    # Guess if the file contains one or many scenario
    with target.open() as buffer:
        many = buffer.readline().lstrip().startswith("[")
    if many:
        return load_many_scenarios(target)
    else:
        return [load_scenario(target)]


def scenario_version(scenario: Scenario) -> str:
    """
    Generate a unique version for a scenario based on its contents.
    """
    template_version = get_template_version(scenario.template)
    hasher = hashlib.new("md5", usedforsecurity=False)
    hasher.update(template_version.encode())
    hasher.update(scenario.hash().encode())
    hasher.update(os.environ.get("PACKSE_VERSION_SEED", "").encode())
    return hasher.hexdigest()[:8]


def scenario_prefix(scenario: Scenario) -> str:
    """
    Generate a prefix for a scenario.
    """
    version = scenario_version(scenario)
    return f"{scenario.name}-{version}"
