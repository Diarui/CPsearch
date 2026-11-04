"""Private access to the packaged default configuration."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any


def load_default_config() -> dict[str, Any]:
    resource = files("evidence_control").joinpath("default_config.json")
    return json.loads(resource.read_text(encoding="utf-8"))

