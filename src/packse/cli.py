import argparse
import logging
import sys
from pathlib import Path
from subprocess import CalledProcessError

from packse.build import build
from packse.error import (
    BuildError,
    DestinationAlreadyExists,
    PublishError,
    ServeError,
    UserError,
)
from packse.index import index_down, index_up
from packse.list import list
from packse.publish import publish
from packse.serve import serve
from packse.view import view


def entrypoint():
    parser = get_parser()
    args = parser.parse_args()
    if not hasattr(args, "call"):
        parser.print_help()
        return None

    if args.quiet:
        log_level = logging.CRITICAL
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(level=log_level, format="%(message)s")

    # Call the implementation wrapper e.g. `_call_build`
    try:
        args.call(args)
    except DestinationAlreadyExists as exc:
        print(f"{exc}. Pass `--rm` to allow removal.", file=sys.stderr)
        exit(1)
    except UserError as exc:
        print(f"{exc}.", file=sys.stderr)
        exit(1)
    except BuildError as exc:
        print(f"{exc}.", file=sys.stderr)
        exit(1)
    except PublishError as exc:
        print(f"{exc}.", file=sys.stderr)
        exit(1)
    except ServeError as exc:
        print(f"{exc}.", file=sys.stderr)
        exit(1)
    except CalledProcessError as exc:
        print(
            f"Error running command: {', '.join(exc.cmd)!r} (exit code {exc.returncode})",
            file=sys.stderr,
        )
        print(exc.output.decode(), file=sys.stderr)
        exit(2)
    except KeyboardInterrupt:
        print("Interrupted!", file=sys.stderr)
        exit(1)


def _call_build(args):
    build(args.targets, rm_destination=args.rm)


def _call_view(args):
    view(args.targets, args.name)


def _call_serve(args):
    serve(args.targets)


def _call_index_up(args):
    index_up(
        host=args.host,
        port=args.port,
        reset=args.reset,
        storage_path=args.storage_path,
        background=args.bg,
        offline=args.offline,
        all=args.all,
    )


def _call_index_down(args):
    success = index_down(storage_path=args.storage_path)
    if not success:
        exit(1)


def _call_publish(args):
    publish(
        args.targets,
        index_url=args.index_url,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        retry_on_rate_limit=args.retry,
        anonymous=args.anonymous,
        workers=args.workers,
    )


def _call_list(args):
    skip_invalid = args.skip_invalid
    if not args.targets:
        skip_invalid = True
        args.targets = Path.cwd().glob("**/*.json")

    list(args.targets, args.no_versions, skip_invalid, args.no_sources)


def _root_parser():
    parser = argparse.ArgumentParser(
        description="Utilities for working example packaging scenarios",
    )
    _add_shared_arguments(parser)
    return parser


def _add_build_parser(subparsers):
    parser = subparsers.add_parser("build", help="Build packages for a scenario")
    parser.set_defaults(call=_call_build)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="+",
        help="The scenario to build",
    )
    parser.add_argument(
        "--rm",
        action="store_true",
        help="Allow removal of existing build directory",
    )
    _add_shared_arguments(parser)


def _add_publish_parser(subparsers):
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "publish", help="Publish packages for a scenario"
    )
    parser.set_defaults(call=_call_publish)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="+",
        help="The scenario distribution directory to publish",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not actually publish, just show twine commands that would be used.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip existing distributions instead of failing.",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="Retry when rate limits are encountered instead of failing. Note retries must be very long to succeed.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of threads to use when publishing.",
    )
    parser.add_argument(
        "--index-url",
        type=str,
        default="https://test.pypi.org/legacy/",
        help="The URL of the package index to publish the packages to.",
    )
    parser.add_argument(
        "--anonymous", action="store_true", help="Upload without credentials."
    )
    _add_shared_arguments(parser)


def _add_view_parser(subparsers):
    parser = subparsers.add_parser("view", help="View a scenario")
    parser.set_defaults(call=_call_view)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="+",
        help="The scenario file to view",
    )
    parser.add_argument(
        "--name",
        type=str,
        default=None,
        help="The scenario name to view",
    )

    _add_shared_arguments(parser)


def _add_serve_parser(subparsers):
    parser = subparsers.add_parser(
        "serve", help="Serve scenarios on a temporary local package index"
    )
    parser.set_defaults(call=_call_serve)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="*",
        help="The scenarios to serve",
    )

    _add_shared_arguments(parser)


def _add_index_parser(subparsers):
    parser = subparsers.add_parser("index", help="Run a local package index")

    subparsers = parser.add_subparsers(title="commands")
    up = subparsers.add_parser(
        "up", help="Start a package index server in the background."
    )
    up.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="The host to bind the package index to.",
    )
    up.add_argument(
        "--port",
        type=int,
        default=3141,
        help="The port to bind the package index to.",
    )
    up.add_argument(
        "--reset",
        action="store_true",
        help="Reset the server's state on start.",
    )
    up.add_argument(
        "--storage-path",
        type=Path,
        default=None,
        help="The path to store server data at. Defaults to '~/.packse' if in the background, otherwise a temporary directory is used.",
    )
    up.add_argument(
        "--bg",
        action="store_true",
        help="Run the index server in the background, exiting after it is ready.",
    )
    up.add_argument(
        "--offline",
        action="store_true",
        help="Run the all index servers without acccess to the real PyPI.",
    )
    up.add_argument(
        "--all",
        action="store_true",
        help="Output the index server URL that allows fallback to the real PyPI.",
    )
    up.set_defaults(call=_call_index_up)

    down = subparsers.add_parser("down", help="Stop a running package index server.")
    down.add_argument(
        "--storage-path",
        type=Path,
        default=None,
        help="The path used to store server data.",
    )
    down.set_defaults(call=_call_index_down)

    _add_shared_arguments(parser)
    _add_shared_arguments(up)
    _add_shared_arguments(down)


def _add_list_parser(subparsers):
    parser = subparsers.add_parser("list", help="List scenarios")
    parser.set_defaults(call=_call_list)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="*",
        help="The scenario files to load",
    )
    parser.add_argument(
        "--no-versions",
        action="store_true",
        help="Do not include in the scenario versions in the displayed names.",
    )
    parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Skip invalid scenario files instead of failing.",
    )
    parser.add_argument(
        "--no-sources",
        action="store_true",
        help="Do not show the source file for each scenario.",
    )
    _add_shared_arguments(parser)


def _add_shared_arguments(parser):
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Disable logging",
    )


def get_parser() -> argparse.ArgumentParser:
    parser = _root_parser()
    subparsers = parser.add_subparsers(title="commands")
    _add_build_parser(subparsers)
    _add_view_parser(subparsers)
    _add_publish_parser(subparsers)
    _add_list_parser(subparsers)
    _add_serve_parser(subparsers)
    _add_index_parser(subparsers)

    return parser
