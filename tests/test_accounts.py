"""Accounts: hashed ids, guest progress merged on sign-in, progress saved to the database."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("saas_valuation")
from saas_valuation.config import load_config, project_path  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

from valuation_tutor.core.learner import Learner  # noqa: E402
from valuation_tutor.core.storage import SQLStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APP = str(ROOT / "app" / "main.py")
pytestmark = pytest.mark.skipif(
    not (project_path(load_config()["data"]["processed_dir"]) / "comps.csv").exists(), reason="engine data not built")


def test_account_id_is_a_salted_hash_without_the_email():
    sys.path.insert(0, str(ROOT / "app"))
    import shared
    user = {"iss": "https://accounts.google.com", "sub": "1234", "email": "someone@example.com", "given_name": "Ada"}
    a, b = shared.account_from(user, "salt-a"), shared.account_from(user, "salt-b")
    assert a["name"] == "Ada" and len(a["id"]) == 64
    assert a["id"] != b["id"]                                   # the salt matters
    assert "someone" not in a["id"] and "1234" not in a["id"]


def test_guest_progress_moves_into_the_account_and_is_saved(tmp_path, monkeypatch):
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()                                                    # as a guest
    at.button(key="continue").click().run()
    at.button(key="skip_obs").click().run()                     # learner exists, guest-owned
    assert at.session_state["learner_owner"] is None
    at.session_state["learner"].concept("growth").mastered = True

    import shared
    db = SQLStore(f"sqlite:///{tmp_path / 'app.sqlite'}")
    saved = Learner()
    saved.complete_step("saas:revenue", True)
    db.save_learner("acct-1", saved.to_dict())                  # the account already has progress
    monkeypatch.setattr(shared, "store", lambda: db)
    monkeypatch.setattr(shared, "auth_configured", lambda: True)
    monkeypatch.setattr(shared, "account", lambda: {"id": "acct-1", "name": "Ada"})

    at.run()                                                    # now signed in
    assert not at.exception, at.exception
    lr = at.session_state["learner"]
    assert at.session_state["learner_owner"] == "acct-1"
    assert lr.step("saas:revenue").completed and lr.mastered("growth")   # both kept
    stored = Learner.from_dict(db.load_learner("acct-1"))
    assert stored.mastered("growth") and stored.step("saas:revenue").completed
