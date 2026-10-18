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

CALLS = ("survives", "degrades", "side chain modified", "unsure")
CONFIDENCE = ("low", "medium", "high")

# Where the acid's own big signal sits on the instrument's ppm scale in these datasets.
# 98% (K): 11.43 to 11.58 ppm; a few early spectra sit near 11.08 (referenced differently).
# 81% (H): 11.66 to 12.08 ppm, depending on the sample.
ACID_WINDOW = {"K": (11.5, 0.5), "H": (11.85, 0.4), None: (11.6, 0.65)}
ACID_ZONE = (10.0, 13.0)          # never cite a peak in here as the sample's own
EXCHANGEABLE = (6.3, 9.6)         # NH and NH3+ signals of non-aromatic samples sit here in this acid
AROMATIC = {"FF", "YY", "WW", "HH", "PHE", "TYR", "TRP", "HIS"}


@dataclass
class Feedback:
    kind: str      # agrees | look again | open | to do | tip | note | trap | ok
    text: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.text}"


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
                                f"{later:.1f} Hz near {center:.2f} ppm). This is common while the sample dissolves "
                                "and is not a chemical change by itself.")
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


def check_prediction(pred: dict, key: dict) -> Report:
    """Comparison of a prediction with a key of {field: {"answer", "band", "water"}}."""
    rep = Report()
    for name, k in key.items():
        v = pred.get(name)
        label = k.get("label", name)
        if v is None or v is ...:
            rep.append(Feedback("to do", f"{label}: no prediction entered. Compare with the reveal."))
        elif "answer" in k:
            rep.append(Feedback("agrees", f"{label}: {v}. This matches the data.") if v == k["answer"] else
                       Feedback("look again", f"{label}: you said {v}; there are {k['answer']} ({k.get('why', '')})."))
        else:
            lo, hi = k["band"]
            water = k.get("water")
            try:
                v = float(v)
            except (TypeError, ValueError):
                rep.append(Feedback("look again", f"{label}: use a number in ppm, for example 2.0."))
                continue
            if lo <= v <= hi:
                rep.append(Feedback("agrees", f"{label}: {v} ppm. This is where it appears in this data ({lo} to {hi} ppm)."))
            elif water and water[0] <= v <= water[1]:
                rep.append(Feedback("note", f"{label}: {v} ppm is where it sits in water. The acid moves it up by "
                                            "about half a ppm or more."))
            else:
                rep.append(Feedback("look again", f"{label}: you said {v} ppm; in this data it appears at {lo} to {hi} ppm."))
    return rep


def verdict_problems(verdict: dict, cases: list[str]) -> list[str]:
    """Format problems only (not right or wrong): what to fix before the check can read a verdict."""
    issues = []
    for case in cases:
        entry = verdict.get(case, {})
        call = str(entry.get("call", "")).strip().lower()
        if call and call not in CALLS:
            issues.append(f"{case}: call should be one of {', '.join(CALLS)} (got {call!r})")
        conf = str(entry.get("confidence", "")).strip().lower()
        if conf and conf not in CONFIDENCE:
            issues.append(f"{case}: confidence should be one of {', '.join(CONFIDENCE)} (got {conf!r})")
        for k in ("lost_ppm", "new_ppm", "kept_ppm"):
            for p in entry.get(k, []) or []:
                if not isinstance(p, (int, float)):
                    issues.append(f"{case}: {k} holds {p!r}; use numbers like 2.09")
    return issues


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
    call = str(entry.get("call", "")).strip().lower()
    expected = case.get("call")
    source = case.get("call_source", "the published finding")
    check = f"Check your call against {case.get('check_against', 'the paper')}."
    if not call:
        rep.append(Feedback("to do", "No call yet: choose " + ", ".join(CALLS) + "."))
    elif call == "unsure":
        settle = f" What settles it: {case['why']}." if case.get("why") else ""
        rep.append(Feedback("open", "You answered unsure, which is a fair call on this data." + settle
                            + ("" if expected else " " + check)))
    elif expected is None:
        rep.append(Feedback("open", f"You called it '{call}'. {check} Your hand-in goes to review as you wrote it."))
    elif call == expected:
        rep.append(Feedback("agrees", f"This matches {source}: '{expected}'."))
    else:
        why = f": {case['why']}" if case.get("why") else ""
        rep.append(Feedback("look again", f"This differs from {source} ('{expected}'){why}. "
                                          "Your hand-in goes to review as you wrote it."))

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
                rep.append(Feedback("note", f"{p:.2f} (lost): NH and OH protons exchange with the deuterated acid and "
                                            "often fade or do not show. A missing NH peak is not evidence of breakdown."))
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
            rep.append(Feedback("look again", f"Product '{guess}': the published product is {case['product']}."))
    elif guess and expected is None:
        rep.append(Feedback("open", f"Product '{guess}': check it against {case.get('check_against', 'the paper')}."))

    conf = str(entry.get("confidence", "")).strip().lower()
    if expected and call and call != "unsure":
        if conf == "high" and call != expected:
            rep.append(Feedback("note", "You gave high confidence to a call that differs from the published one. Check your evidence again."))
        elif conf == "low" and call == expected:
            rep.append(Feedback("note", "Your call matches the published one, so the evidence supports more than low confidence."))
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
    if r >= threshold:
        return Feedback("agrees", f"Similarity {r:.3f}: your processing matches the instrument's.")
    return Feedback("look again", f"Similarity {r:.3f}, below {threshold}. Check the phase and the axis direction.")


def check_backbone(ppm, case: dict | None = None, tol: float | None = None) -> Feedback:
    """The member's backbone signal (the alpha-H). Compared only when the case names one; otherwise
    it is saved for the reviewer."""
    case = case or {}
    tol = tol if tol is not None else case.get("tolerance_ppm", 0.05)
    if ppm is ... or ppm is None:
        return Feedback("to do", "No backbone signal chosen yet.")
    bb = [s for s in case.get("signals", []) if s.get("backbone")]
    if not bb:
        return Feedback("open", f"{float(ppm):.2f} ppm: saved with your hand-in. Your reviewer goes over it with you.")
    if any(abs(s["ppm"] - float(ppm)) <= tol for s in bb):
        return Feedback("agrees", f"{float(ppm):.2f} ppm: {bb[0]['what']}.")
    hit = _nearest(case.get("signals", []), float(ppm), tol)
    if hit:
        return Feedback("look again", f"{float(ppm):.2f} ppm is {hit['what']}. The backbone signal is the H on the "
                                      "carbon that carries both the NH3+ and the COOH.")
    return Feedback("look again", f"No signal near {float(ppm):.2f} ppm in the key. Pick a peak from your list.")
