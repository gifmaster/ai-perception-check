"""The held-out sample: a different style of file, a key written before the first run, run once."""

from pathlib import Path

import pytest
import yaml

from perceptioncheck import Rules, analyse, parse_responses

ROOT = Path(__file__).parents[1]
KEY = yaml.safe_load((ROOT / "tests" / "holdout_truth.yaml").read_text(encoding="utf-8"))["questions"]
RULES = Rules.builtin()
RESULT = analyse(parse_responses((ROOT / "samples" / "holdout" / "kommune_ai_survey.csv").read_bytes(), RULES), RULES)
BY_ID = {q.question.id: q for q in RESULT.questions}


def test_group_sizes():
    assert (RESULT.n_leadership, RESULT.n_staff) == (5, 20)


@pytest.mark.parametrize("qid", sorted(KEY))
def test_held_out_numbers_and_quadrant(qid):
    want, got = KEY[qid], BY_ID[qid]
    assert float(got.agree_leadership) * 100 == pytest.approx(want["lead"])
    assert float(got.agree_staff) * 100 == pytest.approx(want["staff"])
    assert got.gap_pp == pytest.approx(want["gap"])
    assert got.quadrant == want["quadrant"]
