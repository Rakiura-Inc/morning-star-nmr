"""Predictions, reveals and the hand-in.

Blind by order: a `reveal` cell asks `revealed(...)` first, which refuses until a prediction for
that question exists. The hand-in records whether the prediction came first.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess

from . import __version__, portal

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
    return question in _predictions and (question not in _reveals
                                         or _predictions[question]["at"] <= _reveals[question])


def pkg_commit() -> str:
    """The commit this package was installed from (pip's direct_url.json), or the checkout's HEAD."""
    try:
        from importlib.metadata import distribution
        info = json.loads(distribution("nmrtrain").read_text("direct_url.json") or "{}")
        sha = (info.get("vcs_info") or {}).get("commit_id")
        if sha:
            return sha[:12]
    except Exception:
        pass
    try:
        here = os.path.dirname(__file__)
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()[:12]
    except Exception:
        pass
    return f"v{__version__}"


def handin(part: str, figures: dict | None = None, verdict: dict | None = None, numbers: dict | None = None,
           question: str | None = None, traps: int = 0, processing: str = "pdata") -> dict:
    """Save the figures (PNG) and the verdict (JSON) in handin/, then tick the part on Rakiura.

    figures: {"file_stem": fig}. numbers: at most 20 single values for the step.
    Nothing is submitted: run nt.portal.submit() yourself when you are ready.
    """
    out = os.path.join(portal.state.handin_dir, part)
    os.makedirs(out, exist_ok=True)
    saved = []
    for stem, fig in (figures or {}).items():
        path = os.path.join(out, f"{stem}.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
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
    path = os.path.join(out, "verdict.json")
    with open(path, "w") as fh:
        json.dump(record, fh, indent=2, default=str)
    saved.append(path)
    nums = {"traps_flagged": traps, "pkg_commit": pkg_commit(), "processing": processing}
    if question:
        nums["predicted_before_reveal"] = bool(record["predicted_before_reveal"])
    nums.update(numbers or {})
    portal.done(part, figures=list((figures or {}).values()), numbers=dict(list(nums.items())[:20]))
    portal.stage_file(json.dumps(record, indent=1, default=str), f"{part} verdict.json")
    print("Saved for your hand-in:")
    for p in saved:
        print(f"   {os.path.relpath(p)}")
    if portal.state.mode == "offline":
        print("Offline mode: attach these files on your step page. When you are connected to Rakiura, they are added for you.")
    return record


def fill(value, default, name: str):
    """A member's answer, or a stand-in so the notebook keeps running (with one line saying so)."""
    if value is ... or value is None:
        print(f"[to do] {name} is not filled in yet, so the notebook uses {default!r} for now.")
        return default
    return value


REPLICATION_COLUMNS = ["row_id", "dipeptide", "dipeptide_name", "acid_wt_pct", "acid_code", "nucleus",
                       "time_points", "processing", "tool", "verdict", "main_product", "matches_published",
                       "traps_flagged", "dataset_doi", "reviewed_on", "contributor"]


def replication_row(sample: str, acid: str, entry: dict, time_points: list[str], matches: str = "unsure",
                    traps: int = 0, processing: str = "pdata", nucleus: str = "1H") -> dict:
    """One row for the community replication table (see replication/README.md). Staff fill
    row_id and reviewed_on after review; the contributor is credited by name only on opt-in."""
    from .io import NAMES
    return {"row_id": "", "dipeptide": sample, "dipeptide_name": NAMES.get(sample, sample),
            "acid_wt_pct": {"K": 98, "H": 81}.get(acid, ""), "acid_code": acid, "nucleus": nucleus,
            "time_points": ";".join(time_points), "processing": processing,
            "tool": f"nmrtrain {pkg_commit()}", "verdict": str(entry.get("call", "")).strip().lower() or "blank",
            "main_product": str(entry.get("product_guess", "")).strip(), "matches_published": matches,
            "traps_flagged": traps, "dataset_doi": "10.5281/zenodo.11223995", "reviewed_on": "",
            "contributor": "Rakiura member"}


def save_rows(rows: list[dict], part: str, name: str = "replication_rows.csv") -> str:
    import csv
    out = os.path.join(portal.state.handin_dir, part)
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, name)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REPLICATION_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"   {os.path.relpath(path)}")
    return path
