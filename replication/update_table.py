"""Maintainer script for the shared results table (20 homodipeptides x 2 acids).

Members never edit replications.csv. A maintainer runs this on rows from APPROVED hand-ins (each
dipeptide hand-in saves handin/dipeptide-verdict/replication_rows.csv), then opens one pull request.

    python replication/update_table.py --reference                    # add the Rakiura reference rows
    python replication/update_table.py --rows a.csv b.csv --reviewed-on 2026-11-02 [--credit "A. Name"]
    python replication/update_table.py --grid-only                    # just regenerate the README grid

Rows are validated against schema.json. Public data only: any row whose dataset is not the public
dipeptide record is refused.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

TABLE = os.path.join(HERE, "replications.csv")
README = os.path.join(HERE, "README.md")
SCHEMA = json.load(open(os.path.join(HERE, "schema.json")))
COLUMNS = [c["name"] for c in SCHEMA["columns"]]
DIPEPTIDES = ["AA", "CC", "DD", "EE", "FF", "GG", "HH", "II", "KK", "LL", "MM", "NN", "PP", "QQ", "RR", "SS",
              "TT", "VV", "WW", "YY"]
VERDICTS = {"survives", "degrades", "side chain modified", "unsure"}
PUBLIC_DOI = "10.5281/zenodo.11223995"
BEGIN, END = "<!-- grid:begin -->", "<!-- grid:end -->"


def read_table() -> list[dict]:
    with open(TABLE, newline="") as fh:
        return list(csv.DictReader(fh))


def write_table(rows: list[dict]) -> None:
    with open(TABLE, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def validate(row: dict) -> list[str]:
    errs = []
    if set(row) != set(COLUMNS):
        errs.append(f"columns differ: {sorted(set(row) ^ set(COLUMNS))}")
    if row.get("dataset_doi") != PUBLIC_DOI:
        errs.append("not the public dipeptide dataset: rows from unpublished data never enter this table")
    if row.get("dipeptide") not in DIPEPTIDES:
        errs.append(f"unknown dipeptide {row.get('dipeptide')!r}")
    if (str(row.get("acid_code")), str(row.get("acid_wt_pct"))) not in {("K", "98"), ("H", "81")}:
        errs.append("acid must be K/98 or H/81")
    if row.get("verdict") not in VERDICTS:
        errs.append(f"verdict {row.get('verdict')!r} is not one of {sorted(VERDICTS)}")
    if row.get("matches_published") not in {"yes", "no", "unsure"}:
        errs.append("matches_published must be yes, no or unsure")
    return errs


def next_id(rows: list[dict]) -> str:
    n = [int(r["row_id"][2:]) for r in rows if r["row_id"].startswith("R-")]
    return f"R-{(max(n) if n else 0) + 1:04d}"


def add_reference(rows: list[dict]) -> int:
    import nmrtrain as nt
    key = nt.answers.load("dipeptides", quiet=True)
    have = {r["row_id"] for r in rows}
    added = 0
    for cid, c in sorted(key["cases"].items()):
        rid = f"REF-{cid}"
        if rid in have:
            continue
        verdict = c["call"]   # the key holds published calls only
        rows.append({"row_id": rid, "dipeptide": c["sample"], "dipeptide_name": nt.io.NAMES[c["sample"]],
                     "acid_wt_pct": {"K": 98, "H": 81}[c["acid"]], "acid_code": c["acid"], "nucleus": "1H",
                     "time_points": f"{c['first']};{c['last']}", "processing": "pdata",
                     "tool": f"nmrtrain key {key['version']} (published calls only)", "verdict": verdict,
                     "main_product": "", "matches_published": "yes", "traps_flagged": 0,
                     "dataset_doi": PUBLIC_DOI, "reviewed_on": "", "contributor": "Rakiura reference"})
        added += 1
    return added


def add_rows(rows: list[dict], files: list[str], reviewed_on: str, credit: str | None) -> int:
    added = 0
    for path in files:
        with open(path, newline="") as fh:
            for row in csv.DictReader(fh):
                row = {k: (row.get(k) or "") for k in COLUMNS}
                row["reviewed_on"] = reviewed_on
                row["contributor"] = credit or "Rakiura member"
                row["row_id"] = next_id(rows)
                errs = validate(row)
                if errs:
                    raise SystemExit(f"{path}: refused ({'; '.join(errs)})")
                rows.append(row)
                added += 1
    return added


def grid(rows: list[dict]) -> str:
    members = [r for r in rows if r["row_id"].startswith("R-")]
    lines = ["| Dipeptide | 98% (K) | 81% (H) |", "|---|---|---|"]
    covered = 0
    for d in DIPEPTIDES:
        cells = []
        for acid in ("K", "H"):
            mine = [r for r in members if r["dipeptide"] == d and r["acid_code"] == acid]
            ref = next((r for r in rows if r["row_id"] == f"REF-{d}-{acid}"), None)
            calls = sorted({r["verdict"] for r in mine})
            agree = sum(1 for r in mine if r["matches_published"] == "yes")
            text = f"{len(mine)} replication(s)" if mine else "open"
            if mine:
                covered += 1
                text += f": {', '.join(calls)}" + (f"; {agree} match the paper" if agree else "")
            if ref:
                text += f" (reference: {ref['verdict']})"
            cells.append(text)
        lines.append(f"| {d} | {cells[0]} | {cells[1]} |")
    people = len({r["contributor"] for r in members})
    head = (f"{covered} of 40 conditions replicated by {people} contributor(s). "
            f"Updated {dt.date.today().isoformat()}.")
    return head + "\n\n" + "\n".join(lines)


def write_grid(rows: list[dict]) -> None:
    text = open(README).read()
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    open(README, "w").write(text[:a] + "\n" + grid(rows) + "\n" + text[b:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", nargs="*", default=[])
    ap.add_argument("--reviewed-on", default=dt.date.today().isoformat())
    ap.add_argument("--credit", help="display name, only with the member's opt-in")
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--grid-only", action="store_true")
    args = ap.parse_args()
    rows = read_table()
    if not args.grid_only:
        n = (add_reference(rows) if args.reference else 0) + add_rows(rows, args.rows, args.reviewed_on, args.credit)
        write_table(rows)
        print(f"added {n} row(s); {len(rows)} in the table")
    write_grid(rows)
    print(f"regenerated the grid in {os.path.relpath(README)}")


if __name__ == "__main__":
    main()
