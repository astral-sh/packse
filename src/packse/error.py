import textwrap
from pathlib import Path


class PackseError(Exception):
    """Base type for all Packse exceptions"""


class UserError(PackseError):
    """It's the user's fault :)"""


class RequiresExtra(UserError):
    def __init__(self, feature: str, extra: str) -> None:
        message = f"Using {feature} requires installation with extra {extra!r}"
        super().__init__(message)


class DestinationAlreadyExists(UserError):
    def __init__(self, destination: Path) -> None:
        message = f"Destination directory '{destination}' already exists"
        super().__init__(message)


class InvalidScenario(UserError):
    def __init__(self, path: Path, reason: str) -> None:
        message = f"File at '{path}' is not a valid scenario: {reason}"
        super().__init__(message)


class InvalidPackageVersion(UserError):
    """Version is not PEP compliant"""

    def __init__(self, version: str) -> None:
        message = f"Version {version!r} is not valid."
        super().__init__(message)


class FileNotFound(UserError):
    def __init__(self, path: Path) -> None:
        message = f"File '{path}' not found"
        super().__init__(message)


class BuildError(PackseError):
    def __init__(self, message, output) -> None:
        message = message + ":\n" + textwrap.indent(output, " " * 4)
        super().__init__(message)


class PublishError(PackseError):
    pass


class PublishToolError(PublishError):
    def __init__(self, message, output) -> None:
        message = message + ":\n" + textwrap.indent(output, " " * 4)
        super().__init__(message)


class PublishNoCredentials(PublishError):
    def __init__(self) -> None:
        message = (
            "No credentials found for publish!\n"
            "Provide an API token via `PACKSE_PUBLISH_PASSWORD` or disable authentication with `--anonymous`"
        )
        super().__init__(message)


class PublishAlreadyExists(PublishError):
    def __init__(self, package: str) -> None:
        message = f"Publish for '{package}' already exists"
        super().__init__(message)


class PublishRateLimit(PublishError):
    def __init__(self, package: str) -> None:
        message = f"Publish of '{package}' failed due to rate limits"
        super().__init__(message)


class PublishConnectionError(PublishError):
    def __init__(self, package: str) -> None:
        message = f"Publish of '{package}' failed due to a connection error"
        super().__init__(message)


class InvalidPublishTarget(UserError):
    def __init__(self, path: Path, reason: str) -> None:
        message = f"Publish target at '{path}' is not a valid: {reason}"
        super().__init__(message)


class ServeError(PackseError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ServeThreadError(ServeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ServeCommandError(ServeError):
    def __init__(self, message: str, stderr: str) -> None:
        if stderr.strip():
            message += f":\n\n{stderr}"
        super().__init__(message)


class ServeAddressInUse(ServeError):
    def __init__(self, url: str) -> None:
        message = f"Address '{url}' already in use"
        super().__init__(message)


class ServeAlreadyRunning(ServeError):
    def __init__(self) -> None:
        message = "Server is already running"
        super().__init__(message)
