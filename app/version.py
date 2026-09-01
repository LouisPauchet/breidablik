"""Single source of truth for the app version: pyproject.toml's [project].version. Read
directly from the file (rather than importlib.metadata) so it works identically whether or
not the package has been pip-installed — true in Docker/Passenger, but not for a plain
`pytest`/`uvicorn --reload` run against the source tree.
"""

import tomllib
from functools import lru_cache
from pathlib import Path

_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


@lru_cache
def get_version() -> str:
    with _PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]
