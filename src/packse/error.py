import textwrap
from pathlib import Path


class PackseError(Exception):
    """Base type for all Packse exceptions"""


class UserError(PackseError):
    """It's the user's fault :)"""


class DestinationAlreadyExists(UserError):
    def __init__(self, destination: Path) -> None:
        message = f"Destination directory '{destination}' already exists"
        super().__init__(message)


class InvalidScenario(UserError):
    def __init__(self, path: Path, reason: str) -> None:
        message = f"File at '{path}' is not a valid scenario: {reason}"
        super().__init__(message)


class ScenarioNotFound(UserError):
    def __init__(self, path: Path) -> None:
        message = f"Scenario '{path}' not found"
        super().__init__(message)


class BuildError(PackseError):
    def __init__(self, message, output) -> None:
        message = message + ":\n" + textwrap.indent(output, " " * 4)
        super().__init__(message)


class PublishError(PackseError):
    def __init__(self, message, output) -> None:
        message = message + ":\n" + textwrap.indent(output, " " * 4)
        super().__init__(message)


class PublishAlreadyExists(PackseError):
    def __init__(self, package: str) -> None:
        message = f"Publish for '{package}' already exists."
        super().__init__(message)


class InvalidPublishTarget(UserError):
    def __init__(self, path: Path, reason: str) -> None:
        message = f"Publish target at '{path}' is not a valid: {reason}"
        super().__init__(message)
