"""Unit tests: thresholds, privacy guards, parsing and the report."""

import pytest

from perceptioncheck import Response, Rules, analyse, parse_responses, questionnaire_markdown, results_csv, template_csv, to_markdown
from perceptioncheck.engine import InputError, RulesError

RULES = Rules.builtin()
IDS = ",".join(RULES.ids)


def responses(lead, staff, qid="q01"):
    """Build responses answering one statement. lead and staff are lists of answers."""
    return [Response("leadership", {qid: a}) for a in lead] + [Response("staff", {qid: a}) for a in staff]


def quadrant(lead, staff):
    return analyse(responses(lead, staff), RULES).questions[0].quadrant


# --- thresholds ----------------------------------------------------------------------------------

def test_a_gap_of_exactly_twenty_points_is_big():
    # leadership 5/5 agree = 100%, staff 4/5 = 80%
    assert quadrant([5] * 5, [4, 4, 4, 4, 2]) == "watch"


def test_a_gap_just_under_twenty_points_is_small():
    # leadership 4/5 = 80%, staff 13/20 = 65% -> hold the arithmetic with fractions: 15 points
    r = analyse(responses([5, 5, 5, 5, 2], [4] * 13 + [2] * 7), RULES)
    assert r.questions[0].quadrant == "aligned"


def test_staff_at_exactly_fifty_percent_is_not_low():
    assert quadrant([5] * 5, [4, 4, 4, 4, 4, 2, 2, 2, 2, 2]) == "watch"  # staff 50%, gap 50


def test_staff_just_under_fifty_percent_is_low():
    assert quadrant([5] * 5, [4, 4, 4, 4, 2, 2, 2, 2, 2, 2]) == "blind_spot"


def test_staff_more_positive_than_leadership_is_a_big_gap_too():
    r = analyse(responses([2, 2, 2, 2, 5], [5] * 10), RULES)
    q = r.questions[0]
    assert q.gap_pp == pytest.approx(-80.0) and q.quadrant == "watch"


def test_neutral_three_is_not_agreement():
    r = analyse(responses([3] * 5, [3] * 5), RULES)
    assert r.questions[0].agree_leadership == 0 and r.questions[0].quadrant == "shared_weakness"


# --- small groups --------------------------------------------------------------------------------

def test_a_group_below_the_minimum_blocks_everything():
    r = analyse(responses([5] * 4, [3] * 30), RULES)
    assert r.blocked and "leadership" in r.blocked
    assert all(q.suppressed and q.gap is None and q.agree_staff is None for q in r.questions)
    md = to_markdown(r, "Org")
    assert "Nothing to show" in md and "Priority matrix" not in md


def test_one_statement_with_too_few_answers_is_hidden_alone():
    # q02 is answered by only 4 leaders, q01 by 5
    rs = [Response("leadership", {"q01": 5, "q02": 5}) for _ in range(4)] + [Response("leadership", {"q01": 5})]
    rs += [Response("staff", {"q01": 3, "q02": 3}) for _ in range(6)]
    r = analyse(rs, RULES)
    by = {q.question.id: q for q in r.questions}
    assert not by["q01"].suppressed and by["q02"].suppressed
    assert "Not shown" in to_markdown(r) and "Q02" in to_markdown(r)


def test_blank_answers_are_skipped_not_counted():
    rs = [Response("leadership", {"q01": 5}) for _ in range(5)] + [Response("leadership", {}) for _ in range(3)]
    rs += [Response("staff", {"q01": 3}) for _ in range(5)]
    q = analyse(rs, RULES).questions[0]
    assert q.n_leadership == 5 and q.agree_leadership == 1


# --- reading files -------------------------------------------------------------------------------

def test_semicolons_bom_danish_roles_and_capital_headers():
    text = "﻿Rolle;Q01;Q02\nLedelse;5;4\nMedarbejder;3;2\n"
    rs = parse_responses(text, RULES)
    assert [(r.role, r.answers) for r in rs] == [("leadership", {"q01": 5, "q02": 4}), ("staff", {"q01": 3, "q02": 2})]


def test_cp1252_file_from_excel():
    data = "role;q01\nledelse;4\nmedarbejder;3\n".encode("cp1252")
    assert len(parse_responses(data, RULES)) == 2


def test_decimal_comma_five_is_read_as_five():
    assert parse_responses("role,q01\nstaff,4.0\n", RULES)[0].answers == {"q01": 4}


@pytest.mark.parametrize("bad", ["0", "6", "agree", "3.5", "-1"])
def test_answers_outside_one_to_five_are_refused_with_the_row(bad):
    with pytest.raises(InputError, match="Row 3, q01"):
        parse_responses(f"role,q01\nstaff,3\nstaff,{bad}\n", RULES)


def test_unknown_role_is_refused():
    with pytest.raises(InputError, match="not recognised"):
        parse_responses("role,q01\nCEO,5\n", RULES)


def test_file_without_role_needs_a_role_argument_and_the_reverse():
    with pytest.raises(InputError, match="role"):
        parse_responses("q01\n5\n", RULES)
    assert parse_responses("q01\n5\n", RULES, role="staff")[0].role == "staff"
    with pytest.raises(InputError, match="role column"):
        parse_responses("role,q01\nstaff,5\n", RULES, role="staff")


def test_empty_and_header_only_files():
    with pytest.raises(InputError):
        parse_responses("", RULES)
    with pytest.raises(InputError, match="no answers"):
        parse_responses("role,q01\n", RULES)


# --- privacy -------------------------------------------------------------------------------------

@pytest.mark.parametrize("header", ["Name", "E-mail", "email", "Navn", "Telefon", "Team", "Department", "Initials", "User ID", "Timestamp", "Comment"])
def test_any_column_that_is_not_a_role_or_an_answer_is_refused(header):
    with pytest.raises(InputError, match="Delete it"):
        parse_responses(f"role,{header},q01\nstaff,x,5\n", RULES)


def test_personal_looking_headers_get_the_personal_data_message():
    with pytest.raises(InputError, match="personal data"):
        parse_responses("role,Email,q01\nstaff,a,5\n", RULES)


def test_an_email_address_in_any_cell_is_refused():
    with pytest.raises(InputError, match="@"):
        parse_responses("role,q01\nstaff,5\nstaff,anna@firma.dk\n", RULES)


def test_the_report_and_csv_hold_no_individual_answers():
    rs = parse_responses(open("samples/fjordvik_perception.csv", encoding="utf-8").read(), RULES)
    r = analyse(rs, RULES)
    md, csv_text = to_markdown(r, "Org"), results_csv(r)
    assert "role" not in csv_text.splitlines()[0].split(",")
    assert len(csv_text.splitlines()) == 1 + len(RULES.ids)
    assert "leadership,4,4,5" not in md


# --- rules and outputs ---------------------------------------------------------------------------

def test_every_statement_has_a_known_dimension_and_ids_are_q01_to_q14():
    assert RULES.ids == [f"q{n:02d}" for n in range(1, 15)]


def test_rules_reject_a_missing_quadrant():
    import yaml
    from perceptioncheck.engine import RULES_DIR
    data = yaml.safe_load((RULES_DIR / "questions.yaml").read_text(encoding="utf-8"))
    del data["quadrants"]["aligned"]
    with pytest.raises(RulesError, match="aligned"):
        Rules(data)


def test_template_and_questionnaire_match_the_rules():
    assert template_csv(RULES).lstrip("﻿").strip() == "role," + IDS
    md = questionnaire_markdown(RULES)
    assert all(q.text in md for q in RULES.questions)
    assert "never shown" in md


def test_report_lists_every_shown_question_once_in_the_table():
    rs = parse_responses(open("samples/fjordvik_perception.csv", encoding="utf-8").read(), RULES)
    md = to_markdown(analyse(rs, RULES), "Fjordvik")
    assert md.count("| Q0") + md.count("| Q1") >= 14
    assert "3 of 14 statements are blind spots" in md
    assert "Rules last reviewed" in md
