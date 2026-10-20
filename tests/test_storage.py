from valuation_tutor.core.learner import Learner
from valuation_tutor.core.storage import SQLStore


def test_learner_progress_round_trip(tmp_path):
    store = SQLStore(f"sqlite:///{tmp_path / 'app.sqlite'}")
    assert store.load_learner("abc") is None
    l = Learner()
    l.answer(["growth"], True, "a", True)
    store.save_learner("abc", l.to_dict())
    l.answer(["growth"], True, "b", True)
    store.save_learner("abc", l.to_dict())                 # upsert, not a second row
    assert Learner.from_dict(store.load_learner("abc")) == l
    store.delete_learner("abc")
    assert store.load_learner("abc") is None


def test_survives_reopening(tmp_path):
    url = f"sqlite:///{tmp_path / 'app.sqlite'}"
    SQLStore(url).save_learner("x", {"xp": 5})
    assert SQLStore(url).load_learner("x") == {"xp": 5}
