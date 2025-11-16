from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def ensure_local_packages_importable() -> None:
    """
    Add the repo's packages/python directory to sys.path when running directly.

    This allows developers to run the server without installing editable packages
    via uv/pip, while production deployments can still rely on installed deps.
    """

    current = Path(__file__).resolve()
    for ancestor in current.parents:
        packages_dir = ancestor / "packages" / "python"
        if packages_dir.exists():
            packages_path = str(packages_dir)
            if packages_path not in sys.path:
                sys.path.insert(0, packages_path)
            return
