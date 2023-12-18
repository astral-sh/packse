import logging
from pathlib import Path

from packse.index import index_up

logger = logging.getLogger(__name__)


def serve(
    targets: list[Path],
    # host: str = "localhost",
    # port: int = 3141,
    # storage_path: Path | None = None,
):
    index_up()
