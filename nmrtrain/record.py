"""Predictions, reveals and the hand-in.

Blind by order: a `reveal` cell asks `revealed(...)` first, which refuses until a prediction for
that question exists. The hand-in records whether the prediction came first.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import shutil
import subprocess
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from . import __version__, portal
from .checks import CALLS, CONFIDENCE, HARSHER, LEFT, key_call, plain_call, quoted, show_format
from .data import RECORDS
from .names import ACID_WT_PCT, sample_name
from .peaks import SAME_PEAK_PPM

FIGURE_DPI = 130
COMMIT_CHARS = 12
DIPEPTIDE_DOI = RECORDS["11223995"]["doi"]

_predictions: dict[str, dict] = {}
_reveals: dict[str, str] = {}


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


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
        print("Make your prediction first: fill in the prediction cell above and run it, then run this cell again.")
        return False
    _reveals.setdefault(question, _now())
    return True


def has_prediction(question: str) -> bool:
    """True once a prediction for the question is saved. Silent, for a second reveal cell under one
    that already told the member what to do."""
    return question in _predictions


def predicted_before_reveal(question: str) -> bool:
    """True when a prediction for the question was saved before its reveal first ran."""
    if question not in _predictions:
        return False
    if question not in _reveals:
        return True
    return _predictions[question]["at"] <= _reveals[question]


def _installed_commit() -> str | None:
    """The commit pip installed this package from (its direct_url.json), if it came from git."""
    try:
        direct_url = distribution("nmrtrain").read_text("direct_url.json")
    except PackageNotFoundError:
        return None
    if not direct_url:
        return None  # installed from a folder or a wheel, not from git
    vcs_info = json.loads(direct_url).get("vcs_info") or {}
    return vcs_info.get("commit_id")


def _checkout_commit() -> str | None:
    """HEAD of the git checkout this package is imported from, if there is one."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        out = subprocess.run(  # noqa: S603 (fixed arguments, no shell)
            [git, "rev-parse", "HEAD"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip()


def pkg_commit() -> str:
    """The commit this package was installed from (pip's direct_url.json), or the checkout's HEAD."""
    sha = _installed_commit() or _checkout_commit()
    if sha:
        return sha[:COMMIT_CHARS]
    return f"v{__version__}"


def handin(  # noqa: PLR0913 (one argument for each thing a hand-in holds)
    part: str,
    *,
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
    portal.stage_file(json.dumps(record, indent=1, default=str), f"{part} verdict.json", part=part)
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
    *,
    matches: str = "unsure",
    traps: int = 0,
) -> dict:
    """One row for the shared results table (see replication/README.md), from the dipeptide
    notebook, which reads the instrument's 1H spectra. Staff fill row_id and reviewed_on after
    review; the contributor is credited by name only on opt-in."""
    return {
        "row_id": "",
        "dipeptide": sample,
        "dipeptide_name": sample_name(sample),
        "acid_wt_pct": ACID_WT_PCT.get(acid, ""),
        "acid_code": acid,
        "nucleus": "1H",
        "time_points": ";".join(time_points),
        "processing": "pdata",
        "tool": f"nmrtrain {pkg_commit()}",
        "verdict": key_call(entry.get("call", "")) or "blank",
        "main_product": str(entry.get("product_guess", "")).strip(),
        "matches_published": matches,
        "traps_flagged": traps,
        "dataset_doi": DIPEPTIDE_DOI,
        "reviewed_on": "",
        "contributor": "Rakiura member",
    }


def save_rows(rows: list[dict], part: str, name: str = "replication_rows.csv") -> None:
    """Save shared-results-table rows as a CSV in the part's hand-in folder, and print its path."""
    out = Path(portal.state.handin_dir, part)
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPLICATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"   {os.path.relpath(path)}")


# ---------------------------------------------------------------------------------------------
# recording a verdict one field at a time, next to the plot that answers it

_LIST_WORDS = {"lost_ppm": ("lost peak", "lost"), "new_ppm": ("new peak", "new"), "kept_ppm": ("kept peak", "kept")}


def _ppm_list(values) -> str:
    """'1.99, 2.08 and 4.92' (or 'none')."""
    words = [f"{ppm:g}" for ppm in values]
    if not words:
        return "none"
    if len(words) == 1:
        return words[0]
    return ", ".join(words[:-1]) + " and " + words[-1]


def _in_a_notebook() -> bool:
    """True inside Jupyter or Colab, where Markdown can be displayed; False in a plain Python run."""
    try:
        from IPython import get_ipython  # IPython is there wherever a notebook runs
    except ImportError:
        return False
    shell = get_ipython()
    return shell is not None and type(shell).__name__ != "TerminalInteractiveShell"


def _say(markdown: str, plain: str) -> None:
    """One line for the member: bold in a notebook, plain text anywhere else."""
    if _in_a_notebook():
        from IPython.display import Markdown, display

        display(Markdown(markdown))
    else:
        print(plain)


def _confirm(name: str, value, saved: bool, rest: str) -> None:
    """One line saying whether an answer was saved, by its variable name, and what to do next."""
    head = "Saved" if saved else "Not saved yet"
    shown = f"{name} = ..." if value is ... else f"{name} = {value!r}"
    if rest:
        _say(f"**{head}** `{shown}`: {rest}", f"{head} {shown}: {rest}")
    else:
        _say(f"**{head}** `{shown}`", f"{head} {shown}")


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
_SAME_PEAK_PPM = SAME_PEAK_PPM  # a picked peak this close to one the member wrote is the same peak


def _write_down_list(name: str, value, who: str, field: str, *, suggestion: list | None) -> None:
    """Confirm a ppm list (lost, new or kept peaks), comparing it with what the peak picker found."""
    word, group = _LIST_WORDS[field]
    if not isinstance(value, (list, tuple)):
        _confirm(name, value, False, f"write the {word}s as numbers in square brackets, like [2.08, 4.94].")
        return
    not_numbers = [ppm for ppm in value if not isinstance(ppm, (int, float))]
    if not_numbers:
        _confirm(
            name,
            value,
            False,
            f"write each {word} as a number without quotes, like [2.08, 4.94] (found {not_numbers[0]!r}).",
        )
        return
    picked = [round(float(ppm), 2) for ppm in suggestion or []]
    if not value:
        rest = f"no {word}s for {who}. If there were none, that is your answer and you can move on."
        if picked:
            rest += f" The peak picker listed these as {group}: {_ppm_list(picked)}. Copy the ones you agree with."
        _confirm(name, value, True, rest)
        return
    if len(value) == 1:
        rest = f"1 {word} for {who}, at {_ppm_list(value)} ppm."
    else:
        rest = f"{len(value)} {word}s for {who}, at {_ppm_list(value)} ppm."
    extra = []
    for ppm in picked:
        if not any(abs(ppm - written) <= _SAME_PEAK_PPM for written in value):
            extra.append(ppm)
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
        allowed = _ALLOWED[field]
        words = _FIELD_WORDS.get(field, field)
        rest = f"write {words} for {who}: one of {quoted(allowed)}"
        if "unsure" in allowed:
            rest += ' ("unsure" is a fair answer)'
        _confirm(name, value, False, rest + ".")


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
    if field == "note":
        _confirm(name, value, True, f"your note for {who}.")
    else:
        _confirm(name, value, True, f"{_FIELD_WORDS.get(field, field)} for {who}.")


def write_down(name: str, value, who: str, field: str, *, suggestion: list | None = None) -> None:
    """Record one field of a verdict and say in one line what was saved, by its variable name.

    field: "lost_ppm", "new_ppm", "kept_ppm", "left", "call", "confidence", "harsher", "product_guess"
    or "note".
    suggestion: for a ppm list, what the peak picker found; it is shown to compare with, never copied
    into the answer. Returns None, so a cell that ends with it prints only the confirmation.
    """
    if field in _LIST_WORDS:
        _write_down_list(name, value, who, field, suggestion=suggestion)
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


def _table_cell(value) -> str:
    """One answer as table text: a peak list as '1.99, 2.08', an empty one as 'none'."""
    if isinstance(value, (list, tuple)):
        words = []
        for item in value:
            if isinstance(item, (int, float)):
                words.append(f"{item:g}")
            else:
                words.append(repr(item))  # a typed word, shown in quotes so it stands out
        return ", ".join(words) or "none"
    if value is None:
        value = ""
    text = str(value).strip().replace("|", "/").replace("\n", " ")
    return text or "(empty)"


def verdict_table(rows: dict, examples: dict | None = None) -> str:
    """A Markdown table, one row per molecule, columns as on the hand-in. The examples come first."""
    entries = {**(examples or {}), **rows}
    columns = []
    for field, title in _TABLE_COLUMNS:
        if any(field in entry for entry in entries.values()):
            columns.append((field, title))
    lines = ["| | " + " | ".join(title for _, title in columns) + " |", "|---" * (len(columns) + 1) + "|"]
    for label, entry in entries.items():
        cells = [_table_cell(entry.get(field, "")) for field, _ in columns]
        lines.append(f"| **{label}** | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_verdict(
    rows: dict, names: dict | None = None, examples: dict | None = None, check: list | None = None, **extra
) -> dict:
    """Assemble the verdict from the fields recorded above, show it as a table, and return it in the
    hand-in format: {case: {...}, **extra}. rows: {case: entry}. names: {case: row label}.
    examples: {row label: entry}, shown in the table for comparison and left out of the verdict.
    check: the cases whose format is checked (default: all rows)."""
    names = names or {}
    labelled = {names.get(case, case): entry for case, entry in rows.items()}
    table = verdict_table(labelled, examples)
    _say(table, table)
    show_format(rows, check or list(rows), names)
    verdict = {case: dict(entry) for case, entry in rows.items()}
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
