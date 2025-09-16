import hashlib
import logging
import shutil
import tempfile
import time
from pathlib import Path

from packse import __development_base_path__
from packse.build import build
from packse.error import (
    RequiresExtra,
)
from packse.inspect import variables_for_templates
from packse.template import create_from_template
from packse.templates import __templates_path__

logger = logging.getLogger(__name__)


async def index_server(index_dir: Path, host: str, port: int):
    try:
        import uvicorn
        from fastapi import FastAPI
        from starlette.staticfiles import StaticFiles
    except ImportError:
        raise RequiresExtra("index commands", "index")

    index_url = f"http://{host}:{port}"
    logger.info("Starting index at %s", index_url)

    app = FastAPI()
    app.mount("/", StaticFiles(directory=index_dir, html=True))

    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


def sha256_file(path: Path):
    with open(path, "rb", buffering=0) as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def build_index(
    targets: list[Path],
    no_hash: bool,
    short_names: bool,
    dist_dir: Path | None,
    index_dir: Path | None,
    exist_ok: bool = False,
):
    start = time.time()

    if not exist_ok and index_dir.exists():
        shutil.rmtree(index_dir)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        if not dist_dir:
            logger.info("Building distributions...")
            build(
                targets,
                rm_destination=True,
                skip_root=False,
                short_names=short_names,
                no_hash=no_hash,
                dist_dir=tmpdir / "dist",
                build_dir=tmpdir / "build",
            )
            dist_dir = tmpdir / "dist"

        render_index(targets, no_hash, short_names, dist_dir, index_dir, exist_ok)

    # Copy the vendored build dependencies
    if (index_dir / "vendor").exists():
        shutil.rmtree(index_dir / "vendor")
    shutil.copytree(__development_base_path__ / "vendor", index_dir / "vendor")

    logger.info("Built scenarios and populated templates in %.2fs", time.time() - start)


def render_index(
    targets: list[Path],
    no_hash: bool,
    short_names: bool,
    dist_dir: Path,
    index_dir: Path,
    exist_ok: bool,
):
    """Render the index HTML (`index/simple-html`) and copy built distributions to it (`index/files`)."""
    (index_dir / "files").mkdir(parents=True, exist_ok=exist_ok)

    variables = variables_for_templates(
        targets, short_names=short_names, no_hash=no_hash
    )
    # Find all files associated with the scenarios and copy them to `index/files`
    for scenario in variables["scenarios"]:
        for package in scenario["packages"]:
            # Create a new distributions section
            package["dists"] = []
            for version in package["versions"]:
                scenario_name = (
                    scenario["name"]
                    if no_hash
                    else f"{scenario['name']}-{scenario['version']}"
                )
                for file in Path(dist_dir / scenario_name).iterdir():
                    if package["name"].replace("-", "_") + "-" + version[
                        "version"
                    ] not in str(file):
                        continue

                    # Include all the version information to start
                    dist = version.copy()
                    # Then add a sha256
                    dist["sha256"] = sha256_file(file)
                    dist["file"] = file.name
                    package["dists"].append(dist)
                    logger.info(
                        "Found distribution %s",
                        file.name,
                    )
                    shutil.copy(file, index_dir / "files" / file.name)

    logger.info("Populating template...")
    # TODO(konsti): Render the index page with all distributions, not only the incremental ones
    create_from_template(
        index_dir,
        "index",
        variables=dict(variables),
        exist_ok=exist_ok,
    )
    shutil.copy(
        __templates_path__ / "index" / "index.html",
        index_dir / "index.html",
    )
