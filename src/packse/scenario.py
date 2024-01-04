import hashlib
import json
import os
from pathlib import Path

import msgspec

from packse.template import load_template_config

type PackageName = str
type PackageVersion = str
type VersionSpec = str


class PackageMetadata(msgspec.Struct):
    """
    Metadata for a single version of a package.
    """

    requires_python: str | None = ">=3.7"
    requires: list[VersionSpec] = []
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
        hasher.update(self.sdist.to_bytes())
        hasher.update(self.wheel.to_bytes())
        hasher.update(self.description.encode())
        return hasher.hexdigest()


class RootPackageMetadata(msgspec.Struct):
    requires_python: str | None = ">=3.7"
    requires: list[VersionSpec] = []

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update((self.requires_python or "").encode())
        for require in self.requires:
            hasher.update(require.encode())
        return hasher.hexdigest()


class EnvironmentMetadata(msgspec.Struct):
    python: str = "3.7"

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update(self.python.encode())
        return hasher.hexdigest()


class Package(msgspec.Struct):
    versions: dict[PackageVersion, PackageMetadata]

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        for name, version in self.versions.items():
            hasher.update(name.encode())
            hasher.update(version.hash().encode())
        return hasher.hexdigest()


class Expected(msgspec.Struct):
    """
    The expected outcome of a scenario.
    """

    satisfiable: bool
    """
    Are the packages in the scenario resolvable?
    """

    packages: dict[PackageName, PackageVersion] = {}
    """
    The expected versions to be installed for each package in the scenario.

    Only relevant if `satisfiable` is true.
    """

    explanation: str | None = None
    """
    An optional explanation for the expected result.
    """

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update(str(self.satisfiable).encode())
        if self.explanation:
            hasher.update(self.explanation.encode())
        for name, package in self.packages.items():
            hasher.update(name.encode())
            hasher.update(package.encode())
        return hasher.hexdigest()


class Scenario(msgspec.Struct):
    name: str
    """
    The name of the scenario.
    """

    packages: dict[PackageName, Package]
    """
    The packages available in the scenario.
    """

    root: RootPackageMetadata
    """
    The root package of the scenario.
    """

    expected: Expected
    """
    The expected result when resolving the scenario.
    """

    environment: EnvironmentMetadata = msgspec.field(
        default_factory=EnvironmentMetadata
    )
    """
    Metadata about the installation environment.
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
        hasher.update(self.root.hash().encode())
        hasher.update(self.environment.hash().encode())
        hasher.update(self.expected.hash().encode())
        for name, package in self.packages.items():
            hasher.update(name.encode())
            hasher.update(package.hash().encode())
        return hasher.hexdigest()

    def dict(self) -> dict:
        return json.loads(msgspec.json.encode(self))


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
    template_version = load_template_config(scenario.template).version
    hasher = hashlib.new("md5", usedforsecurity=False)
    hasher.update(template_version.to_bytes())
    hasher.update(scenario.hash().encode())
    hasher.update(os.environ.get("PACKSE_VERSION_SEED", "").encode())
    return hasher.hexdigest()[:8]


def scenario_prefix(scenario: Scenario) -> str:
    """
    Generate a prefix for a scenario.
    """
    version = scenario_version(scenario)
    return f"{scenario.name}-{version}"
