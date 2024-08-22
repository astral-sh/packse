"""
Utilities for testing
"""

import base64
import hashlib
import os
import re
import signal
import subprocess
import sys
from contextlib import contextmanager
from itertools import islice
from pathlib import Path

import pytest

from packse import __development_base_path__

MAX_FILE_LENGTH = 500
"""Maximum number of characters to store per file in filesystem snapshots. If exceeded, a hash of the contents will be used instead."""


def snapshot_command(
    command: list[str],
    working_directory: Path | None = None,
    snapshot_filesystem: bool = False,
    snapshot_stderr: bool = True,
    snapshot_stdout: bool = True,
    extra_filters: list[tuple[str, str]] | None = None,
    interrupt_after: float = None,
    env: dict[str, str] = None,
) -> dict:
    env = env or {}
    # By default, filter out absolute references to the working directory
    filters = [
        (re.escape(str(Path(sys.executable).parent)), "[PYTHON_BINDIR]"),
        (re.escape(str((working_directory or Path.cwd()).absolute())), "[PWD]"),
        (
            r"in (\d+\.)?\d+(ms|s)",
            "in [TIME]",
        ),
        (re.escape(str(__development_base_path__.absolute())), "[PROJECT_ROOT]"),
    ]
    if extra_filters:
        filters += extra_filters

    killed = False
    env = {**os.environ, **env}
    process = subprocess.Popen(
        ["packse"] + command,
        cwd=working_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        stdout, stderr = process.communicate(timeout=interrupt_after)
    except subprocess.TimeoutExpired:
        process.send_signal(signal.SIGINT)
        stdout, stderr = process.communicate(timeout=2)
        killed = True

    result = {
        "exit_code": process.returncode if not killed else "<stopped>",
        "stdout": (
            apply_filters(stdout.decode(), filters)
            if snapshot_stdout
            else "<not included>"
        ),
        "stderr": (
            apply_filters(stderr.decode(), filters)
            if snapshot_stderr
            else "<not included>"
        ),
    }

    if snapshot_filesystem:
        result["filesystem"] = snapshot_filesystem_tree(working_directory)

    return result


@contextmanager
def tmpchdir(path: str):
    """
    Change current-working directories for the duration of the context
    """
    path = os.path.abspath(path)
    if os.path.isfile(path) or (not os.path.exists(path) and not path.endswith("/")):
        path = os.path.dirname(path)

    owd = os.getcwd()

    try:
        os.chdir(path)
        yield path
    finally:
        os.chdir(owd)


@pytest.fixture
def tmpcwd(tmp_path):
    with tmpchdir(tmp_path):
        yield tmp_path


@pytest.fixture
def tmpenviron():
    old_environ = dict(os.environ)

    yield os.environ

    os.environ.clear()
    os.environ.update(old_environ)


def snapshot_filesystem_tree(working_directory: Path | None = None) -> dict:
    working_directory = working_directory or Path.cwd()
    snapshot = {}
    snapshot["tree"] = tree(working_directory)

    for root, _, files in working_directory.walk():
        for file in files:
            file_path = root / file
            try:
                contents = file_path.read_text()
            except UnicodeDecodeError:
                contents = base64.b64encode(file_path.read_bytes())

            snapshot[str(file_path.relative_to(working_directory))] = (
                f"md5:{hash_contents(contents)}"
                if len(contents) > MAX_FILE_LENGTH
                else contents
            )

    return snapshot


def hash_contents(contents: bytes | str) -> str:
    if isinstance(contents, str):
        contents = contents.encode()
    return hashlib.md5(contents, usedforsecurity=False).hexdigest()


def apply_filters(content: str, filters: list[tuple[str, str]]) -> str:
    for pattern, replacement in filters:
        content = re.sub(pattern, replacement, content)
    return content


# Derived from https://stackoverflow.com/questions/9727673/list-directory-tree-structure-in-python
def tree(
    dir_path: Path,
    level: int = -1,
    limit_to_directories: bool = False,
    length_limit: int = 1000,
):
    """Given a directory Path object print a visual tree structure"""

    space = "    "
    branch = "│   "
    tee = "├── "
    last = "└── "
    buffer = ""

    dir_path = Path(dir_path)  # accept string coerceable to Path
    files = 0
    directories = 0

    def inner(dir_path: Path, prefix: str = "", level=-1):
        nonlocal files, directories
        if not level:
            return  # 0, stop iterating
        if limit_to_directories:
            contents = [d for d in dir_path.iterdir() if d.is_dir()]
        else:
            contents = list(dir_path.iterdir())
        pointers = [tee] * (len(contents) - 1) + [last]
        for pointer, path in zip(pointers, sorted(contents)):
            if path.is_dir():
                yield prefix + pointer + path.name
                directories += 1
                extension = branch if pointer == tee else space
                yield from inner(path, prefix=prefix + extension, level=level - 1)
            elif not limit_to_directories:
                yield prefix + pointer + path.name
                files += 1

    buffer += dir_path.name + "\n"
    iterator = inner(dir_path, level=level)
    for line in islice(iterator, length_limit):
        buffer += line + "\n"
    if next(iterator, None):
        buffer += f"... length_limit, {length_limit}, reached, counted:\n"
    buffer += (
        f"\n{directories} directories" + (f", {files} files" if files else "") + "\n"
    )
    return buffer
