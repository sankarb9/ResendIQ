import pytest

from resendiq.wifi import core


def test_summarize_loss_and_stats():
    m = core.summarize([10.0, 20.0, None, 30.0])
    assert m["sent"] == 4 and m["received"] == 3 and m["loss"] == 25.0
    assert m["avg"] == 20.0 and m["min"] == 10.0 and m["max"] == 30.0


def test_all_lost_is_dead_zone_and_unreachable():
    m = core.summarize([None, None])
    assert core.reachability(m) == "Unreachable" and core.score(m) == 0.0 and core.classify(m) == "Potential Dead Zone"


def test_classification_thresholds():
    stable = dict(received=10, loss=0.0, avg=20.0, jitter=5.0)
    fair = dict(received=10, loss=3.0, avg=80.0, jitter=20.0)
    unstable = dict(received=10, loss=8.0, avg=150.0, jitter=40.0)
    dead = dict(received=10, loss=12.0, avg=20.0, jitter=1.0)
    assert [core.classify(x) for x in (stable, fair, unstable, dead)] == \
        ["Stable", "Fair", "Unstable", "Potential Dead Zone"]


def test_score_bounds_and_ordering():
    good = core.score(dict(received=10, loss=0.0, avg=20.0, jitter=0.0))
    bad = core.score(dict(received=10, loss=9.0, avg=190.0, jitter=45.0))
    assert good == 100.0 and 0 <= bad < good


def test_mean_ci():
    assert core.mean_ci([]) == (None, None, None)
    assert core.mean_ci([5.0]) == (5.0, None, None)
    mean, sd, ci = core.mean_ci([10.0, 20.0, 30.0])
    assert mean == 20.0 and sd == 10.0 and ci == pytest.approx(4.303 * 10 / 3 ** 0.5, abs=0.1)
