"""Streamlit front end for the AI Perception Check.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from perceptioncheck import Rules, analyse, parse_responses, questionnaire_markdown, results_csv, template_csv, to_markdown  # noqa: E402
from perceptioncheck.engine import InputError  # noqa: E402
from perceptioncheck.pdf import markdown_to_pdf  # noqa: E402

REPO = "https://github.com/gifmaster/ai-perception-check"
SAMPLE = ROOT / "samples" / "fjordvik_perception.csv"

st.set_page_config(page_title="AI Perception Check", page_icon="🔍", layout="wide")


@st.cache_resource
def rules() -> Rules:
    return Rules.builtin()


R = rules()
QUAD_COLOUR = {"blind_spot": "#c0392b", "watch": "#d68910", "shared_weakness": "#7f8c8d", "aligned": "#1e8449"}

st.title("AI Perception Check")
st.caption(f"Built by [Alexander Senderovitz](https://senderovitz.eu) · Rules last reviewed {R.last_reviewed}")
st.write("Do leadership and staff see AI governance the same way? Upload anonymous answers from both groups and see where "
         "they differ most. The gap is where the work is.")

# --- Sidebar ---------------------------------------------------------------------
with st.sidebar:
    st.header("Before you start")
    org = st.text_input("Organisation (for the report)", placeholder="e.g. Fjordvik Logistik")
    st.markdown("**1. Ask the same 14 statements** of leadership and staff, in any form tool.")
    st.download_button("Download the questionnaire", questionnaire_markdown(R), "ai-perception-questionnaire.md", "text/markdown",
                       help="Ready to paste into Google Forms, Microsoft Forms or similar.")
    st.markdown("**2. Export the answers as CSV** with a role column and the columns q01 to q14.")
    st.download_button("Download the CSV template", template_csv(R), "ai-perception-template.csv", "text/csv")
    st.divider()
    st.caption("Screening aid. It shows how people see things, not how things are.")

# --- Data ------------------------------------------------------------------------
st.info(f"**Privacy.** Nothing is stored on the server, but the file is processed in the cloud while the page is open. "
        f"Upload anonymous answers only: no names, e-mail addresses or teams. Columns other than the role and the answers are "
        f"refused, and any group with fewer than {R.min_group} answers is never shown. For sensitive data, run it on your own "
        f"computer (see the [repository]({REPO})).")

mode = st.radio("Your files", ["One file with a role column", "Two files: leadership and staff"], horizontal=True, key="mode")
responses, error = [], ""
if mode.startswith("One"):
    up = st.file_uploader("Answers (CSV)", type=["csv", "txt"], key="one")
    use_sample = st.checkbox("Use the fictional sample (Fjordvik Logistik, 8 leadership and 40 staff answers)", value=up is None, key="sample")
    try:
        if up is not None:
            responses = parse_responses(up.getvalue(), R)
        elif use_sample:
            responses = parse_responses(SAMPLE.read_bytes(), R)
            org = org or "Fjordvik Logistik (fictional)"
    except InputError as exc:
        error = str(exc)
else:
    c1, c2 = st.columns(2)
    lead_up = c1.file_uploader("Leadership answers (CSV)", type=["csv", "txt"], key="lead")
    staff_up = c2.file_uploader("Staff answers (CSV)", type=["csv", "txt"], key="staff")
    try:
        if lead_up is not None and staff_up is not None:
            responses = parse_responses(lead_up.getvalue(), R, role="leadership") + parse_responses(staff_up.getvalue(), R, role="staff")
    except InputError as exc:
        error = str(exc)

if error:
    st.error(error)
    st.stop()
if not responses:
    st.stop()

result = analyse(responses, R)
st.write(f"**{result.n_leadership}** leadership answers and **{result.n_staff}** staff answers.")
if result.blocked:
    st.warning(result.blocked)
    st.stop()

md = to_markdown(result, org)
d1, d2, d3 = st.columns(3)
d1.download_button("Download report (PDF)", markdown_to_pdf(md, "AI Perception Check", reviewed=R.last_reviewed),
                   "ai-perception-check.pdf", "application/pdf", type="primary", width="stretch")
d2.download_button("Download report (Markdown)", md, "ai-perception-check.md", "text/markdown", width="stretch")
d3.download_button("Download the numbers (CSV)", results_csv(result), "ai-perception-numbers.csv", "text/csv", width="stretch",
                   help="One row per statement. No individual answers.")

# --- Matrix ----------------------------------------------------------------------
st.subheader("Priority matrix")
st.caption(f"Big gap means {R.big_gap_pp} points or more between the share of leadership and the share of staff who agree. "
           f"Staff are 'low' when under {R.staff_low_pct}% agree.")
grid = [("blind_spot", "watch"), ("shared_weakness", "aligned")]
heads = [f"Staff under {R.staff_low_pct}% agree", f"Staff {R.staff_low_pct}% or more agree"]
for row_title, row in zip((f"Big gap ({R.big_gap_pp}+ points)", "Small gap"), grid):
    st.markdown(f"**{row_title}**")
    cols = st.columns(2)
    for col, key, head in zip(cols, row, heads):
        qs = result.in_quadrant(key)
        with col.container(border=True):
            st.markdown(f"**{R.quadrants[key]['title']}** · {head}  \n{', '.join(q.question.id.upper() for q in qs) or 'none'}")
            st.caption(R.quadrants[key]["action"])

df = pd.DataFrame([{"Statement": q.question.id.upper(), "Gap (points)": q.gap_pp, "Staff agree (%)": float(q.agree_staff) * 100,
                    "Where": R.quadrants[q.quadrant]["title"], "q": q.quadrant} for q in result.shown])
colour = alt.Scale(domain=[R.quadrants[k]["title"] for k in QUAD_COLOUR], range=list(QUAD_COLOUR.values()))
base = alt.Chart(df).encode(x=alt.X("Gap (points):Q", title="Gap: leadership agree minus staff agree (points)"),
                            y=alt.Y("Staff agree (%):Q", title="Staff who agree (%)", scale=alt.Scale(domain=[0, 100])))
chart = base.mark_circle(size=140).encode(color=alt.Color("Where:N", scale=colour, legend=alt.Legend(title=None)),
                                          tooltip=["Statement", "Gap (points)", "Staff agree (%)", "Where"])
labels = base.mark_text(dy=-12, fontSize=11).encode(text="Statement")
st.altair_chart(chart + labels, width="stretch")

# --- Detail ----------------------------------------------------------------------
st.subheader("What to do")
for key in sorted(R.quadrants, key=lambda k: R.quadrants[k]["priority"]):
    qs = result.in_quadrant(key)
    if qs:
        with st.expander(f"{R.quadrants[key]['title']} ({len(qs)})", expanded=key == "blind_spot"):
            st.markdown(f"*{R.quadrants[key]['meaning']}* {R.quadrants[key]['action']}")
            for q in qs:
                st.markdown(f"- **{q.question.id.upper()}.** {q.question.text}  \n  Leadership {float(q.agree_leadership) * 100:.0f}% agree, "
                            f"staff {float(q.agree_staff) * 100:.0f}% agree (gap {q.gap_pp:+.0f} points)")

if result.hidden:
    st.caption("Not shown (too few answers): " + ", ".join(q.question.id.upper() for q in result.hidden))

with st.expander("How to read this"):
    st.markdown("- Agree means 4 or 5 on a 1 to 5 scale.\n- A gap shows how people see things, not how things are. It is a reason to talk, not a finding.\n"
                "- Only people who chose to answer are included, so the picture may not represent everyone.\n"
                "- With few answers every figure is shaky. Treat a few points of difference as noise.\n"
                f"- Rules, wording and thresholds are in [`rules/questions.yaml`]({REPO}/blob/main/src/perceptioncheck/rules/questions.yaml).")
