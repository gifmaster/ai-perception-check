"""Writes the sample CSV files from answer counts.

Each table lists, per statement, how many people gave answer 1, 2, 3, 4 and 5. The counts are the input.
The expected results in tests/ground_truth.yaml and tests/holdout_truth.yaml were worked out by hand from
these counts, not produced by the tool.

Run:  python scripts/make_samples.py
"""

from __future__ import annotations

import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Development sample: Fjordvik Logistik (fictional). Leadership n=8, staff n=40.
DEV_LEAD = {
    "q01": [0, 0, 1, 3, 4], "q02": [0, 0, 0, 4, 4], "q03": [0, 0, 0, 2, 6], "q04": [1, 2, 2, 2, 1],
    "q05": [0, 0, 2, 3, 3], "q06": [0, 1, 1, 3, 3], "q07": [1, 3, 2, 2, 0], "q08": [0, 0, 2, 4, 2],
    "q09": [0, 0, 0, 2, 6], "q10": [1, 2, 3, 2, 0], "q11": [0, 0, 1, 4, 3], "q12": [0, 0, 2, 3, 3],
    "q13": [1, 3, 1, 2, 1], "q14": [0, 1, 1, 3, 3],
}
DEV_STAFF = {
    "q01": [2, 6, 10, 14, 8], "q02": [8, 12, 10, 7, 3], "q03": [10, 14, 8, 6, 2], "q04": [8, 12, 10, 8, 2],
    "q05": [6, 12, 10, 9, 3], "q06": [2, 5, 9, 16, 8], "q07": [8, 14, 10, 6, 2], "q08": [1, 4, 10, 17, 8],
    "q09": [2, 6, 10, 14, 8], "q10": [9, 13, 10, 6, 2], "q11": [1, 4, 7, 17, 11], "q12": [2, 5, 10, 15, 8],
    "q13": [1, 4, 5, 18, 12], "q14": [2, 6, 8, 16, 8],
}

# Held-out sample: a municipality (fictional). Leadership n=5, staff n=20.
HOLD_LEAD = {
    "q01": [0, 0, 0, 1, 4], "q02": [0, 0, 1, 2, 2], "q03": [0, 1, 1, 2, 1], "q04": [1, 1, 1, 1, 1],
    "q05": [0, 0, 0, 2, 3], "q06": [0, 0, 1, 1, 3], "q07": [2, 1, 1, 1, 0], "q08": [0, 0, 0, 1, 4],
    "q09": [0, 0, 2, 2, 1], "q10": [0, 0, 1, 3, 1], "q11": [0, 1, 2, 1, 1], "q12": [0, 0, 1, 2, 2],
    "q13": [1, 2, 1, 1, 0], "q14": [0, 0, 0, 3, 2],
}
HOLD_STAFF = {
    "q01": [0, 1, 3, 8, 8], "q02": [2, 4, 4, 6, 4], "q03": [4, 6, 5, 4, 1], "q04": [3, 6, 5, 4, 2],
    "q05": [0, 1, 2, 9, 8], "q06": [1, 2, 3, 8, 6], "q07": [5, 6, 4, 3, 2], "q08": [4, 6, 6, 3, 1],
    "q09": [0, 3, 6, 7, 4], "q10": [1, 2, 5, 9, 3], "q11": [0, 1, 3, 9, 7], "q12": [0, 2, 4, 8, 6],
    "q13": [6, 6, 4, 3, 1], "q14": [1, 3, 5, 7, 4],
}

# Too few leadership answers (4) to be shown.
SMALL_LEAD = {q: [0, 0, 1, 2, 1] for q in DEV_LEAD}


def column(counts: list[int], rng: random.Random) -> list[int]:
    values = [score for score, n in enumerate(counts, start=1) for _ in range(n)]
    rng.shuffle(values)
    return values


def rows(table: dict[str, list[int]], seed: int) -> list[list[int]]:
    rng = random.Random(seed)
    cols = [column(table[q], rng) for q in sorted(table)]
    return [list(r) for r in zip(*cols)]


def write(path: Path, header: list[str], body: list[list[str]], sep: str = ",", bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(sep.join(r) for r in [header] + body) + "\n"
    path.write_text(("﻿" if bom else "") + text, encoding="utf-8")


def main() -> None:
    ids = sorted(DEV_LEAD)
    body = [["leadership"] + [str(v) for v in r] for r in rows(DEV_LEAD, 1)]
    body += [["staff"] + [str(v) for v in r] for r in rows(DEV_STAFF, 2)]
    write(ROOT / "samples" / "fjordvik_perception.csv", ["role"] + ids, body)

    body = [["Ledelse"] + [str(v) for v in r] for r in rows(HOLD_LEAD, 11)]
    body += [["Medarbejder"] + [str(v) for v in r] for r in rows(HOLD_STAFF, 12)]
    write(ROOT / "samples" / "holdout" / "kommune_ai_survey.csv", ["Rolle"] + [i.upper() for i in ids], body, sep=";", bom=True)

    body = [["leadership"] + [str(v) for v in r] for r in rows(SMALL_LEAD, 3)]
    body += [["staff"] + [str(v) for v in r] for r in rows(DEV_STAFF, 2)]
    write(ROOT / "samples" / "small_group.csv", ["role"] + ids, body)


if __name__ == "__main__":
    main()
