"""Trap checks and comparisons with published calls. Feedback only: never a score, never "correct" or "wrong".

Every check returns `Feedback` lines. A trap that fires never stops the notebook; it prints one
line and is counted in the hand-in (`traps_flagged`) so the reviewer sees what the member was told.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

import numpy as np

from . import peaks as _peaks
from .io import Spectrum, time_label

# The calls a member writes, in plain words. The answer keys and the replication table keep the
# older words ("degrades", "side chain modified"); both spellings are accepted everywhere.
CALLS = ("survives", "breaks down", "side chain changed", "unsure")
KEY_CALLS = ("survives", "degrades", "side chain modified", "unsure")
_CALL_WORDS = {"degrades": "breaks down", "degraded": "breaks down", "broke down": "breaks down",
               "breaks": "breaks down", "break down": "breaks down",
               "side chain modified": "side chain changed", "side-chain changed": "side chain changed",
               "side chain change": "side chain changed"}
_KEY_WORD = {"breaks down": "degrades", "side chain changed": "side chain modified"}
CONFIDENCE = ("low", "medium", "high")

# Where the acid's own big signal sits on the instrument's ppm scale in these datasets.
# 98% (K): 11.43 to 11.58 ppm; a few early spectra sit near 11.08 (referenced differently).
# 81% (H): 11.66 to 12.08 ppm, depending on the sample.
ACID_WINDOW = {"K": (11.5, 0.5), "H": (11.85, 0.4), None: (11.6, 0.65)}
ACID_ZONE = _peaks.ACID_AREA       # never cite a peak in here as the sample's own
EXCHANGEABLE = (6.3, 9.6)         # NH and NH3+ signals of non-aromatic samples sit here in this acid
AROMATIC = {"FF", "YY", "WW", "HH", "PHE", "TYR", "TRP", "HIS"}


def plain_call(call) -> str:
    """A call in the member's words: "degrades" reads as "breaks down", and so on."""
    c = str(call or "").strip().lower()
    return _CALL_WORDS.get(c, c)


def key_call(call) -> str:
    """A call in the answer keys' words (used by the replication table)."""
    c = plain_call(call)
    return _KEY_WORD.get(c, c)


# What each kind of line starts with when printed. The kind itself stays internal.
PREFIX = {"agrees": "Yes.", "look again": "Look again.", "to do": "To do:", "tip": "Tip:", "note": "Note:",
          "trap": "Trap:", "ok": "OK:", "open": ""}


@dataclass
class Feedback:
    kind: str      # agrees | look again | open | to do | tip | note | trap | ok
    text: str

    def __str__(self) -> str:
        lead = PREFIX.get(self.kind, "")
        return f"{lead} {self.text}" if lead else self.text


class Report(list):
    """A list of Feedback lines that prints nicely."""

    def show(self, title: str | None = None) -> "Report":
        if title:
            print(title)
        for line in self:
            print(f"  {line}")
        if not self:
            print("  nothing to flag")
        return self

    def count(self, kind: str) -> int:  # type: ignore[override]
        return sum(1 for f in self if f.kind == kind)

    def __repr__(self) -> str:
        return "\n".join(str(f) for f in self) or "(no feedback)"


# ---------------------------------------------------------------------------------------------
# trap checks


def acid_ppm(s: Spectrum) -> float:
    """Position of the tallest peak in 10 to 13 ppm (the acid), or overall if nothing is there."""
    x, y = s.region(*ACID_ZONE)
    if y.size and y.max() > 0.2 * np.max(s.y):
        return float(x[int(np.argmax(y))])
    return _peaks.tallest_ppm(s)


def check_axis(s: Spectrum) -> Feedback:
    """Is the ppm axis the right way round? 1H: the tallest peak (the acid) must sit near 11.5 ppm.
    13C: the tallest peak of these molecules sits in the aliphatic band (10 to 60 ppm)."""
    p = _peaks.tallest_ppm(s)
    mirror = float(s.ppm.max() + s.ppm.min()) - p
    if s.nucleus == "13C":
        if 5 <= p <= 65:
            return Feedback("ok", f"{s.label}: tallest peak at {p:.1f} ppm, in the aliphatic band. The axis is the right way round.")
        if 5 <= mirror <= 65:
            return Feedback("trap", f"{s.label}: the tallest peak is at {p:.1f} ppm, the mirror image of {mirror:.1f}. "
                                    "The ppm axis is probably reversed.")
        return Feedback("look again", f"{s.label}: the tallest peak is at {p:.1f} ppm. Check the axis.")
    center, half = ACID_WINDOW.get(s.acid, ACID_WINDOW[None])
    pct = {"K": "98%", "H": "81%"}.get(s.acid, "this")
    if abs(p - center) <= half:
        return Feedback("ok", f"{s.label}: acid peak at {p:.3f} ppm. The axis is the right way round.")
    if abs(mirror - center) <= half:
        return Feedback("trap", f"{s.label}: the acid peak is at {p:.2f} ppm here. In {pct} acid it sits near "
                                f"{center:.1f} ppm, so the ppm axis is probably reversed. Use nt.process.reverse "
                                "or load the processed spectrum.")
    return Feedback("look again", f"{s.label}: the tallest peak is at {p:.2f} ppm, not near {center:.1f}. "
                                  "Check the axis and which spectrum this is.")


def check_order(series: list[Spectrum], time_order: list[str] | None = None) -> Feedback:
    """Time labels and the instrument's acquisition dates must both increase up the stack."""
    from .data import RECORDS
    order = time_order or [t for r in RECORDS.values() for t in r["time_order"]]
    for a, b in zip(series, series[1:]):
        if a.time in order and b.time in order and order.index(a.time) > order.index(b.time):
            return Feedback("trap", f"Your stack is not in time order: {a.time_label} comes before {b.time_label}. "
                                    "Put the spectra in time order before comparing.")
        if a.acquired and b.acquired and a.acquired > b.acquired:
            return Feedback("trap", f"Your stack is not in time order: {a.time_label} was recorded after "
                                    f"{b.time_label}. Put the spectra in time order before comparing.")
    return Feedback("ok", "The labels and the acquisition dates are both in time order.")


def check_drift(series: list[Spectrum], limit: float = 0.2) -> Feedback:
    """How far the acid signal moves across the series."""
    pos = [acid_ppm(s) for s in series]
    moved = max(pos) - min(pos)
    if moved > limit:
        return Feedback("trap", f"The acid peak moved by {moved:.2f} ppm across this series. Some drift is "
                                "expected as the solution changes, but this much shifts every other peak too. "
                                "Align on it before reading other shifts, and say in your hand-in that you did.")
    return Feedback("ok", f"The acid peak moves by {moved:.2f} ppm across the series, which is small. "
                          "Keep the instrument's ppm scale.")


def check_normalisation(norm: tuple | None, acid: str | None = "K") -> Feedback:
    """Scaling to the whole spectrum (or a region that holds the acid) hides the sample's peaks."""
    center, _ = ACID_WINDOW.get(acid, ACID_WINDOW[None])
    if norm is None or (min(norm) <= center <= max(norm)):
        return Feedback("trap", "Your traces are scaled to the acid peak, which hides small changes. "
                                "Scale within 1 to 6.5 ppm, or within the region you are reading.")
    return Feedback("ok", f"Scaled within {min(norm)} to {max(norm)} ppm.")


def check_broad_early(series: list[Spectrum], lo: float = 1.0, hi: float = 6.5, ratio: float = 1.5) -> Feedback:
    """Is the first spectrum's main peak much broader than later ones?"""
    first = series[0]
    center = _peaks.tallest_ppm(first, lo, hi)
    widths = [_peaks.linewidth_hz(s, center)[1] for s in series]
    later = statistics.median(widths[1:]) if len(widths) > 1 else widths[0]
    if later > 0 and widths[0] > ratio * later:
        return Feedback("note", f"The {first.time_label} peaks are broader than later ones ({widths[0]:.1f} Hz vs "
                                f"{later:.1f} Hz near {center:.2f} ppm). The peaks sharpen after day 1, most likely because "
                                "the hydrogens on nitrogen swap with the acid's deuterium and stop splitting the "
                                "peaks next to them. It is not breakdown.")
    return Feedback("ok", f"Line widths near {center:.2f} ppm: {widths[0]:.1f} Hz first, {later:.1f} Hz later.")


def check_signal_loss(first: Spectrum, last: Spectrum, lo: float = 1.0, hi: float = 6.5,
                      min_new_height: float = 0.05) -> Feedback:
    """Most of the sample's signal gone, relative to the acid, with nothing new: maybe it came out of solution."""
    def amount(s):
        return _peaks.area(s, lo, hi) / max(_peaks.area(s, *ACID_ZONE), 1e-12)

    kept = amount(last) / amount(first) if amount(first) > 0 else 1.0
    new = _peaks.compare(_peaks.pick(first, lo, hi), [p for p in _peaks.pick(last, lo, hi)
                                                      if p["height"] >= min_new_height])["new"]
    if kept < 0.5 and not new:
        return Feedback("trap", "Most of the signal disappeared and nothing new appeared. That can mean the sample "
                                "came out of solution rather than reacted. Say so in your hand-in, or answer unsure.")
    return Feedback("ok", f"Signal relative to the acid: {kept:.0%} of the first spectrum's"
                          + (f", with {len(new)} new peak(s)." if new else "."))


def run_traps(series: list[Spectrum], norm: tuple | None = (1.0, 6.5), lo: float = 1.0, hi: float = 6.5,
              title: str | None = None, quiet: bool = False) -> Report:
    """All the trap checks that apply to one stacked series. Prints them; returns the Report."""
    rep = Report()
    if series[0].nucleus == "1H":
        rep += [check_axis(s) for s in series]
        rep.append(check_order(series))
        rep.append(check_drift(series))
        rep.append(check_normalisation(norm, series[0].acid))
        rep.append(check_broad_early(series, lo, hi))
        rep.append(check_signal_loss(series[0], series[-1], lo, hi))
    else:
        rep += [check_axis(s) for s in series]
        rep.append(check_order(series))
    if not quiet:
        flagged = Report(f for f in rep if f.kind != "ok")
        ok = len(rep) - len(flagged)
        acid = {"K": " in 98% acid", "H": " in 81% acid"}.get(series[0].acid, "")
        flagged.show(title or f"Checks on {series[0].sample_name}{acid}: {ok} passed, {len(flagged)} flagged")
    return rep


def traps_flagged(*reports: Report) -> int:
    return sum(r.count("trap") for r in reports)


# ---------------------------------------------------------------------------------------------
# predictions and verdicts


def _number(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


LOOK_NEXT = "Now look at the spectra below and find where it really sits."


def check_prediction(pred: dict, key: dict) -> Report:
    """Feedback on a prediction made before the member has seen the data.

    key: {field: spec}. A spec is one of:
      {"label", "answer", "why"}                       a count that follows from the structure
      {"label", "typical", "typical_text", "water"}    a position, judged only against the typical
                                                       range the notebook teaches (never this dataset)
      {"label", "later"}                               a call the member checks later in the notebook
    """
    rep = Report()
    for name, k in key.items():
        v = pred.get(name)
        label = k.get("label", name)
        if v is None or v is ... or v == "":
            rep.append(Feedback("to do", f"{label}: no prediction entered. You can still find it in the spectra below."))
        elif "later" in k:
            rep.append(Feedback("open", f"{label}: you said {v!r}. {k['later']}"))
        elif "answer" in k:
            why = k.get("why", "")
            if v == k["answer"]:
                rep.append(Feedback("agrees", f"{label}: {v}. {why}"))
            else:
                rep.append(Feedback("look again", f"{label}: you said {v}; the structure gives {k['answer']}. {why} "
                                                  "Open hint 2 above if this is still unclear."))
        else:
            x = _number(v)
            if x is None:
                rep.append(Feedback("to do", f"{label}: write a number in ppm, for example 2.0."))
                continue
            lo, hi = k["typical"]
            near = k.get("typical_text", f"between {lo} and {hi} ppm")
            water = k.get("water")
            if lo <= x <= hi:
                rep.append(Feedback("agrees", f"{label}: {x:g} ppm fits {near}. {LOOK_NEXT}"))
            elif water and water[0] <= x <= water[1]:
                rep.append(Feedback("look again", f"{label}: {x:g} ppm is closer to where it sits in water. The acid "
                                                  "pulls electrons away from the hydrogens, so signals sit higher "
                                                  f"in acid; the table above gives {near}. {LOOK_NEXT}"))
            else:
                rep.append(Feedback("look again", f"{label}: you said {x:g} ppm; the table above gives {near}. "
                                                  f"{LOOK_NEXT}"))
    return rep


def check_reading(reading: dict, key: dict, prediction: dict | None = None) -> Report:
    """Feedback on positions the member read off the spectra (after the plots). Here the ranges
    measured in this dataset are used: key {field: {"label", "band"}}."""
    rep = Report()
    for name, k in key.items():
        if "band" not in k:
            continue
        label = k.get("label", name)
        x = _number(reading.get(name))
        if x is None:
            rep.append(Feedback("to do", f"{label}: read its position off the plot or peak list above and "
                                         "write it as a number."))
            continue
        lo, hi = k["band"]
        before = (prediction or {}).get(name)
        was = f" You predicted {before} ppm." if _number(before) is not None else ""
        if lo <= x <= hi:
            rep.append(Feedback("agrees", f"{label}: {x:g} ppm. In this data it sits at {lo} to {hi} ppm.{was}"))
        else:
            rep.append(Feedback("look again", f"{label}: {x:g} ppm. Check which peak you read: in this data it sits "
                                              f"at {lo} to {hi} ppm.{was}"))
    return rep


FIELD_WORDS = {"call": "decision", "lost_ppm": "lost peaks", "new_ppm": "new peaks", "kept_ppm": "kept peaks",
               "left": "how much is left", "product_guess": "product guess", "confidence": "confidence"}
LEFT = ("little or none", "no clear loss", "unsure")
HARSHER = ("98%", "81%", "same", "unsure")


def quoted(words) -> str:
    """'"a", "b" or "c"', for listing the allowed answers."""
    w = [f'"{x}"' for x in words]
    return ", ".join(w[:-1]) + " or " + w[-1]


def verdict_problems(verdict: dict, cases: list[str], names: dict | None = None) -> list[str]:
    """Things to fix before the check can read a verdict (format only, never right or wrong)."""
    issues = []
    for case in cases:
        who = (names or {}).get(case, case)
        entry = verdict.get(case, {}) or {}
        call = plain_call(entry.get("call", ""))
        if call and call not in CALLS:
            issues.append(f'The decision for {who} is "{entry.get("call")}": write one of {quoted(CALLS)}.')
        conf = str(entry.get("confidence", "")).strip().lower()
        if conf and conf not in CONFIDENCE:
            issues.append(f'The confidence for {who} is "{entry.get("confidence")}": write one of {quoted(CONFIDENCE)}.')
        left = str(entry.get("left", "")).strip().lower()
        if left and left not in LEFT:
            issues.append(f'How much is left for {who} is "{entry.get("left")}": write one of {quoted(LEFT)}.')
        for k in ("lost_ppm", "new_ppm", "kept_ppm"):
            for p in entry.get(k, []) or []:
                if not isinstance(p, (int, float)):
                    issues.append(f"The {FIELD_WORDS[k]} for {who} include {p!r}: write numbers without quotes, "
                                  "like [2.08, 4.94].")
    return issues


def _blank(v) -> bool:
    return not v.strip() if isinstance(v, str) else not v


def verdict_notes(verdict: dict, cases: list[str], names: dict | None = None) -> list[str]:
    """One friendly line per molecule naming the fields still empty. Empty is allowed; nothing here
    blocks the hand-in."""
    notes = []
    for case in cases:
        who = (names or {}).get(case, case)
        entry = verdict.get(case, {}) or {}
        empty = [FIELD_WORDS[k] for k in FIELD_WORDS if k in entry and _blank(entry[k])]
        if empty:
            notes.append(f"{who}: still empty: {', '.join(empty)}. An empty peak list is fine if there were "
                         'none, and "unsure" is a fair answer.')
    return notes


def show_format(verdict: dict, cases: list[str], names: dict | None = None) -> list[str]:
    """Print the format problems and the notes on empty fields. Returns the problems."""
    problems = verdict_problems(verdict, cases, names)
    for line in problems + verdict_notes(verdict, cases, names):
        print(f"  {line}")
    if not problems:
        print("Nothing here blocks your hand-in. Change any answer above and run the cells again to update it.")
    return problems


def _dist(s: dict, p: float) -> float:
    """Distance to a key signal; a kept signal may sit slightly elsewhere at the last time (ppm_last)."""
    return min(abs(s["ppm"] - p), abs(s.get("ppm_last", s["ppm"]) - p))


def _nearest(signals: list[dict], p: float, tol: float):
    hits = [s for s in signals if _dist(s, p) <= tol]
    return min(hits, key=lambda s: _dist(s, p)) if hits else None


def check_verdict(entry: dict, case: dict, tol: float | None = None, sample: str | None = None) -> Report:
    """Feedback on one verdict ({"call", "lost_ppm", "new_ppm", "kept_ppm", "product_guess", "confidence"})
    against one answer-key case. A case with no published call points to the paper's tables.
    'unsure' is always a fair answer."""
    tol = tol if tol is not None else case.get("tolerance_ppm", 0.05)
    sample = sample or case.get("sample", "")
    rep = Report()
    entry = entry or {}
    call = plain_call(entry.get("call", ""))
    expected = plain_call(case.get("call")) or None
    source = case.get("call_source", "the published finding")
    check = f"Check your decision against {case.get('check_against', 'the paper')}."
    if not call:
        rep.append(Feedback("to do", f"No decision yet: write one of {quoted(CALLS)}."))
    elif call == "unsure":
        settle = f" What settles it: {case['why']}." if case.get("why") else ""
        rep.append(Feedback("open", "You answered unsure, which is a fair answer on this data." + settle
                            + ("" if expected else " " + check)))
    elif expected is None:
        rep.append(Feedback("open", f"You decided '{call}'. {check} Your hand-in goes to review as you wrote it."))
    elif call == expected:
        rep.append(Feedback("agrees", f"This matches {source}: '{expected}'."))
    else:
        why = f": {case['why']}" if case.get("why") else ""
        rep.append(Feedback("look again", f"This differs from {source} ('{expected}'){why}. Go back over the "
                                          "peaks you listed as lost and kept. Your hand-in goes to review as you "
                                          "wrote it."))

    signals = case.get("signals", [])
    cited = {g: [p for p in (entry.get(f"{g}_ppm") or []) if isinstance(p, (int, float))]
             for g in ("lost", "new", "kept")}
    for group, values in cited.items():
        for p in values:
            hit = _nearest(signals, p, tol)
            if ACID_ZONE[0] <= p <= ACID_ZONE[1]:
                rep.append(Feedback("look again", f"{p:.2f} ({group}): that is the acid's own signal, not the sample's."))
            elif hit and hit["group"] == group:
                rep.append(Feedback("agrees", f"{p:.2f} ({group}): {hit['what']}."))
            elif hit:
                why = hit.get("if_listed_as", {}).get(group, f"in the data this one is {hit['group']} ({hit['what']}).")
                rep.append(Feedback("look again", f"{p:.2f} (you said {group}): {why}"))
            elif group == "lost" and EXCHANGEABLE[0] <= p <= EXCHANGEABLE[1] and sample not in AROMATIC:
                rep.append(Feedback("note", f"{p:.2f} (lost): hydrogens on nitrogen or oxygen swap with the acid's "
                                            "deuterium, so their signals often fade or do not show. A missing NH peak "
                                            "is not evidence of breakdown."))
            elif _nearest(signals, 12.0 - p, tol):
                m = _nearest(signals, 12.0 - p, tol)
                rep.append(Feedback("look again", f"{p:.2f}: nothing here, but its mirror image {12.0 - p:.2f} is "
                                                  f"{m['what']}. Is your ppm axis reversed?"))
            elif signals:
                rep.append(Feedback("note", f"{p:.2f} ({group}): no signal in the key within {tol} ppm. It may be a "
                                            "minor peak, or a misread value."))
    for s in signals:
        if s.get("optional"):
            continue
        if not any(_dist(s, p) <= tol for p in cited.get(s["group"], [])):
            rep.append(Feedback("tip", f"You could also cite {s['ppm']:.2f} as {s['group']}: {s['what']}."))

    guess = str(entry.get("product_guess", "")).strip().lower()
    if "product_words" in case:
        if not guess:
            rep.append(Feedback("to do", "No product guess yet."))
        elif any(w in guess for w in case["product_words"]):
            rep.append(Feedback("agrees", f"Product: {case['product']}."))
        elif any(w in guess for w in case.get("close_words", [])):
            rep.append(Feedback("note", case.get("close_message", f"Close. The published product is {case['product']}.")))
        else:
            rep.append(Feedback("look again", f"Product '{guess}': the published product is {case['product']}. "
                                              "See Look closer below for its spectrum."))
    elif guess and expected is None:
        rep.append(Feedback("open", f"Product '{guess}': check it against {case.get('check_against', 'the paper')}."))

    conf = str(entry.get("confidence", "")).strip().lower()
    if expected and call and call != "unsure":
        if conf == "high" and call != expected:
            rep.append(Feedback("note", "You gave high confidence to a decision that differs from the published one. Check your evidence again."))
        elif conf == "low" and call == expected:
            rep.append(Feedback("note", "Your decision matches the published one, so the evidence supports more than low confidence."))
    return rep


def check_peak_list(mine: dict, case: dict, tol: float | None = None, labels: dict | None = None) -> Report:
    """Do the member's peak lists ({time: [ppm...]}) contain the signals that matter (and lack the gone ones)?"""
    tol = tol if tol is not None else case.get("tolerance_ppm", 0.05)
    rep = Report()
    for t, exp in case.get("expect", {}).items():
        have = _peaks.ppms(mine.get(t, []))
        where = (labels or {}).get(t, time_label(t))
        missed = _peaks.match(have, exp.get("present", []), tol)["missing"]
        wrongly = _peaks.match(have, exp.get("absent", []), tol)["found"]
        if not missed and not wrongly:
            rep.append(Feedback("agrees", f"{where}: all {len(exp.get('present', []))} expected signals are in your list."))
        for p in missed:
            if any(abs((12.0 - p) - q) <= tol for q in have):
                rep.append(Feedback("look again", f"{where}: no peak near {p:.2f} but one near {12.0 - p:.2f}, its "
                                                  "mirror image: is the axis reversed?"))
            else:
                rep.append(Feedback("look again", f"{where}: no peak near {p:.2f}. If it is small, try a lower "
                                                  "MIN_HEIGHT."))
        for p in wrongly:
            rep.append(Feedback("look again", f"{where}: a peak near {p:.2f} should be gone by now. Check which "
                                              "spectrum this list came from."))
    return rep


def similarity_feedback(r: float, threshold: float = 0.95) -> Feedback:
    """r: the correlation of two traces between 1 and 6.5 ppm (1 means the same shape)."""
    if r >= threshold:
        return Feedback("agrees", f"Similarity {r:.3f}, at or above {threshold}: the two traces have the same "
                                  "shape, so your processing matches the instrument's.")
    return Feedback("look again", f"Similarity {r:.3f}, below {threshold}: the two traces differ in shape. Check "
                                  "the phase and the axis direction.")


def line_feedback(diff: dict, label: str = "") -> Feedback:
    """The largest difference in position between matching lines (from peaks.line_differences)."""
    lead = f"{label}: " if label else ""
    if diff.get("largest_ppm") is None:
        return Feedback("look again", f"{lead}No lines found between 1 and 6.5 ppm to compare. Check the axis.")
    d, at = diff["largest_ppm"], diff["at_ppm"]
    text = (f"{lead}The largest difference between matching lines is {d:.4f} ppm, at the line near {at:.3f} ppm "
            f"({diff['lines']} lines compared).")
    if d <= 0.01:
        return Feedback("agrees", text + " Every line sits within 0.01 ppm of the instrument's.")
    return Feedback("look again", text + " That is more than 0.01 ppm: check the phase, the axis direction and "
                                         "whether that line is a small peak only one of the two spectra shows.")


def check_backbone(ppm, case: dict | None = None, tol: float | None = None) -> Feedback:
    """The member's backbone signal (the alpha hydrogen). Compared only when the case names one;
    otherwise it is saved for the reviewer."""
    case = case or {}
    tol = tol if tol is not None else case.get("tolerance_ppm", 0.05)
    if ppm is ... or ppm is None:
        return Feedback("to do", "No backbone signal chosen yet.")
    bb = [s for s in case.get("signals", []) if s.get("backbone")]
    if not bb:
        return Feedback("open", f"Saved: {float(ppm):.2f} ppm as your backbone signal. It goes in your hand-in, and "
                                "your reviewer goes over it with you.")
    if any(abs(s["ppm"] - float(ppm)) <= tol for s in bb):
        return Feedback("agrees", f"{float(ppm):.2f} ppm: {bb[0]['what']}.")
    hit = _nearest(case.get("signals", []), float(ppm), tol)
    if hit:
        return Feedback("look again", f"{float(ppm):.2f} ppm is {hit['what']}. The backbone signal is the alpha "
                                      "hydrogen: the hydrogen on the carbon next to the nitrogen.")
    return Feedback("look again", f"No signal near {float(ppm):.2f} ppm in the key. Pick a peak from your list.")
