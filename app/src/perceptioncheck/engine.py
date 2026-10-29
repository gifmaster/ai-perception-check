"""AI Perception Check engine.

Takes anonymous 1 to 5 answers from leadership and staff, and finds where the two groups see AI governance
differently. All wording and thresholds live in ``rules/questions.yaml``. Nothing is stored and nothing is
guessed: the result is arithmetic on the answers, done with exact fractions so that a gap of exactly 20 points
is never lost to rounding.

Privacy by design: only a role and the answers are accepted. Any other column is refused, a value that looks
like an e-mail address is refused, and a group with too few answers is never shown.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import yaml

RULES_DIR = Path(__file__).parent / "rules"

LEADERSHIP_WORDS = {"leadership", "leader", "leaders", "management", "manager", "managers", "ledelse", "leder", "ledere",
                    "direktion", "bestyrelse"}
STAFF_WORDS = {"staff", "employee", "employees", "medarbejder", "medarbejdere", "ansat", "ansatte"}
ROLE_HEADERS = {"role", "rolle"}
# Headers that suggest personal data. Used only to give a clearer error: every unknown column is refused anyway.
PERSONAL_HEADER = re.compile(r"(name|navn|e-?mail|mail|phone|telefon|mobil|user|bruger|initial|\bid\b|\bip\b|nummer|number|department|afdeling|team)", re.I)
ANSWER = re.compile(r"^([1-5])(?:[.,]0+)?$")


class InputError(ValueError):
    """The uploaded file cannot be used. The message says what to change."""


class RulesError(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Rules
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Question:
    id: str
    dimension: str
    text: str


class Rules:
    def __init__(self, data: dict[str, Any]):
        try:
            self.last_reviewed: str = str(data.get("last_reviewed", ""))
            self.scale = {int(k): v for k, v in data["scale"].items()}
            t = data["thresholds"]
            self.min_group = int(t["min_group"])
            self.big_gap_pp = int(t["big_gap_pp"])
            self.staff_low_pct = int(t["staff_low_pct"])
            self.dimensions: dict[str, str] = dict(data["dimensions"])
            self.questions: list[Question] = [Question(**q) for q in data["questions"]]
            self.quadrants: dict[str, dict[str, Any]] = dict(data["quadrants"])
        except (KeyError, TypeError) as exc:
            raise RulesError(f"Missing or invalid field: {exc}") from exc
        self._validate()

    @classmethod
    def builtin(cls) -> "Rules":
        return cls(yaml.safe_load((RULES_DIR / "questions.yaml").read_text(encoding="utf-8")))

    def _validate(self) -> None:
        ids = [q.id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise RulesError("Duplicate question id")
        for q in self.questions:
            if q.dimension not in self.dimensions:
                raise RulesError(f"{q.id}: unknown dimension '{q.dimension}'")
            if not q.text.strip():
                raise RulesError(f"{q.id}: empty statement")
        for needed in ("blind_spot", "watch", "shared_weakness", "aligned"):
            if needed not in self.quadrants:
                raise RulesError(f"Missing quadrant '{needed}'")
        if self.min_group < 2:
            raise RulesError("min_group below 2 would not protect anyone")

    @property
    def ids(self) -> list[str]:
        return [q.id for q in self.questions]


# --------------------------------------------------------------------------- #
# Reading answers
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Response:
    role: str                       # "leadership" or "staff"
    answers: dict[str, int] = field(default_factory=dict)


def _decode(data: bytes | str) -> str:
    if isinstance(data, str):
        return data.lstrip("﻿")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")  # Excel in Denmark often saves this way


def _role(value: str, row: int) -> str:
    v = value.strip().lower()
    if v in LEADERSHIP_WORDS:
        return "leadership"
    if v in STAFF_WORDS:
        return "staff"
    raise InputError(f"Row {row}: role '{value.strip()}' is not recognised. Use 'leadership' or 'staff' (Danish: 'ledelse' or 'medarbejder').")


def parse_responses(data: bytes | str, rules: Rules, role: str | None = None) -> list[Response]:
    """Read one CSV file. Pass ``role`` when the file holds only one group; otherwise it needs a role column."""
    text = _decode(data)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise InputError("The file is empty.")
    delimiter = max(",;\t", key=lambda d: lines[0].count(d))
    rows = list(csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter))
    header = [h.strip().lower() for h in rows[0]]
    role_col = next((i for i, h in enumerate(header) if h in ROLE_HEADERS), None)
    q_cols: dict[int, str] = {}
    for i, h in enumerate(header):
        if i == role_col:
            continue
        if h in rules.ids:
            q_cols[i] = h
        elif PERSONAL_HEADER.search(h):
            raise InputError(f"Column '{rows[0][i].strip()}' looks like personal data, which this tool does not accept. "
                             f"Delete it from the file. Only a role column and the answer columns {rules.ids[0]} to {rules.ids[-1]} are read.")
        else:
            raise InputError(f"Column '{rows[0][i].strip()}' is not part of the questionnaire. Delete it from the file. "
                             f"Only a role column and the answer columns {rules.ids[0]} to {rules.ids[-1]} are read.")
    if len(set(q_cols.values())) != len(q_cols):
        raise InputError("A question column appears twice.")
    if not q_cols:
        raise InputError(f"No answer columns found. The columns must be named {rules.ids[0]} to {rules.ids[-1]}.")
    if role is None and role_col is None:
        raise InputError("The file needs a 'role' column (leadership or staff), or upload leadership and staff as two files.")
    if role is not None and role_col is not None:
        raise InputError("This file has a role column. Upload it as the combined file, not as a single group.")

    out: list[Response] = []
    for n, row in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        if any("@" in c for c in row):
            raise InputError(f"Row {n} contains an '@'. This tool does not accept e-mail addresses or other personal data.")
        who = role if role is not None else _role(row[role_col] if role_col < len(row) else "", n)
        answers: dict[str, int] = {}
        for i, qid in q_cols.items():
            raw = row[i].strip() if i < len(row) else ""
            if raw == "":
                continue
            m = ANSWER.match(raw)
            if not m:
                raise InputError(f"Row {n}, {qid}: '{raw}' is not a 1 to 5 answer.")
            answers[qid] = int(m.group(1))
        out.append(Response(who, answers))
    if not out:
        raise InputError("The file has a header but no answers.")
    return out


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class QuestionResult:
    question: Question
    n_leadership: int
    n_staff: int
    suppressed: bool
    agree_leadership: Fraction | None = None    # share answering 4 or 5
    agree_staff: Fraction | None = None
    mean_leadership: float | None = None
    mean_staff: float | None = None
    gap: Fraction | None = None                 # leadership share minus staff share, as a fraction
    quadrant: str | None = None

    @property
    def gap_pp(self) -> float | None:
        return None if self.gap is None else float(self.gap * 100)


@dataclass(frozen=True)
class Result:
    rules: Rules
    n_leadership: int
    n_staff: int
    questions: tuple[QuestionResult, ...]
    blocked: str = ""                           # why nothing is shown, when a whole group is too small

    @property
    def shown(self) -> list[QuestionResult]:
        return [q for q in self.questions if not q.suppressed]

    @property
    def hidden(self) -> list[QuestionResult]:
        return [q for q in self.questions if q.suppressed]

    def in_quadrant(self, quadrant: str) -> list[QuestionResult]:
        """Questions in a quadrant, biggest gap first."""
        return sorted((q for q in self.shown if q.quadrant == quadrant), key=lambda q: (-abs(q.gap), q.question.id))


def _classify(gap: Fraction, staff: Fraction, rules: Rules) -> str:
    big = abs(gap) >= Fraction(rules.big_gap_pp, 100)
    low = staff < Fraction(rules.staff_low_pct, 100)
    if big:
        return "blind_spot" if low else "watch"
    return "shared_weakness" if low else "aligned"


def analyse(responses: Sequence[Response], rules: Rules | None = None) -> Result:
    rules = rules or Rules.builtin()
    lead = [r for r in responses if r.role == "leadership"]
    staff = [r for r in responses if r.role == "staff"]
    blocked = ""
    small = [name for name, grp in (("leadership", lead), ("staff", staff)) if len(grp) < rules.min_group]
    if small:
        blocked = (f"Fewer than {rules.min_group} answers from {' and '.join(small)}. Nothing is shown, so that no one can be "
                   f"identified. Collect more answers, or combine groups before running the check.")
    results = []
    for q in rules.questions:
        a_l = [r.answers[q.id] for r in lead if q.id in r.answers]
        a_s = [r.answers[q.id] for r in staff if q.id in r.answers]
        if blocked or len(a_l) < rules.min_group or len(a_s) < rules.min_group:
            results.append(QuestionResult(q, len(a_l), len(a_s), suppressed=True))
            continue
        share_l = Fraction(sum(1 for a in a_l if a >= 4), len(a_l))
        share_s = Fraction(sum(1 for a in a_s if a >= 4), len(a_s))
        gap = share_l - share_s
        results.append(QuestionResult(q, len(a_l), len(a_s), False, share_l, share_s,
                                      sum(a_l) / len(a_l), sum(a_s) / len(a_s), gap, _classify(gap, share_s, rules)))
    return Result(rules, len(lead), len(staff), tuple(results), blocked)


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #


def _pct(x: Fraction) -> str:
    s = f"{float(x) * 100:.1f}"
    return (s[:-2] if s.endswith(".0") else s) + "%"


def _gap(g: Fraction) -> str:
    s = f"{float(g) * 100:+.1f}"
    return s[:-2] if s.endswith(".0") else s


def _ids(qs: Sequence[QuestionResult]) -> str:
    return ", ".join(q.question.id.upper() for q in qs) or "none"


def to_markdown(result: Result, org: str = "", today: date | None = None) -> str:
    rules, today = result.rules, today or date.today()
    lines = [f"# AI Perception Check: {org or 'our organisation'}", "",
             f"- **Date:** {today.isoformat()}",
             f"- **Answers:** {result.n_leadership} from leadership, {result.n_staff} from staff",
             f"- **Rules last reviewed:** {rules.last_reviewed}",
             f"- **Anonymity:** a statement is only shown when each group has at least {rules.min_group} answers", ""]
    if result.blocked:
        lines += [f"> **Nothing to show.** {result.blocked}", ""]
    else:
        n = len(result.shown)
        lines += [f"> {len(result.in_quadrant('blind_spot'))} of {n} statements are blind spots, "
                  f"{len(result.in_quadrant('watch'))} show different views, "
                  f"{len(result.in_quadrant('shared_weakness'))} are shared weaknesses and "
                  f"{len(result.in_quadrant('aligned'))} are aligned.", ""]
        qd = rules.quadrants
        lines += ["## Priority matrix", "",
                  f"| | Staff mostly do not agree (under {rules.staff_low_pct}%) | Staff mostly agree ({rules.staff_low_pct}% or more) |",
                  "|---|---|---|",
                  f"| **Big gap ({rules.big_gap_pp} points or more)** | {qd['blind_spot']['title']}: {_ids(result.in_quadrant('blind_spot'))} | "
                  f"{qd['watch']['title']}: {_ids(result.in_quadrant('watch'))} |",
                  f"| **Small gap** | {qd['shared_weakness']['title']}: {_ids(result.in_quadrant('shared_weakness'))} | "
                  f"{qd['aligned']['title']}: {_ids(result.in_quadrant('aligned'))} |", ""]
        lines += ["## What to do", ""]
        for key in sorted(qd, key=lambda k: qd[k]["priority"]):
            qs = result.in_quadrant(key)
            if not qs:
                continue
            lines += [f"### {qd[key]['title']}", "", f"*{qd[key]['meaning']}* {qd[key]['action']}", ""]
            for q in qs:
                lines.append(f"- **{q.question.id.upper()}.** {q.question.text} Leadership {_pct(q.agree_leadership)} agree, "
                             f"staff {_pct(q.agree_staff)} agree (gap {_gap(q.gap)} points).")
            lines.append("")
        lines += ["## All statements", "",
                  "| ID | Statement | Leadership agree | Staff agree | Gap (points) | Leadership average | Staff average | Where |",
                  "|---|---|---|---|---|---|---|---|"]
        for q in result.shown:
            lines.append(f"| {q.question.id.upper()} | {q.question.text} | {_pct(q.agree_leadership)} | {_pct(q.agree_staff)} | "
                         f"{_gap(q.gap)} | {q.mean_leadership:.1f} | {q.mean_staff:.1f} | {qd[q.quadrant]['title']} |")
        lines.append("")
    if result.hidden and not result.blocked:
        lines += [f"Not shown (fewer than {rules.min_group} answers in a group): {_ids(result.hidden)}.", ""]
    lines += ["## How to read this", "",
              "- Agree means an answer of 4 or 5 on a scale of 1 to 5. The gap is the share of leadership who agree minus the share of staff who agree.",
              "- This shows how people see things, not how things are. A gap is a reason to talk, not a finding of fact.",
              "- The answers are from the people who chose to respond. They may not represent everyone.",
              "- A small number of answers makes every figure shaky. Treat a few points of difference as noise.",
              "", "---", "",
              "*Produced with the AI Perception Check. A conversation starter for leadership, not an HR, audit or legal assessment.*", ""]
    return "\n".join(lines)


def questionnaire_markdown(rules: Rules | None = None) -> str:
    """The statements, ready to paste into a form tool. Same text for leadership and staff."""
    rules = rules or Rules.builtin()
    lines = ["# AI Perception Check: questionnaire", "",
             "Ask the same statements of leadership and staff. Answers are anonymous. Do not ask for names, e-mail addresses or teams "
             f"small enough to identify anyone. Groups with fewer than {rules.min_group} answers are never shown.", "",
             "Scale for every statement: " + ", ".join(f"{k} = {v.lower()}" for k, v in sorted(rules.scale.items())) + ".", ""]
    for dim, title in rules.dimensions.items():
        qs = [q for q in rules.questions if q.dimension == dim]
        if qs:
            lines += [f"## {title}", ""]
            lines += [f"- **{q.id.upper()}.** {q.text}" for q in qs]
            lines.append("")
    lines += ["Export the answers as CSV with one column per statement named q01 to "
              f"{rules.ids[-1]}, and a role column with the value leadership or staff.", ""]
    return "\n".join(lines)


def template_csv(rules: Rules | None = None) -> str:
    rules = rules or Rules.builtin()
    return "﻿" + ",".join(["role"] + rules.ids) + "\n"


def results_csv(result: Result) -> str:
    """The numbers per statement. No individual answers are in it."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "dimension", "statement", "n_leadership", "n_staff", "agree_leadership_pct", "agree_staff_pct",
                "gap_points", "mean_leadership", "mean_staff", "quadrant"])
    for q in result.questions:
        base = [q.question.id, q.question.dimension, q.question.text, q.n_leadership, q.n_staff]
        if q.suppressed:
            w.writerow(base + ["", "", "", "", "", "hidden"])
        else:
            w.writerow(base + [_pct(q.agree_leadership).rstrip("%"), _pct(q.agree_staff).rstrip("%"), _gap(q.gap),
                               f"{q.mean_leadership:.2f}", f"{q.mean_staff:.2f}", q.quadrant])
    return "﻿" + out.getvalue()
