import pytest

from packse import __development_base_path__
from packse.scenario import (
    Expected,
    Package,
    PackageMetadata,
    Requirement,
    RootPackageMetadata,
    Scenario,
)
from packse.view import dependency_tree

from .common import snapshot_command


def test_view_no_target(snapshot):
    assert (
        snapshot_command(["view"], snapshot_stderr=False, snapshot_stdout=False)
        == snapshot
    )


def test_view_target_does_not_exist(snapshot):
    assert snapshot_command(["view", "foo"]) == snapshot


@pytest.mark.usefixtures("tmpcwd")
def test_view_one_target_does_not_exist(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target), "foo"]) == snapshot


def test_view_invalid_target(snapshot, tmpcwd):
    target = tmpcwd / "test.json"
    target.touch()
    assert snapshot_command(["view", str(target)]) == snapshot


def test_view_example(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target)]) == snapshot


def test_view_example_short_names(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target), "--short-names"]) == snapshot


def test_view_example_name(snapshot):
    target = __development_base_path__ / "scenarios" / "examples" / "example.json"
    assert snapshot_command(["view", str(target), "--name", "example"]) == snapshot


@pytest.mark.parametrize(
    "requirements",
    [
        [
            "python>=3.12",
            "python==3.12",
            "alpha",
            "python>=3.12,<3.14",
            "python>=3.11",
            "python>=3.13",
        ],
        [
            "alpha",
            "python>=3.12,<3.14",
            "python>=3.11",
            "python>=3.13",
            "python>=3.12",
            "python==3.12",
        ],
    ],
)
def test_dependency_tree_filters_matching_python_requirements(requirements):
    scenario = Scenario(
        name="example",
        packages={},
        root=RootPackageMetadata(requires=[Requirement(req) for req in requirements]),
        expected=Expected(satisfiable=False),
    )

    assert dependency_tree(scenario) == (
        "├── environment\n"
        "│   └── python3.12\n"
        "└── root\n"
        "    ├── requires alpha\n"
        "        └── unsatisfied: no versions for package\n"
        "    ├── requires python<3.14,>=3.12\n"
        "    ├── requires python>=3.11\n"
        "    └── requires python>=3.13 (incompatible with environment)\n"
    )
    assert [str(req) for req in scenario.root.requires] == [
        str(Requirement(req)) for req in requirements
    ]


def test_dependency_tree_filters_package_python_requirements():
    scenario = Scenario(
        name="example",
        packages={
            "foo": Package(
                versions={
                    "1.0.0": PackageMetadata(
                        requires_python=">=3.12",
                        requires=[Requirement("python==3.12"), Requirement("alpha")],
                    )
                }
            )
        },
        root=RootPackageMetadata(),
        expected=Expected(satisfiable=False),
    )

    assert dependency_tree(scenario) == (
        "├── environment\n"
        "│   └── python3.12\n"
        "├── root\n"
        "└── foo\n"
        "    └── foo-1.0.0\n"
        "        └── requires alpha\n"
        "            └── unsatisfied: no versions for package\n"
    )
