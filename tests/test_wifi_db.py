import pytest

from resendiq.wifi import core, db


@pytest.fixture()
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", str(tmp_path / "sub" / "t.db"))   # parent dir is created on demand
    db.init()


def test_save_and_load_session_roundtrip(tmpdb):
    samples = {"external": [20.0, 25.0, None, 30.0]}
    result = core.evaluate(samples)
    db.save_session("Room A", 2, result, samples, band="5 GHz")
    df = db.load_sessions()
    assert len(df) == 1 and df.loc[0, "location"] == "Room A" and df.loc[0, "loss_pct"] == 25.0


def test_coords_and_clear(tmpdb):
    db.save_coord("Room A", 0.2, 0.4)
    assert db.load_coords() == {"Room A": (0.2, 0.4)}
    db.clear_all()
    assert db.load_sessions().empty
