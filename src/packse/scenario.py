import hashlib
import json
import os
from pathlib import Path
from typing import Any, Self, Type

import msgspec
import packaging.requirements
import packaging.specifiers

from packse.template import load_template_config

type PackageName = str
type PackageVersion = (
    str  # TODO(zanieb): Consider replacing with `packaging.version.Version`
)


class Requirement(packaging.requirements.Requirement):
    """
    A wrapper for a standard Python requirement e.g. `foo>=1.0.0`
    """

    def __lt__(self, other: Any) -> True:
        """
        Sort by name for display purposes.
        """
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.name < other.name

    def with_unique_name(
        self,
        scenario: "Scenario",
        scenario_version: str,
        short_names: bool,
        no_hash: bool,
    ) -> type[Self]:
        """
        Return a copy of self with scenario metadata in the name
        """
        new = type(self)(str(self))
        new.name = self.name
        if not no_hash:
            new.name += "-" + scenario_version
        if not short_names:
            new.name = scenario.name + "-" + new.name
        return new


class PackageMetadata(msgspec.Struct, forbid_unknown_fields=True):
    """
    Metadata for a single version of a package.
    """

    requires_python: str | None = ">=3.8"
    requires: list[Requirement] = []
    extras: dict[str, list[Requirement]] = {}
    sdist: bool = True
    wheel: bool = True
    yanked: bool = False
    wheel_tags: list[str] = []
    description: str = ""

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update((self.requires_python or "").encode())
        for requirement in self.requires:
            hasher.update(str(requirement).encode())
        for extra_name, requirements in self.extras.items():
            hasher.update(extra_name.encode())
            for requirement in requirements:
                hasher.update(str(requirement).encode())
        hasher.update(self.sdist.to_bytes())
        hasher.update(self.wheel.to_bytes())
        if self.yanked:
            hasher.update(self.yanked.to_bytes())
        if self.wheel:
            for wheel_tag in self.wheel_tags:
                hasher.update(wheel_tag.encode())
        hasher.update(self.description.encode())
        return hasher.hexdigest()

    def dict(self) -> dict:
        enc = msgspec.json.Encoder(enc_hook=enc_hook)
        return json.loads(enc.encode(self))


class RootPackageMetadata(msgspec.Struct, forbid_unknown_fields=True):
    requires_python: str | None = ">=3.8"
    requires: list[Requirement] = []

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update((self.requires_python or "").encode())
        for requirement in self.requires:
            hasher.update(str(requirement).encode())
        return hasher.hexdigest()


class ResolverOptions(msgspec.Struct, forbid_unknown_fields=True):
    python: str | None = None
    """
    An optional Python version override.
    """

    prereleases: bool = False
    """
    If selection of prereleases should be enabled for all packages.
    """

    no_build: list[str] = []
    """
    Packages should be built from source distributions.

    Pre-built binaries are required for the given packages.
    """

    no_binary: list[str] = []
    """
    Pre-built binaries should not be allowed for the given packages.

    A source distribution is required to build the packages.
    """

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        if self.python is not None:
            hasher.update(self.python.encode())
        if self.prereleases is not None:
            hasher.update(self.prereleases.to_bytes())
        for no_binary in self.no_binary:
            hasher.update(no_binary.encode())
        for no_build in self.no_build:
            hasher.update(no_build.encode())

        return hasher.hexdigest()


class EnvironmentMetadata(msgspec.Struct, forbid_unknown_fields=True):
    python: str = "3.8"
    """
    The active Python version.
    """

    additional_python: list[str] = []
    """
    Additional Python versions available on the system.

    By default, only the active Python version is available.
    """

    def hash(self) -> str:
        """
        Return a hash of the contents
        """
        hasher = hashlib.new("md5", usedforsecurity=False)
        hasher.update(self.python.encode())
        for additional_python in self.additional_python:
            hasher.update(additional_python.encode())
        return hasher.hexdigest()


class Package(msgspec.Struct, forbid_unknown_fields=True):
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


class Expected(msgspec.Struct, forbid_unknown_fields=True):
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


class Scenario(msgspec.Struct, forbid_unknown_fields=True):
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

    resolver_options: ResolverOptions = msgspec.field(default_factory=ResolverOptions)
    """
    Additional options for the package resolver
    """

    template: str = "package"
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

        for name, package in self.packages.items():
            hasher.update(name.encode())
            hasher.update(package.hash().encode())

        # Note, the following are excluded because a re-publish is not needed on change
        # - resolver_options
        # - expected

        return hasher.hexdigest()

    def dict(self) -> dict:
        enc = msgspec.json.Encoder(enc_hook=enc_hook)
        return json.loads(enc.encode(self))


def load_scenario(target: Path) -> Scenario:
    """
    Loads a scenario
    """
    dec = msgspec.json.Decoder(Scenario, dec_hook=dec_hook)
    return dec.decode(target.read_text())


def load_many_scenarios(target: Path) -> list[Scenario]:
    """
    Loads a file with many scenarios
    """
    dec = msgspec.json.Decoder(list[Scenario], dec_hook=dec_hook)
    return dec.decode(target.read_text())


def load_scenarios(target: Path) -> list[Scenario]:
    # Guess if the file contains one or many scenario
    with target.open() as buffer:
        many = buffer.readline().lstrip().startswith("[")
    if many:
        return load_many_scenarios(target)
    else:
        return [load_scenario(target)]


def scenario_hash(scenario: Scenario) -> str:
    """
    Generate a unique version for a scenario based on its contents.
    """
    template_version = load_template_config(scenario.template).version
    hasher = hashlib.new("md5", usedforsecurity=False)
    hasher.update(template_version.to_bytes())
    hasher.update(scenario.hash().encode())
    hasher.update(os.environ.get("PACKSE_VERSION_SEED", "").encode())
    return hasher.hexdigest()[:8]


def dec_hook(type: Type, obj: Any) -> Any:
    """
    Custom decoding hook for `Requirement` types.
    """
    # `type` here is the value of the custom type annotation being decoded.
    if type is Requirement:
        # Convert `obj` (which should be a `str`) to a `Requirement`
        return Requirement(obj)
    else:
        raise NotImplementedError(f"Objects of type {type} are not supported")


def enc_hook(obj: Any) -> Any:
    """
    Custom encoding hook for `Requirement` types
    """
    if isinstance(obj, Requirement):
        # convert the requirement to a str
        return str(obj)
    else:
        raise NotImplementedError(f"Objects of type {type(obj)} are not supported")
