import pytest
import yaml

from valuation_tutor.core.concepts import CORE_CONCEPTS
from valuation_tutor.core.fmt import Formatter
from valuation_tutor.core.i18n import LOCALES_DIR, Translator, placeholders

t = Translator("en")
usd, ils = Formatter("USD", t), Formatter("ILS", t)


def test_money_scales_and_signs():
    assert usd.money(3_130_000_000) == "$3.1B"
    assert usd.money(577_000_000) == "$577M"
    assert usd.money(-44_000_000) == "-$44M"
    assert ils.money(12.5e9) == "₪12.5B"
    assert usd.money(None) == "n/a" and usd.money(float("nan")) == "n/a"


def test_percent_precision():
    assert usd.pct(0.19) == "19%"
    assert usd.pct(0.054) == "5.4%"
    assert usd.pct(0.1066, decimals=1) == "10.7%"
    assert usd.pct(-0.13, signed=True) == "-13%"
    assert usd.pct(0.2, signed=True) == "+20%"


def test_other_units():
    assert usd.multiple(3.08) == "3.1x"
    assert usd.per_share(230.94) == "$230.94"


def test_missing_key_raises_instead_of_showing_the_key():
    with pytest.raises(KeyError):
        t.t("no.such.key")


def test_unknown_locale_falls_back_to_english():
    he = Translator("xx")
    assert he.t("app.title") == t.t("app.title")
    assert he.direction == "ltr"


def test_every_core_concept_has_text():
    for cid in CORE_CONCEPTS:
        for part in ("name", "plain", "analogy"):
            assert t.t(f"concepts.{cid}.{part}").strip()


def test_guides_have_all_four_parts_for_every_kind_and_variant():
    tree = yaml.safe_load((LOCALES_DIR / "en.yaml").read_text())
    for kind, guide in tree["charts"].items():
        variants = [guide] + [v for v in guide.values() if isinstance(v, dict)]
        for v in variants:
            assert {"axes", "look_first", "good", "worrying"} <= set(v), kind


def test_placeholders_helper():
    assert placeholders("{company} grew {value}") == {"company", "value"}


def test_no_yaml_boolean_traps_in_keys():
    """YAML reads bare yes/no/on/off keys as booleans, which silently loses the string."""
    def walk(node):
        for k, v in node.items():
            assert isinstance(k, str), f"key {k!r} was parsed as {type(k).__name__}; quote it"
            if isinstance(v, dict):
                walk(v)
    walk(yaml.safe_load((LOCALES_DIR / "en.yaml").read_text()))
