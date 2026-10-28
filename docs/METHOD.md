# Method

## The questionnaire

Fourteen statements in six areas: awareness (q01, q02, q14), policy and rules (q03, q04), shadow AI (q05, q06), skills and training (q07, q08), oversight (q09, q10) and trust and speaking up (q11, q12, q13). They follow the same themes as the five dimensions of the [Practical AI Governance Framework](https://github.com/gifmaster/ai-governance-framework): governance, people, process, technology and culture. Nothing in them comes from a law. They are a practical starting point, not a validated scale.

Every statement is worded so that agreeing is the good answer, and is answered 1 to 5. This keeps the reading simple. The cost is acquiescence: people lean towards agreeing. Because both groups answer the same wording, much of that cancels in the gap.

## What is measured

For each statement and each group: the share who answer 4 or 5 ("agree"), and the average. The **gap** is the leadership share minus the staff share, in percentage points. The share is the main measure because the answers are ordered categories, so an average hides whether a group is split.

A statement lands in one of four places:

| | Staff agree under 50% | Staff agree 50% or more |
|---|---|---|
| Gap of 20 points or more, either direction | blind spot | different views |
| Gap under 20 points | shared weakness | aligned |

The thresholds are in `rules/questions.yaml`. 20 points and 50% are judgement calls, chosen to be easy to explain. With groups as small as 5, one person is 20 points, so treat a statement near a threshold as unclear.

All comparisons use exact fractions. In floating point, 0.8 minus 0.6 is 0.20000000000000007, so a gap of exactly 20 points would have been missed.

## Anonymity

A group needs at least 5 answers to a statement before anything about it is shown, and at least 5 respondents before anything at all is shown. Only a role and the 14 answers are accepted. Any other column, any value containing "@", and any answer outside 1 to 5 stops the upload with a message saying what to remove. The tool cannot know whether a group of 5 is still identifiable in a small team, so the questionnaire advises against asking about teams.

## Testing

- `tests/ground_truth.yaml`: the development sample (8 leadership and 40 staff answers). The key was worked out by hand from the answer counts in `scripts/make_samples.py` before the tool was run. After the first run, one key entry (q07, staff average) turned out to be an arithmetic slip, 2.4 instead of 2.5. The tool was right.
- `tests/holdout_truth.yaml`: a held-out file in a different style, with a key written before the first run and run once. It passed. It contains two gaps of exactly 20 points and staff agreement of exactly 50%.
- `tests/test_engine.py`: thresholds on both sides of the boundaries, groups below the minimum, blank answers, file formats (semicolons, byte order mark, Windows-1252 from Excel, Danish role words), privacy refusals, and the rules checks.
- `tests/test_pdf.py`: every heading, bullet and quote of the Markdown report is in the PDF; the PDF carries the author credit and the rules review date.
- `tests/test_app.py`: smoke tests of the Streamlit app.

## What the held-out result does and does not show

This tool is a calculator. A pass on a held-out file shows that the arithmetic, the thresholds and the file reading are right. It does not show that the statements are good, that the thresholds are right for every organisation, or that a gap means anything in a given workplace. That needs people who know the organisation.
