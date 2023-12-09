import argparse
import logging
import sys
from pathlib import Path

from packse.build import build
from packse.error import BuildError, DestinationAlreadyExists, UserError
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

    logging.basicConfig(level=log_level)

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
        print(f"{exc}", file=sys.stderr)
        exit(1)


def _call_build(args):
    build(args.targets, rm_destination=args.rm)


def _call_view(args):
    view(args.targets)


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


def _add_view_parser(subparsers):
    parser = subparsers.add_parser("view", help="View a scenario")
    parser.set_defaults(call=_call_view)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="+",
        help="The scenario to view",
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

    return parser
