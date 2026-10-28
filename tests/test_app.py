"""Smoke tests for the Streamlit app."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "app.py")


def run():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    return at


def text(at):
    return "\n".join(m.value for m in at.markdown)


def test_sample_loads_with_the_matrix():
    at = run()
    assert "8** leadership answers and **40** staff answers" in text(at)
    assert "Blind spot" in text(at) and "Q03, Q02, Q05" in text(at)
    assert "Built by [Alexander Senderovitz]" in "\n".join(c.value for c in at.caption)


def test_two_file_mode_waits_for_both_files():
    at = run()
    at.radio(key="mode").set_value("Two files: leadership and staff").run()
    assert not at.exception
    assert "Priority matrix" not in [s.value for s in at.subheader]


def test_turning_off_the_sample_shows_nothing_and_no_error():
    at = run()
    at.checkbox(key="sample").uncheck().run()
    assert not at.exception and not at.error
