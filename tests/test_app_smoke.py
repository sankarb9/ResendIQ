"""Smoke test: every Streamlit page renders without an exception."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

PAGES = ["views/home.py", "views/wifi_analyzer.py", "views/arq_simulator.py", "views/measured_to_arq.py", "views/live_terminal.py"]


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_arq_simulator_runs_a_simulation():
    at = AppTest.from_file(str(ROOT / "views/arq_simulator.py"), default_timeout=30)
    at.run()
    next(b for b in at.button if "Run simulation" in b.label).click().run()
    assert not at.exception, [e.value for e in at.exception]
