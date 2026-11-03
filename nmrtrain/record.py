"""Predictions, reveals and the hand-in.

Blind by order: a `reveal` cell asks `revealed(...)` first, which refuses until a prediction for
that question exists. The hand-in records whether the prediction came first.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import os
import shutil
import subprocess
from importlib.metadata import distribution
from pathlib import Path

from . import __version__, portal
from ._safe import quietly
from .checks import CALLS, CONFIDENCE, HARSHER, LEFT, key_call, plain_call, quoted, show_format
from .data import RECORDS
from .io import ACID_WT_PCT, NAMES

FIGURE_DPI = 130
COMMIT_CHARS = 12
DIPEPTIDE_DOI = RECORDS["11223995"]["doi"]

_predictions: dict[str, dict] = {}
_reveals: dict[str, str] = {}


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _filled(value) -> bool:
    if value is ... or value is None or value == "":
        return False
    if isinstance(value, dict):
        return any(_filled(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    return True


def predict(question: str, prediction) -> None:
    """Record a prediction (timestamped), when something was filled in."""
    if not _filled(prediction):
        print("Fill in at least one prediction above (replace the ...), then run this cell again.")
        return
    _predictions[question] = {"prediction": prediction, "at": _now()}
    print(f"Prediction saved at {_predictions[question]['at']}. Now run the reveal.")


def revealed(question: str) -> bool:
    """True when the reveal may run. Otherwise prints one line and returns False."""
    if question not in _predictions:
        print("Make your prediction in the cell above first.")
        return False
    _reveals.setdefault(question, _now())
    return True


def predicted_before_reveal(question: str) -> bool:
    return question in _predictions and (question not in _reveals or _predictions[question]["at"] <= _reveals[question])


def _installed_commit() -> str | None:
    """The commit pip installed this package from (its direct_url.json), if it came from git."""
    info = json.loads(distribution("nmrtrain").read_text("direct_url.json") or "{}")
    return (info.get("vcs_info") or {}).get("commit_id")


def _checkout_commit() -> str | None:
    """HEAD of the git checkout this package is imported from, if there is one."""
    git = shutil.which("git")
    if git is None:
        return None
    out = subprocess.run(  # noqa: S603 (fixed arguments, no shell)
        [git, "rev-parse", "HEAD"], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5, check=False
    )
    return out.stdout.strip() if out.returncode == 0 else None


def pkg_commit() -> str:
    """The commit this package was installed from (pip's direct_url.json), or the checkout's HEAD."""
    sha = quietly(_installed_commit, None) or quietly(_checkout_commit, None)
    return sha[:COMMIT_CHARS] if sha else f"v{__version__}"


def handin(
    part: str,
    figures: dict | None = None,
    verdict: dict | None = None,
    numbers: dict | None = None,
    question: str | None = None,
    traps: int = 0,
    processing: str = "pdata",
) -> dict:
    """Save the figures (PNG) and the verdict (JSON) in handin/, then tick the part on Rakiura.

    figures: {"file_stem": fig}. numbers: at most 20 single values for the step.
    Nothing is submitted: run nt.portal.submit() yourself when you are ready.
    """
    out = Path(portal.state.handin_dir, part)
    out.mkdir(parents=True, exist_ok=True)
    saved = []
    for stem, fig in (figures or {}).items():
        path = out / f"{stem}.png"
        fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
        saved.append(path)
    record = {
        "part": part,
        "saved_at": _now(),
        "verdict": verdict or {},
        "predicted_before_reveal": predicted_before_reveal(question) if question else None,
        "traps_flagged": traps,
        "processing": processing,
        "pkg": f"nmrtrain {__version__} @ {pkg_commit()}",
        "ppm_scale": "instrument (not re-referenced to the acid peak)",
    }
    path = out / "verdict.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    saved.append(path)
    nums = {"traps_flagged": traps, "pkg_commit": pkg_commit(), "processing": processing}
    if question:
        nums["predicted_before_reveal"] = bool(record["predicted_before_reveal"])
    nums.update(numbers or {})
    portal.done(part, figures=list((figures or {}).values()), numbers=dict(list(nums.items())[: portal.MAX_NUMBERS]))
    portal.stage_file(json.dumps(record, indent=1, default=str), f"{part} verdict.json")
    print("Saved for your hand-in:")
    for p in saved:
        print(f"   {os.path.relpath(p)}")
    if portal.state.mode == "offline":
        print(
            "Offline mode: attach these files on your step page. "
            "When you are connected to Rakiura, they are added for you."
        )
    return record


def fill(value, default, name: str):
    """A member's answer, or a stand-in so the notebook keeps running (with one line saying so)."""
    if value is ... or value is None:
        print(f"To do: {name} is not filled in yet, so the notebook uses {default!r} for now.")
        return default
    return value


REPLICATION_COLUMNS = [
    "row_id",
    "dipeptide",
    "dipeptide_name",
    "acid_wt_pct",
    "acid_code",
    "nucleus",
    "time_points",
    "processing",
    "tool",
    "verdict",
    "main_product",
    "matches_published",
    "traps_flagged",
    "dataset_doi",
    "reviewed_on",
    "contributor",
]


def replication_row(
    sample: str,
    acid: str,
    entry: dict,
    time_points: list[str],
    matches: str = "unsure",
    traps: int = 0,
    processing: str = "pdata",
    nucleus: str = "1H",
) -> dict:
    """One row for the shared results table (see replication/README.md). Staff fill
    row_id and reviewed_on after review; the contributor is credited by name only on opt-in."""
    return {
        "row_id": "",
        "dipeptide": sample,
        "dipeptide_name": NAMES.get(sample, sample),
        "acid_wt_pct": ACID_WT_PCT.get(acid, ""),
        "acid_code": acid,
        "nucleus": nucleus,
        "time_points": ";".join(time_points),
        "processing": processing,
        "tool": f"nmrtrain {pkg_commit()}",
        "verdict": key_call(entry.get("call", "")) or "blank",
        "main_product": str(entry.get("product_guess", "")).strip(),
        "matches_published": matches,
        "traps_flagged": traps,
        "dataset_doi": DIPEPTIDE_DOI,
        "reviewed_on": "",
        "contributor": "Rakiura member",
    }


def save_rows(rows: list[dict], part: str, name: str = "replication_rows.csv") -> str:
    """Save shared-results-table rows as a CSV in the part's hand-in folder."""
    out = Path(portal.state.handin_dir, part)
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REPLICATION_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"   {os.path.relpath(path)}")
    return str(path)


# ---------------------------------------------------------------------------------------------
# recording a verdict one field at a time, next to the plot that answers it

_LIST_WORDS = {"lost_ppm": ("lost peak", "lost"), "new_ppm": ("new peak", "new"), "kept_ppm": ("kept peak", "kept")}


def _ppm_list(values) -> str:
    v = [f"{p:g}" for p in values]
    if not v:
        return "none"
    return v[0] if len(v) == 1 else ", ".join(v[:-1]) + " and " + v[-1]


def _show_markdown(markdown: str) -> bool:
    """Display markdown when running in a notebook (not a terminal IPython). True if shown."""
    from IPython import get_ipython  # IPython is only there in a notebook

    shell = get_ipython()
    if shell is None or type(shell).__name__ == "TerminalInteractiveShell":
        return False
    from IPython.display import Markdown, display

    display(Markdown(markdown))
    return True


def _say(markdown: str, plain: str) -> None:
    """One line for the member: bold in a notebook, plain text anywhere else."""
    if not quietly(lambda: _show_markdown(markdown), False):
        print(plain)


def _confirm(name: str, value, saved: bool, rest: str) -> None:
    head = "Saved" if saved else "Not saved yet"
    shown = f"{name} = {'...' if value is ... else repr(value)}"
    _say(f"**{head}** `{shown}`{': ' + rest if rest else ''}", f"{head} {shown}{': ' + rest if rest else ''}")


# What each verdict field accepts, and how a member reads its name.
_ALLOWED = {"call": CALLS, "confidence": CONFIDENCE, "left": LEFT, "harsher": HARSHER}
_FIELD_WORDS = {
    "call": "your decision",
    "confidence": "the confidence",
    "left": "how much is left",
    "harsher": "which acid was harsher",
    "product_guess": "the product guess",
    "note": "the note",
}
_SAME_PEAK_PPM = 0.05  # a picked peak this close to one the member wrote is the same peak


def _write_down_list(name: str, value, who: str, field: str, suggestion: list | None) -> None:
    """Confirm a ppm list (lost, new or kept peaks), comparing it with what the peak picker found."""
    word, group = _LIST_WORDS[field]
    if not isinstance(value, (list, tuple)):
        _confirm(name, value, False, f"write the {word}s as numbers in square brackets, like [2.08, 4.94].")
        return
    bad = [p for p in value if not isinstance(p, (int, float))]
    if bad:
        _confirm(
            name, value, False, f"write each {word} as a number without quotes, like [2.08, 4.94] (found {bad[0]!r})."
        )
        return
    sugg = [round(float(p), 2) for p in (suggestion or [])]
    if not value:
        rest = f"no {word}s for {who}. If there were none, that is your answer and you can move on."
        if sugg:
            rest += f" The peak picker listed these as {group}: {_ppm_list(sugg)}. Copy the ones you agree with."
        _confirm(name, value, True, rest)
        return
    n = len(value)
    rest = f"{n} {word}{'s' if n != 1 else ''} for {who}, at {_ppm_list(value)} ppm."
    extra = [p for p in sugg if not any(abs(p - q) <= _SAME_PEAK_PPM for q in value)]
    if extra:
        rest += f" The peak picker also listed {_ppm_list(extra)} as {group}; check whether you agree."
    _confirm(name, value, True, rest)


def _write_down_blank(name: str, value, who: str, field: str) -> None:
    """Confirm an empty text field: fine for a note, a reminder for anything else."""
    if field == "note":
        _confirm(name, value, True, f"no note for {who}. That is fine.")
    elif field == "product_guess":
        _confirm(
            name,
            value,
            False,
            f'write what you think {who} turned into, "none" if nothing new '
            'formed, or leave "" if you have no idea yet.',
        )
    else:
        allowed = _ALLOWED.get(field)
        fair = ' ("unsure" is a fair answer)' if "unsure" in allowed else ""
        words = _FIELD_WORDS.get(field, field)
        _confirm(name, value, False, f"write {words} for {who}: one of {quoted(allowed)}{fair}.")


def _write_down_text(name: str, value, who: str, field: str) -> None:
    """Confirm a text field (decision, confidence, how much is left, product guess, note...)."""
    text = str(value or "").strip()
    if not text:
        _write_down_blank(name, value, who, field)
        return
    if field == "call":
        text = plain_call(text)
    allowed = _ALLOWED.get(field)
    if allowed and text.lower() not in allowed:
        _confirm(name, value, False, f"write one of {quoted(allowed)}.")
        return
    words = _FIELD_WORDS.get(field, field)
    _confirm(name, value, True, f"{words} for {who}." if field != "note" else f"your note for {who}.")


def write_down(name: str, value, who: str, field: str, suggestion: list | None = None) -> None:
    """Record one field of a verdict and say in one line what was saved, by its variable name.

    field: "lost_ppm", "new_ppm", "kept_ppm", "left", "call", "confidence", "harsher", "product_guess"
    or "note".
    suggestion: for a ppm list, what the peak picker found; it is shown to compare with, never copied
    into the answer. Returns None, so a cell that ends with it prints only the confirmation.
    """
    if field in _LIST_WORDS:
        _write_down_list(name, value, who, field, suggestion)
    else:
        _write_down_text(name, value, who, field)


_TABLE_COLUMNS = [
    ("call", "decision"),
    ("lost_ppm", "lost peaks (ppm)"),
    ("new_ppm", "new peaks (ppm)"),
    ("kept_ppm", "kept peaks (ppm)"),
    ("left", "how much is left"),
    ("product_guess", "product guess"),
    ("confidence", "confidence"),
    ("note", "note"),
]


def _cell(value) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(f"{p:g}" if isinstance(p, (int, float)) else repr(p) for p in value) or "none"
    text = str(value if value is not None else "").strip()
    return text.replace("|", "/").replace("\n", " ") or "(empty)"


def verdict_table(rows: dict, examples: dict | None = None) -> str:
    """A Markdown table, one row per molecule, columns as on the hand-in."""
    present = [
        (k, t) for k, t in _TABLE_COLUMNS if any(k in e for e in list(rows.values()) + list((examples or {}).values()))
    ]
    lines = ["| | " + " | ".join(t for _, t in present) + " |", "|---" * (len(present) + 1) + "|"]
    for label, entry in list((examples or {}).items()) + list(rows.items()):
        lines.append(f"| **{label}** | " + " | ".join(_cell(entry.get(k, "")) for k, _ in present) + " |")
    return "\n".join(lines)


def build_verdict(
    rows: dict, names: dict | None = None, examples: dict | None = None, check: list | None = None, **extra
) -> dict:
    """Assemble the verdict from the fields recorded above, show it as a table, and return it in the
    hand-in format: {case: {...}, **extra}. rows: {case: entry}. names: {case: row label}.
    examples: {row label: entry}, shown in the table for comparison and left out of the verdict.
    check: the cases whose format is checked (default: all rows)."""
    names = names or {}
    labelled = {names.get(c, c): e for c, e in rows.items()}
    table = verdict_table(labelled, examples)
    _say(table, table)
    show_format(rows, check or list(rows), names)
    verdict = {c: dict(e) for c, e in rows.items()}
    verdict.update(extra)
    return verdict


def saved(name: str, value, what: str) -> None:
    """One-line confirmation for a setting the member chose (not a verdict field)."""
    if value is ... or value is None:
        _confirm(name, value, False, f"{what}. The cell uses a stand-in until you fill it in.")
    elif isinstance(value, (list, str)) and not value:
        _confirm(name, value, False, f"{what}. Still empty: fill it in above.")
    else:
        _confirm(name, value, True, f"{what}.")
