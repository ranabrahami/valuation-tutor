"""Every learner-facing string, looked up by key from core/locales/<locale>.yaml.

Sectors keep their own content in their own locale files; the core never
contains English sentences in code. Adding Hebrew means adding he.yaml files
(the locale declares direction: rtl), not editing Python.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Formatter

import yaml

LOCALES_DIR = Path(__file__).parent / "locales"
DEFAULT_LOCALE = "en"


@lru_cache
def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _lookup(tree: dict, key: str):
    node = tree
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


class Translator:
    """t("charts.trend.title", company="HubSpot") -> the string in the active locale.

    Falls back to English for keys a locale hasn't translated yet. A key missing
    in English too is a bug, so it raises instead of showing the key to a learner.
    """

    def __init__(self, locale: str = DEFAULT_LOCALE, locales_dir: Path = LOCALES_DIR):
        self.locale = locale
        self._tree = _load(locales_dir / f"{locale}.yaml") if (locales_dir / f"{locale}.yaml").exists() else {}
        self._fallback = _load(locales_dir / f"{DEFAULT_LOCALE}.yaml")

    @property
    def direction(self) -> str:
        return self.get("meta.direction") or "ltr"

    def get(self, key: str):
        value = _lookup(self._tree, key)
        return value if value is not None else _lookup(self._fallback, key)

    def t(self, key: str, **params) -> str:
        template = self.get(key)
        if template is None:
            raise KeyError(f"Missing translation key: {key}")
        if not isinstance(template, str):
            raise TypeError(f"Translation key {key} is not a string")
        return template.format(**params) if params else template

    def has(self, key: str) -> bool:
        return self.get(key) is not None


def placeholders(template: str) -> set[str]:
    """Names used in a template, e.g. {"company", "value"}; used by tests."""
    return {name for _, name, _, _ in Formatter().parse(template) if name}
