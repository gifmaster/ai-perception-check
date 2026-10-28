"""The development sample against the hand-worked answer key."""

from pathlib import Path

import pytest
import yaml

from perceptioncheck import Rules, analyse, parse_responses

ROOT = Path(__file__).parents[1]
KEY = yaml.safe_load((ROOT / "tests" / "ground_truth.yaml").read_text(encoding="utf-8"))["questions"]
RULES = Rules.builtin()
RESULT = analyse(parse_responses((ROOT / "samples" / "fjordvik_perception.csv").read_bytes(), RULES), RULES)
BY_ID = {q.question.id: q for q in RESULT.questions}


def test_group_sizes():
    assert (RESULT.n_leadership, RESULT.n_staff) == (8, 40)
    assert RESULT.blocked == ""


def test_key_covers_every_question():
    assert set(KEY) == set(RULES.ids)


@pytest.mark.parametrize("qid", sorted(KEY))
def test_numbers_and_quadrant_match_the_key(qid):
    want, got = KEY[qid], BY_ID[qid]
    assert float(got.agree_leadership) * 100 == pytest.approx(want["lead"])
    assert float(got.agree_staff) * 100 == pytest.approx(want["staff"])
    assert got.gap_pp == pytest.approx(want["gap"])
    assert got.quadrant == want["quadrant"]
    assert got.mean_leadership == pytest.approx(want["mean_lead"])
    assert got.mean_staff == pytest.approx(want["mean_staff"])


def test_quadrant_sizes():
    sizes = {k: len(RESULT.in_quadrant(k)) for k in RULES.quadrants}
    assert sizes == {"blind_spot": 3, "watch": 3, "shared_weakness": 3, "aligned": 5}


def test_biggest_gap_first_within_a_quadrant():
    assert [q.question.id for q in RESULT.in_quadrant("blind_spot")] == ["q03", "q02", "q05"]
    assert [q.question.id for q in RESULT.in_quadrant("watch")] == ["q09", "q13", "q01"]


def test_two_files_give_the_same_result_as_one_with_a_role_column():
    lines = (ROOT / "samples" / "fjordvik_perception.csv").read_text(encoding="utf-8").splitlines()
    header, body = lines[0], lines[1:]
    cols = header.split(",")[1:]
    lead = "\n".join([",".join(cols)] + [ln.split(",", 1)[1] for ln in body if ln.startswith("leadership")])
    staff = "\n".join([",".join(cols)] + [ln.split(",", 1)[1] for ln in body if ln.startswith("staff")])
    two = analyse(parse_responses(lead, RULES, role="leadership") + parse_responses(staff, RULES, role="staff"), RULES)
    assert [(q.gap, q.quadrant) for q in two.questions] == [(q.gap, q.quadrant) for q in RESULT.questions]
