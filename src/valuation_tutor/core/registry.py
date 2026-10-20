"""Load sector modules named in config/tutor.yaml.

The core finds sectors only through this list, so adding a sector is a new
module plus one line of config; no core code changes.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import yaml

from .sector import SectorModule

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = PROJECT_ROOT / "config" / "tutor.yaml"


def load_settings(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sector(spec: str, locale: str) -> SectorModule:
    module_name, class_name = spec.split(":")
    sector = getattr(importlib.import_module(module_name), class_name)(locale=locale)
    if not isinstance(sector, SectorModule):
        raise TypeError(f"{spec} does not implement SectorModule")
    return sector


def load_sectors(settings: dict) -> dict[str, SectorModule]:
    sectors = [load_sector(spec, settings["locale"]) for spec in settings["sectors"]]
    return {s.id: s for s in sectors}
