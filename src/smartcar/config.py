from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

PathLike = Union[str, Path]


def load_config(path: PathLike) -> Dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_project_path(value: str, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (project_root / path).resolve()
