import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from subprocess import CalledProcessError

from packse.build import build, build_package
from packse.error import (
    BuildError,
    DestinationAlreadyExists,
    PublishError,
    ServeCommandError,
    ServeError,
    UserError,
)
from packse.fetch import fetch
from packse.index import build_index
from packse.inspect import variables_for_templates
from packse.list import list
from packse.publish import publish
from packse.scenario import find_scenario_files
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
        print(f"{exc}. Pass `--force` to allow removal.", file=sys.stderr)
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
    except ServeCommandError as exc:
        print(f"{exc}", file=sys.stderr)
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
    build(
        args.targets,
        rm_destination=args.force,
        short_names=args.short_names,
        no_hash=args.no_hash,
        skip_root=args.skip_root,
    )


def _call_build_package(args):
    build_package(
        args.name,
        args.version,
        args.no_wheel,
        args.no_sdist,
        args.requires_python,
        args.wheel_tag,
        args.force,
    )


def _call_view(args):
    view(args.targets, args.name, short_names=args.short_names)


def _call_serve(args):
    asyncio.run(
        serve(
            args.targets,
            host=args.host,
            port=args.port,
            dist_dir=args.dist_dir,
            build_dir=args.build_dir,
            index_dir=args.index_dir,
            short_names=args.short_names,
            no_hash=args.no_hash,
        )
    )


def _call_index_build(args):
    build_index(
        args.targets,
        short_names=args.short_names,
        no_hash=args.no_hash,
        dist_dir=args.dist_dir,
        index_dir=args.index_dir,
    )


def _call_publish(args):
    publish(
        args.targets,
        index_url=args.index_url,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        anonymous=args.anonymous,
        workers=args.workers,
    )


def _call_fetch(args):
    fetch(
        args.dest,
        ref=args.ref,
        force=args.force,
    )


def _call_list(args):
    skip_invalid = args.skip_invalid
    if not args.targets:
        skip_invalid = True
        targets = find_scenario_files(Path.cwd())
    else:
        targets = []
        for target in args.targets:
            # Expand any directories to json files within
            if target.is_dir():
                targets.extend(find_scenario_files(target))
            else:
                targets.append(target)

    list(
        targets,
        args.no_hash,
        skip_invalid,
        args.no_sources,
        short_names=args.short_names,
    )


def _call_inspect(args):
    skip_invalid = args.skip_invalid
    if not args.targets:
        skip_invalid = True
        targets = find_scenario_files(Path.cwd())
    else:
        targets = []
        for target in args.targets:
            # Expand any directories to scenario files within
            if target.is_dir():
                targets.extend(find_scenario_files(target))
            else:
                targets.append(target)

    print(
        json.dumps(
            variables_for_templates(
                targets,
                skip_invalid,
                short_names=args.short_names,
                no_hash=args.no_hash,
            ),
            indent=2,
        )
    )


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
        default=[Path("./scenarios")],
        help="The scenario to build",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing builds",
    )
    parser.add_argument(
        "--short-names",
        action="store_true",
        help="Exclude scenario names from generated packages.",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Exclude scenario version hashes from generated packages.",
    )
    parser.add_argument(
        "--skip-root",
        action="store_true",
        help='Do not build a "root" package for the scenario.',
    )
    _add_shared_arguments(parser)


def _add_build_package_parser(subparsers):
    parser = subparsers.add_parser("build-pkg", help="Build a single package")
    parser.set_defaults(call=_call_build_package)
    parser.add_argument(
        "name",
        type=str,
        help="The package name",
    )
    parser.add_argument(
        "version",
        type=str,
        help="The package version",
    )
    parser.add_argument(
        "-t",
        "--wheel-tag",
        type=str,
        help="The tags for wheels",
        action="append",
    )
    parser.add_argument(
        "--no-wheel",
        action="store_true",
        help="Disable building wheels",
    )
    parser.add_argument(
        "--requires-python",
        type=str,
        default=None,
        help="The package Python requirement",
    )
    parser.add_argument(
        "--no-sdist",
        action="store_true",
        help="Disable building source distributions",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing builds",
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
        default=[Path("./scenarios")],
        help="The scenario distribution directory to publish",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not actually publish, just show uv commands that would be used.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip existing distributions instead of failing.",
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
    parser.add_argument(
        "--short-names",
        action="store_true",
        help="Exclude scenario names from generated packages.",
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
        default=[Path("./scenarios")],
        help="The scenarios to serve",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="The host to bind the package index to.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3141,
        help="The port to bind the package index to.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default="./dist",
        help="The directory to store builds in.",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default="./build",
        help="The directory to store intermediate build artifacts in.",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default="./index",
        help="The directory to store the distributions and the rendered HTML in.",
    )
    parser.add_argument(
        "--short-names",
        action="store_true",
        help="Exclude scenario names from generated packages.",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Exclude scenario version hashes from generated packages.",
    )
    _add_shared_arguments(parser)


def _add_index_parser(subparsers):
    parser = subparsers.add_parser("index", help="Run a local package index")

    subparsers = parser.add_subparsers(title="commands")
    build = subparsers.add_parser("build", help="Build a static package index server.")
    build.add_argument(
        "targets",
        type=Path,
        nargs="*",
        default=[Path("./scenarios")],
        help="The scenario files to load",
    )
    build.add_argument(
        "--short-names",
        action="store_true",
        help="Exclude scenario names from generated packages.",
    )
    build.add_argument(
        "--no-hash",
        action="store_true",
        help="Exclude scenario version hashes from generated packages.",
    )
    build.add_argument(
        "--dist-dir",
        type=Path,
        default=None,
        help="An existing distribution directory to use. If provided, the scenarios will not be rebuilt.",
    )
    build.add_argument(
        "--index-dir",
        type=Path,
        default="./index",
        help="An existing distribution directory to use. If provided, the scenarios will not be rebuilt.",
    )
    build.set_defaults(call=_call_index_build)

    _add_shared_arguments(parser)
    _add_shared_arguments(build)


def _add_list_parser(subparsers):
    parser = subparsers.add_parser("list", help="List scenarios at the given paths")
    parser.set_defaults(call=_call_list)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="*",
        default=[Path("./scenarios")],
        help="The scenario files to load",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Do not include in the scenario version hashes in the displayed names.",
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
    parser.add_argument(
        "--short-names",
        action="store_true",
        help="Exclude scenario names from generated packages.",
    )
    _add_shared_arguments(parser)


def _add_inspect_parser(subparsers):
    parser = subparsers.add_parser(
        "inspect", help="Inspect scenarios at the given paths"
    )
    parser.set_defaults(call=_call_inspect)
    parser.add_argument(
        "targets",
        type=Path,
        nargs="*",
        default=[Path("./scenarios")],
        help="The scenario files to load",
    )
    parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Skip invalid scenario files instead of failing.",
    )
    parser.add_argument(
        "--short-names",
        action="store_true",
        help="Exclude scenario names from generated packages.",
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Do not include in the scenario version hashes in the displayed names.",
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


def _add_fetch_parser(subparsers):
    parser = subparsers.add_parser(
        "fetch", help="Fetch built-in scenarios from the packse repository"
    )
    parser.set_defaults(call=_call_fetch)
    parser.add_argument(
        "--dest",
        type=Path,
        help="Where to place the fetched scenarios",
    )
    parser.add_argument(
        "--ref",
        type=str,
        default=None,
        help="The reference to fetch",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Allow replacement of existing destination directory",
    )
    _add_shared_arguments(parser)


def get_parser() -> argparse.ArgumentParser:
    parser = _root_parser()
    subparsers = parser.add_subparsers(title="commands")
    _add_build_parser(subparsers)
    _add_build_package_parser(subparsers)
    _add_view_parser(subparsers)
    _add_publish_parser(subparsers)
    _add_list_parser(subparsers)
    _add_inspect_parser(subparsers)
    _add_serve_parser(subparsers)
    _add_fetch_parser(subparsers)
    _add_index_parser(subparsers)

    return parser
