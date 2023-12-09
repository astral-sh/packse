import textwrap
from pathlib import Path


class PackseError(Exception):
    pass


class UserError(PackseError):
    pass


class DestinationAlreadyExists(UserError):
    def __init__(self, destination: Path) -> None:
        message = f"Destination directory '{destination}' already exists"
        super().__init__(message)


class InvalidScenario(UserError):
    def __init__(self, path: Path) -> None:
        message = f"File at '{path}' is not a valid scenario"
        super().__init__(message)


class ScenarioNotFound(UserError):
    def __init__(self, path: Path) -> None:
        message = f"Scenario '{path}' not found"
        super().__init__(message)


class BuildError(PackseError):
    def __init__(self, message, output) -> None:
        message = message + ":\n" + textwrap.indent(output, " " * 4)
        super().__init__(message)
