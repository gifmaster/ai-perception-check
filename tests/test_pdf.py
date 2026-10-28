"""The PDF must say exactly what the Markdown report says, and carry the author credit."""

import io
import re
from datetime import date
from pathlib import Path

import pytest

pypdf = pytest.importorskip("pypdf")

from perceptioncheck import Rules, analyse, parse_responses, to_markdown  # noqa: E402
from perceptioncheck.pdf import fpdf_markdown, markdown_to_pdf, plain, spans  # noqa: E402

ROOT = Path(__file__).parents[1]
RULES = Rules.builtin()


def raw_text(data: bytes) -> str:
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(data)).pages))


def body_text(data: bytes) -> str:
    """The PDF's text without the running header and footer lines, so text that breaks across pages reads on."""
    pages = []
    for n, page in enumerate(pypdf.PdfReader(io.BytesIO(data)).pages):
        lines = (page.extract_text() or "").splitlines()
        lines = [ln for ln in lines if not re.search(r"\|\s+page \d+ of \d+$", ln) and not ln.startswith("Rules last reviewed:")]
        if n > 0 and lines:
            lines = lines[1:]
        pages.append(" ".join(lines))
    return re.sub(r"\s+", " ", " ".join(pages))


def assert_same_content(md: str, data: bytes) -> int:
    text, checked = body_text(data), 0
    for line in md.splitlines():
        if line.startswith(("#", "- ", ">")):
            body = re.sub(r"\s+", " ", plain(re.sub(r"^(#+ |- \[[ xX]\] |- |> ?)", "", line))).strip()
            if body:
                assert body in text, body
                checked += 1
    return checked


def report() -> str:
    rs = parse_responses((ROOT / "samples" / "fjordvik_perception.csv").read_bytes(), RULES)
    return to_markdown(analyse(rs, RULES), "Fjordvik Logistik", date(2026, 10, 28))


def test_pdf_says_what_the_markdown_says():
    md = report()
    assert assert_same_content(md, markdown_to_pdf(md, "AI Perception Check", reviewed=RULES.last_reviewed)) >= 12


def test_matrix_and_table_figures_are_in_the_pdf():
    text = body_text(markdown_to_pdf(report(), "AI Perception Check"))
    for needle in ("Priority matrix", "Blind spot: Q03, Q02, Q05", "Aligned: Q11, Q12, Q06, Q14, Q08", "+80", "-37.5", "100%", "87.5%"):
        assert needle in text, needle


def test_pdf_credits_the_author_and_the_review_date():
    data = markdown_to_pdf(report(), "AI Perception Check", reviewed=RULES.last_reviewed)
    raw = raw_text(data)
    assert "Built by Alexander Senderovitz, senderovitz.eu" in raw
    assert f"Rules last reviewed: {RULES.last_reviewed} by Alexander Senderovitz" in raw
    assert pypdf.PdfReader(io.BytesIO(data)).metadata.author == "Alexander Senderovitz"


def test_a_blocked_report_is_still_a_valid_pdf():
    rs = parse_responses((ROOT / "samples" / "small_group.csv").read_bytes(), RULES)
    md = to_markdown(analyse(rs, RULES), "Org", date(2026, 10, 28))
    assert "Nothing to show" in md
    assert "Nothing to show" in body_text(markdown_to_pdf(md, "AI Perception Check"))


def test_inline_parsing():
    assert spans("a **b** *c*")[1] == ("B", "b", None)
    assert fpdf_markdown("*(x)* A--B") == "__(x)__ A\\--B"
