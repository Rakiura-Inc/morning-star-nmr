"""Trap checks and comparisons with published calls. Feedback only: never a score, never "correct" or "wrong".

Every check returns `Feedback` lines (one, or a list). A trap that fires never stops the notebook;
it prints one line and is counted in the hand-in (`traps_flagged`) so the reviewer sees what the
member was told.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from itertools import pairwise

import numpy as np

from . import peaks as _peaks
from .data import RECORDS
from .io import Spectrum
from .names import ACID_STRENGTH

# The calls a member writes, in plain words. The answer keys and the replication table keep the
# older words ("degrades", "side chain modified"); both spellings are accepted everywhere.
CALLS = ("survives", "breaks down", "side chain changed", "unsure")
KEY_CALLS = ("survives", "degrades", "side chain modified", "unsure")
_CALL_WORDS = {
    "degrades": "breaks down",
    "degraded": "breaks down",
    "broke down": "breaks down",
    "breaks": "breaks down",
    "break down": "breaks down",
    "side chain modified": "side chain changed",
    "side-chain changed": "side chain changed",
    "side chain change": "side chain changed",
}
_KEY_WORD = {"breaks down": "degrades", "side chain changed": "side chain modified"}
CONFIDENCE = ("low", "medium", "high")

# Where the acid's own big signal sits on the instrument's ppm scale in these datasets.
# 98% (K): 11.43 to 11.58 ppm; a few early spectra sit near 11.08 (referenced differently).
# 81% (H): 11.66 to 12.08 ppm, depending on the sample.
ACID_WINDOW = {"K": (11.5, 0.5), "H": (11.85, 0.4), None: (11.6, 0.65)}
ACID_ZONE = _peaks.ACID_AREA  # never cite a peak in here as the sample's own
EXCHANGEABLE = (6.3, 9.6)  # NH and NH3+ signals of non-aromatic samples sit here in this acid
AROMATIC = {"FF", "YY", "WW", "HH", "PHE", "TYR", "TRP", "HIS"}
ACID_MIN_SHARE = 0.2  # the 10 to 13 ppm peak counts as the acid's when it is at least this share of the tallest
C13_TALLEST_BAND = (5, 65)  # where the tallest 13C peak of these molecules sits, in ppm
# A 1H signal at p ppm read off a reversed axis shows up near MIRROR_SUM_PPM - p.
MIRROR_SUM_PPM = 12.0


def _mirror(p: float) -> float:
    return MIRROR_SUM_PPM - p


def plain_call(call) -> str:
    """A call in the member's words: "degrades" reads as "breaks down", and so on."""
    c = str(call or "").strip().lower()
    return _CALL_WORDS.get(c, c)


def key_call(call) -> str:
    """A call in the answer keys' words (used by the replication table)."""
    c = plain_call(call)
    return _KEY_WORD.get(c, c)


# The word a printed line starts with, for each kind of feedback. The kind itself stays internal.
LEAD_WORDS = {
    "agrees": "Yes.",
    "look again": "Look again.",
    "to do": "To do:",
    "tip": "Tip:",
    "note": "Note:",
    "trap": "Trap:",
    "ok": "OK:",
    "open": "",
}


@dataclass
class Feedback:
    """One line of feedback. kind: agrees, look again, open, to do, tip, note, trap or ok."""

    kind: str
    text: str

    def __str__(self) -> str:
        lead = LEAD_WORDS[self.kind]
        if lead:
            return f"{lead} {self.text}"
        return self.text


def show(feedback: list[Feedback], title: str) -> None:
    """Print a title, then each feedback line indented under it."""
    print(title)
    for line in feedback:
        print(f"  {line}")
    if not feedback:
        print("  nothing to flag")


# ---------------------------------------------------------------------------------------------
# trap checks


def acid_ppm(spectrum: Spectrum) -> float:
    """Position of the tallest peak between 10 and 13 ppm (the acid's own peak). On a mirrored axis
    nothing big sits there, so it falls back to the tallest peak anywhere."""
    ppm, intensity = spectrum.region(*ACID_ZONE)
    if intensity.size and intensity.max() > ACID_MIN_SHARE * spectrum.intensity.max():
        return float(ppm[int(np.argmax(intensity))])
    return _peaks.tallest_ppm(spectrum)


def _check_carbon_axis(spectrum: Spectrum, tallest: float, mirror: float) -> Feedback:
    """13C: the tallest peak of these molecules sits in the aliphatic band (5 to 65 ppm)."""
    low, high = C13_TALLEST_BAND
    if low <= tallest <= high:
        return Feedback(
            "ok",
            f"{spectrum.label}: tallest peak at {tallest:.1f} ppm, in the aliphatic band. "
            "The axis is the right way round.",
        )
    if low <= mirror <= high:
        return Feedback(
            "trap",
            f"{spectrum.label}: the tallest peak is at {tallest:.1f} ppm, the mirror image of {mirror:.1f}. "
            "The ppm axis is probably reversed.",
        )
    return Feedback("look again", f"{spectrum.label}: the tallest peak is at {tallest:.1f} ppm. Check the axis.")


def check_axis(spectrum: Spectrum) -> Feedback:
    """Is the ppm axis the right way round? 1H: the tallest peak (the acid) must sit near 11.5 ppm
    in 98% acid. 13C: the tallest peak sits in the aliphatic band."""
    tallest = _peaks.tallest_ppm(spectrum)
    mirror = float(spectrum.ppm.max() + spectrum.ppm.min()) - tallest  # where it lands if the axis is flipped
    if spectrum.nucleus == "13C":
        return _check_carbon_axis(spectrum, tallest, mirror)
    centre, half_width = ACID_WINDOW.get(spectrum.acid, ACID_WINDOW[None])
    strength = ACID_STRENGTH.get(spectrum.acid, "this")
    if abs(tallest - centre) <= half_width:
        return Feedback("ok", f"{spectrum.label}: acid peak at {tallest:.3f} ppm. The axis is the right way round.")
    if abs(mirror - centre) <= half_width:
        return Feedback(
            "trap",
            f"{spectrum.label}: the acid peak is at {tallest:.2f} ppm here. In {strength} acid it sits near "
            f"{centre:.1f} ppm, so the ppm axis is probably reversed. Use ng.proc_base.rev "
            "or load the processed spectrum.",
        )
    return Feedback(
        "look again",
        f"{spectrum.label}: the tallest peak is at {tallest:.2f} ppm, not near {centre:.1f}. "
        "Check the axis and which spectrum this is.",
    )


# Every time label the datasets use, in time order.
TIME_ORDER = [time for record in RECORDS.values() for time in record["time_order"]]


def check_order(series: list[Spectrum]) -> Feedback:
    """Time labels and the instrument's acquisition dates must both increase up the stack."""
    for earlier, later in pairwise(series):
        both_known = earlier.time in TIME_ORDER and later.time in TIME_ORDER
        if both_known and TIME_ORDER.index(earlier.time) > TIME_ORDER.index(later.time):
            return Feedback(
                "trap",
                f"Your stack is not in time order: {earlier.time_label} comes before {later.time_label}. "
                "Put the spectra in time order before comparing.",
            )
        if earlier.acquired and later.acquired and earlier.acquired > later.acquired:
            return Feedback(
                "trap",
                f"Your stack is not in time order: {earlier.time_label} was recorded after "
                f"{later.time_label}. Put the spectra in time order before comparing.",
            )
    return Feedback("ok", "The labels and the acquisition dates are both in time order.")


DRIFT_LIMIT_PPM = 0.2  # more acid-peak drift than this across a series shifts every other peak too


def check_drift(series: list[Spectrum]) -> Feedback:
    """How far the acid signal moves across the series."""
    positions = [acid_ppm(spectrum) for spectrum in series]
    moved = max(positions) - min(positions)
    if moved > DRIFT_LIMIT_PPM:
        return Feedback(
            "trap",
            f"The acid peak moved by {moved:.2f} ppm across this series. Some drift is "
            "expected as the solution changes, but this much shifts every other peak too. "
            "Align on it before reading other shifts, and say in your hand-in that you did.",
        )
    return Feedback(
        "ok",
        f"The acid peak moves by {moved:.2f} ppm across the series, which is small. Keep the instrument's ppm scale.",
    )


def check_normalisation(norm: tuple | None, acid: str | None = "K") -> Feedback:
    """Scaling to the whole spectrum (or a region that holds the acid) hides the sample's peaks."""
    acid_centre, _ = ACID_WINDOW.get(acid, ACID_WINDOW[None])
    if norm is None or (min(norm) <= acid_centre <= max(norm)):
        return Feedback(
            "trap",
            "Your traces are scaled to the acid peak, which hides small changes. "
            "Scale within 1 to 6.5 ppm, or within the region you are reading.",
        )
    return Feedback("ok", f"Scaled within {min(norm)} to {max(norm)} ppm.")


BROAD_RATIO = 1.5  # a first peak this many times wider than the later ones counts as broad


def check_broad_early(series: list[Spectrum], low_ppm: float = 1.0, high_ppm: float = 6.5) -> Feedback:
    """Is the first spectrum's main peak much broader than later ones?"""
    first = series[0]
    centre = _peaks.tallest_ppm(first, low_ppm, high_ppm)
    widths = [_peaks.linewidth_hz(spectrum, centre) for spectrum in series]
    later = statistics.median(widths[1:]) if len(widths) > 1 else widths[0]
    if later > 0 and widths[0] > BROAD_RATIO * later:
        return Feedback(
            "note",
            f"The {first.time_label} peaks are broader than later ones ({widths[0]:.1f} Hz vs "
            f"{later:.1f} Hz near {centre:.2f} ppm). The peaks sharpen after day 1, most likely because "
            "the hydrogens on nitrogen swap with the acid's deuterium and stop splitting the "
            "peaks next to them. It is not breakdown.",
        )
    return Feedback("ok", f"Line widths near {centre:.2f} ppm: {widths[0]:.1f} Hz first, {later:.1f} Hz later.")


MIN_NEW_HEIGHT = 0.05  # a new peak smaller than this share of the tallest does not count here
MOSTLY_GONE = 0.5  # less than half the first spectrum's signal (against the acid) is left


def _signal_against_acid(spectrum: Spectrum, low_ppm: float, high_ppm: float) -> float:
    """All the sample's signal between two ppm values, divided by the acid peak's area."""
    acid_area = max(_peaks.area(spectrum, *ACID_ZONE), 1e-12)  # never divide by zero on an empty acid window
    return _peaks.area(spectrum, low_ppm, high_ppm) / acid_area


def check_signal_loss(first: Spectrum, last: Spectrum, low_ppm: float = 1.0, high_ppm: float = 6.5) -> Feedback:
    """Most of the sample's signal gone, relative to the acid, with nothing new: maybe it came out of solution."""
    first_amount = _signal_against_acid(first, low_ppm, high_ppm)
    kept = _signal_against_acid(last, low_ppm, high_ppm) / first_amount if first_amount > 0 else 1.0
    first_ppm = [peak["ppm"] for peak in _peaks.pick(first, low_ppm, high_ppm)]
    last_ppm = [peak["ppm"] for peak in _peaks.pick(last, low_ppm, high_ppm) if peak["height"] >= MIN_NEW_HEIGHT]
    new = _peaks.compare(first_ppm, last_ppm)["new"]
    if kept < MOSTLY_GONE and not new:
        return Feedback(
            "trap",
            "Most of the signal disappeared and nothing new appeared. That can mean the sample "
            "came out of solution rather than reacted. Say so in your hand-in, or answer unsure.",
        )
    if new:
        return Feedback(
            "ok", f"Signal relative to the acid: {kept:.0%} of the first spectrum's, with {len(new)} new peak(s)."
        )
    return Feedback("ok", f"Signal relative to the acid: {kept:.0%} of the first spectrum's.")


def run_traps(
    series: list[Spectrum], norm: tuple | None = (1.0, 6.5), low_ppm: float = 1.0, high_ppm: float = 6.5
) -> list[Feedback]:
    """All the trap checks that apply to one stacked series. Prints the ones that flag something.

    norm: the region the stack was scaled to. low_ppm, high_ppm: the region the member reads."""
    feedback = [check_axis(spectrum) for spectrum in series]
    feedback.append(check_order(series))
    if series[0].nucleus == "1H":
        feedback.append(check_drift(series))
        feedback.append(check_normalisation(norm, series[0].acid))
        feedback.append(check_broad_early(series, low_ppm, high_ppm))
        feedback.append(check_signal_loss(series[0], series[-1], low_ppm, high_ppm))
    flagged = [line for line in feedback if line.kind != "ok"]
    passed = len(feedback) - len(flagged)
    first = series[0]
    if first.acid in ACID_STRENGTH:
        title = f"Checks on {first.sample_name} in {ACID_STRENGTH[first.acid]} acid"
    else:
        title = f"Checks on {first.sample_name}"
    show(flagged, f"{title}: {passed} passed, {len(flagged)} flagged")
    return feedback


def traps_flagged(*feedback_lists: list[Feedback]) -> int:
    """How many trap lines fired across the given check results (counted in the hand-in)."""
    count = 0
    for feedback in feedback_lists:
        count += sum(1 for line in feedback if line.kind == "trap")
    return count


# ---------------------------------------------------------------------------------------------
# predictions and verdicts


def _number(value) -> float | None:
    """A member's answer as a number, or None if it is not one (a word, or ... left in)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


LOOK_NEXT = "Now look at the spectra below and find where it really sits."


def _count_feedback(label: str, answer, spec: dict) -> Feedback:
    """A count that follows from the structure: spec {"answer", "why"}."""
    why = spec.get("why", "")
    if answer == spec["answer"]:
        return Feedback("agrees", f"{label}: {answer}. {why}")
    return Feedback(
        "look again",
        f"{label}: you said {answer}; the structure gives {spec['answer']}. {why} "
        "Open hint 2 above if this is still unclear.",
    )


def _position_feedback(label: str, answer, spec: dict) -> Feedback:
    """A position, judged only against the typical range the notebook teaches:
    spec {"typical", "typical_text", "water"}."""
    position = _number(answer)
    if position is None:
        return Feedback("to do", f"{label}: write a number in ppm, for example 2.0.")
    low, high = spec["typical"]
    near = spec.get("typical_text", f"between {low} and {high} ppm")
    water = spec.get("water")
    if low <= position <= high:
        return Feedback("agrees", f"{label}: {position:g} ppm fits {near}. {LOOK_NEXT}")
    if water and water[0] <= position <= water[1]:
        return Feedback(
            "look again",
            f"{label}: {position:g} ppm is closer to where it sits in water. The acid "
            "pulls electrons away from the hydrogens, so signals sit higher "
            f"in acid; the table above gives {near}. {LOOK_NEXT}",
        )
    return Feedback("look again", f"{label}: you said {position:g} ppm; the table above gives {near}. {LOOK_NEXT}")


def check_prediction(prediction: dict, key: dict) -> list[Feedback]:
    """Feedback on a prediction made before the member has seen the data.

    key: {field: spec}. A spec is one of:
      {"label", "answer", "why"}                       a count that follows from the structure
      {"label", "typical", "typical_text", "water"}    a position, judged only against the typical
                                                       range the notebook teaches (never this dataset)
      {"label", "later"}                               a call the member checks later in the notebook
    """
    feedback = []
    for name, spec in key.items():
        answer = prediction.get(name)
        label = spec.get("label", name)
        if answer is None or answer is ... or answer == "":
            feedback.append(
                Feedback("to do", f"{label}: no prediction entered. You can still find it in the spectra below.")
            )
        elif "later" in spec:
            feedback.append(Feedback("open", f"{label}: you said {answer!r}. {spec['later']}"))
        elif "answer" in spec:
            feedback.append(_count_feedback(label, answer, spec))
        else:
            feedback.append(_position_feedback(label, answer, spec))
    return feedback


def _reading_feedback(label: str, position: float, band: list, predicted) -> Feedback:
    """One position read off the spectra, against the range it has in this dataset."""
    low, high = band
    was = f" You predicted {predicted} ppm." if _number(predicted) is not None else ""
    if low <= position <= high:
        return Feedback("agrees", f"{label}: {position:g} ppm. In this data it sits at {low} to {high} ppm.{was}")
    return Feedback(
        "look again",
        f"{label}: {position:g} ppm. Check which peak you read: in this data it sits at {low} to {high} ppm.{was}",
    )


def check_reading(reading: dict, key: dict, prediction: dict | None = None) -> list[Feedback]:
    """Feedback on positions the member read off the spectra (after the plots). Here the ranges
    measured in this dataset are used: key {field: {"label", "band"}}."""
    prediction = prediction or {}
    feedback = []
    for name, spec in key.items():
        if "band" not in spec:
            continue
        label = spec.get("label", name)
        position = _number(reading.get(name))
        if position is None:
            feedback.append(
                Feedback(
                    "to do", f"{label}: read its position off the plot or peak list above and write it as a number."
                )
            )
        else:
            feedback.append(_reading_feedback(label, position, spec["band"], prediction.get(name)))
    return feedback


FIELD_WORDS = {
    "call": "decision",
    "lost_ppm": "lost peaks",
    "new_ppm": "new peaks",
    "kept_ppm": "kept peaks",
    "left": "how much is left",
    "product_guess": "product guess",
    "confidence": "confidence",
}
LEFT = ("little or none", "no clear loss", "unsure")
HARSHER = ("98%", "81%", "same", "unsure")


def quoted(words) -> str:
    """'"a", "b" or "c"', for listing the allowed answers."""
    in_quotes = [f'"{word}"' for word in words]
    return ", ".join(in_quotes[:-1]) + " or " + in_quotes[-1]


PEAK_LISTS = ("lost_ppm", "new_ppm", "kept_ppm")


def _entry_problems(entry: dict, who: str) -> list[str]:
    """What to fix in one molecule's verdict before the check can read it."""
    problems = []
    call = plain_call(entry.get("call", ""))
    if call and call not in CALLS:
        problems.append(f'The decision for {who} is "{entry.get("call")}": write one of {quoted(CALLS)}.')
    confidence = str(entry.get("confidence", "")).strip().lower()
    if confidence and confidence not in CONFIDENCE:
        problems.append(f'The confidence for {who} is "{entry.get("confidence")}": write one of {quoted(CONFIDENCE)}.')
    left = str(entry.get("left", "")).strip().lower()
    if left and left not in LEFT:
        problems.append(f'How much is left for {who} is "{entry.get("left")}": write one of {quoted(LEFT)}.')
    for field in PEAK_LISTS:
        for ppm in entry.get(field) or []:
            if not isinstance(ppm, (int, float)):
                problems.append(
                    f"The {FIELD_WORDS[field]} for {who} include {ppm!r}: write numbers without quotes, "
                    "like [2.08, 4.94]."
                )
    return problems


def verdict_problems(verdict: dict, cases: list[str], names: dict | None = None) -> list[str]:
    """Things to fix before the check can read a verdict (format only, never right or wrong)."""
    names = names or {}
    problems = []
    for case in cases:
        problems += _entry_problems(verdict.get(case) or {}, names.get(case, case))
    return problems


def _blank(value) -> bool:
    if isinstance(value, str):
        return not value.strip()
    return not value


def verdict_notes(verdict: dict, cases: list[str], names: dict | None = None) -> list[str]:
    """One friendly line per molecule naming the fields still empty. Empty is allowed; nothing here
    blocks the hand-in."""
    names = names or {}
    notes = []
    for case in cases:
        who = names.get(case, case)
        entry = verdict.get(case) or {}
        empty = [words for field, words in FIELD_WORDS.items() if field in entry and _blank(entry[field])]
        if empty:
            notes.append(
                f"{who}: still empty: {', '.join(empty)}. An empty peak list is fine if there were "
                'none, and "unsure" is a fair answer.'
            )
    return notes


def show_format(verdict: dict, cases: list[str], names: dict | None = None) -> list[str]:
    """Print the format problems and the notes on empty fields. Returns the problems."""
    problems = verdict_problems(verdict, cases, names)
    for line in problems + verdict_notes(verdict, cases, names):
        print(f"  {line}")
    if not problems:
        print("Nothing here blocks your hand-in. Change any answer above and run the cells again to update it.")
    return problems


def _distance(signal: dict, ppm: float) -> float:
    """Distance to a key signal; a kept signal may sit slightly elsewhere at the last time (ppm_last)."""
    last_ppm = signal.get("ppm_last", signal["ppm"])
    return min(abs(signal["ppm"] - ppm), abs(last_ppm - ppm))


def _nearest(signals: list[dict], ppm: float, tolerance_ppm: float) -> dict | None:
    """The key signal closest to ppm, if one is within tolerance_ppm."""
    nearest = None
    for signal in signals:
        distance = _distance(signal, ppm)
        if distance > tolerance_ppm:
            continue
        if nearest is None or distance < _distance(nearest, ppm):
            nearest = signal
    return nearest


def _call_feedback(call: str, expected: str | None, case: dict) -> Feedback:
    """The decision against the published call (or, with none, where to check it)."""
    source = case.get("call_source", "the published finding")
    check = f"Check your decision against {case.get('check_against', 'the paper')}."
    if not call:
        return Feedback("to do", f"No decision yet: write one of {quoted(CALLS)}.")
    if call == "unsure":
        text = "You answered unsure, which is a fair answer on this data."
        if case.get("why"):
            text += f" What settles it: {case['why']}."
        if not expected:
            text += " " + check
        return Feedback("open", text)
    if expected is None:
        return Feedback("open", f"You decided '{call}'. {check} Your hand-in goes to review as you wrote it.")
    if call == expected:
        return Feedback("agrees", f"This matches {source}: '{expected}'.")
    why = ""
    if case.get("why"):
        why = f": {case['why']}"
    return Feedback(
        "look again",
        f"This differs from {source} ('{expected}'){why}. Go back over the "
        "peaks you listed as lost and kept. Your hand-in goes to review as you "
        "wrote it.",
    )


def _against_key_signal(ppm: float, group: str, hit: dict) -> Feedback:
    """A cited peak that sits on one of the key's signals: the same group, or another one."""
    if hit["group"] == group:
        return Feedback("agrees", f"{ppm:.2f} ({group}): {hit['what']}.")
    default = f"in the data this one is {hit['group']} ({hit['what']})."
    why = hit.get("if_listed_as", {}).get(group, default)
    return Feedback("look again", f"{ppm:.2f} (you said {group}): {why}")


def _cited_feedback(
    ppm: float, group: str, signals: list[dict], *, tolerance_ppm: float, sample: str
) -> Feedback | None:
    """One peak the member cited as lost, new or kept, against the key's signals."""
    if ACID_ZONE[0] <= ppm <= ACID_ZONE[1]:
        return Feedback("look again", f"{ppm:.2f} ({group}): that is the acid's own signal, not the sample's.")
    hit = _nearest(signals, ppm, tolerance_ppm)
    if hit:
        return _against_key_signal(ppm, group, hit)
    if group == "lost" and EXCHANGEABLE[0] <= ppm <= EXCHANGEABLE[1] and sample not in AROMATIC:
        return Feedback(
            "note",
            f"{ppm:.2f} (lost): hydrogens on nitrogen or oxygen swap with the acid's "
            "deuterium, so their signals often fade or do not show. A missing NH peak "
            "is not evidence of breakdown.",
        )
    mirrored = _nearest(signals, _mirror(ppm), tolerance_ppm)
    if mirrored:
        return Feedback(
            "look again",
            f"{ppm:.2f}: nothing here, but its mirror image {_mirror(ppm):.2f} is {mirrored['what']}. "
            "Is your ppm axis reversed?",
        )
    if signals:
        return Feedback(
            "note",
            f"{ppm:.2f} ({group}): no signal in the key within {tolerance_ppm} ppm. "
            "It may be a minor peak, or a misread value.",
        )
    return None


def _product_feedback(guess: str, expected: str | None, case: dict) -> Feedback | None:
    """The product guess against the published product, when the key names one."""
    if "product_words" in case:
        if not guess:
            return Feedback("to do", "No product guess yet.")
        if any(word in guess for word in case["product_words"]):
            return Feedback("agrees", f"Product: {case['product']}.")
        if any(word in guess for word in case.get("close_words", [])):
            return Feedback("note", case.get("close_message", f"Close. The published product is {case['product']}."))
        return Feedback(
            "look again",
            f"Product '{guess}': the published product is {case['product']}. See Look closer below for its spectrum.",
        )
    if guess and expected is None:
        return Feedback("open", f"Product '{guess}': check it against {case.get('check_against', 'the paper')}.")
    return None


def _confidence_feedback(confidence: str, call: str, expected: str | None) -> Feedback | None:
    """A nudge when the confidence does not fit how the decision compares with the published one."""
    if not expected or not call or call == "unsure":
        return None
    if confidence == "high" and call != expected:
        return Feedback(
            "note",
            "You gave high confidence to a decision that differs from the published one. Check your evidence again.",
        )
    if confidence == "low" and call == expected:
        return Feedback(
            "note", "Your decision matches the published one, so the evidence supports more than low confidence."
        )
    return None


def _cited_ppm(entry: dict) -> dict[str, list[float]]:
    """The peaks the member cited, by group ("lost", "new", "kept"). Typed words are left out:
    write_down has already asked for numbers."""
    cited = {}
    for group in ("lost", "new", "kept"):
        cited[group] = []
        for ppm in entry.get(f"{group}_ppm") or []:
            if isinstance(ppm, (int, float)):
                cited[group].append(ppm)
    return cited


def check_verdict(entry: dict, case: dict) -> list[Feedback]:
    """Feedback on one verdict ({"call", "lost_ppm", "new_ppm", "kept_ppm", "product_guess", "confidence"})
    against one answer-key case. A case with no published call points to the paper's tables.
    'unsure' is always a fair answer."""
    tolerance_ppm = case.get("tolerance_ppm", 0.05)
    sample = case.get("sample", "")
    entry = entry or {}
    call = plain_call(entry.get("call", ""))
    expected = plain_call(case.get("call")) or None
    feedback = [_call_feedback(call, expected, case)]

    signals = case.get("signals", [])
    cited = _cited_ppm(entry)
    for group, positions in cited.items():
        for ppm in positions:
            line = _cited_feedback(ppm, group, signals, tolerance_ppm=tolerance_ppm, sample=sample)
            if line is not None:
                feedback.append(line)
    for signal in signals:
        if signal.get("optional"):
            continue
        if not any(_distance(signal, ppm) <= tolerance_ppm for ppm in cited.get(signal["group"], [])):
            feedback.append(
                Feedback("tip", f"You could also cite {signal['ppm']:.2f} as {signal['group']}: {signal['what']}.")
            )

    guess = str(entry.get("product_guess", "")).strip().lower()
    confidence = str(entry.get("confidence", "")).strip().lower()
    for line in (_product_feedback(guess, expected, case), _confidence_feedback(confidence, call, expected)):
        if line is not None:
            feedback.append(line)
    return feedback


SIMILAR = 0.95  # a correlation of two traces at or above this counts as the same shape
SAME_LINE_PPM = 0.01  # well under the 0.016 ppm between the two lines of one methyl peak


def similarity_feedback(correlation: float) -> Feedback:
    """correlation: of two traces between 1 and 6.5 ppm (1 means the same shape)."""
    if correlation >= SIMILAR:
        return Feedback(
            "agrees",
            f"Similarity {correlation:.3f}, at or above {SIMILAR}: the two traces have the same "
            "shape, so your processing matches the instrument's.",
        )
    return Feedback(
        "look again",
        f"Similarity {correlation:.3f}, below {SIMILAR}: the two traces differ in shape. Check "
        "the phase and the axis direction.",
    )


def line_feedback(differences: dict) -> Feedback:
    """The largest difference in position between matching lines: {"largest_ppm", "at_ppm", "lines"}."""
    if differences.get("largest_ppm") is None:
        return Feedback("look again", "No lines found between 1 and 6.5 ppm to compare. Check the axis.")
    largest, at = differences["largest_ppm"], differences["at_ppm"]
    text = (
        f"The largest difference between matching lines is {largest:.4f} ppm, at the line near {at:.3f} ppm "
        f"({differences['lines']} lines compared)."
    )
    if largest <= SAME_LINE_PPM:
        return Feedback("agrees", text + " Every line sits within 0.01 ppm of the instrument's.")
    return Feedback(
        "look again",
        text + " That is more than 0.01 ppm: check the phase, the axis direction and "
        "whether that line is a small peak only one of the two spectra shows.",
    )


def check_backbone(ppm, case: dict | None = None) -> Feedback:
    """The member's backbone signal (the alpha hydrogen). Compared only when the case names one;
    otherwise it is saved for the reviewer."""
    case = case or {}
    tolerance_ppm = case.get("tolerance_ppm", 0.05)
    if ppm is ... or ppm is None:
        return Feedback("to do", "No backbone signal chosen yet.")
    ppm = float(ppm)
    backbone = [signal for signal in case.get("signals", []) if signal.get("backbone")]
    if not backbone:
        return Feedback(
            "open",
            f"Saved: {ppm:.2f} ppm as your backbone signal. It goes in your hand-in, and "
            "your reviewer goes over it with you.",
        )
    if any(abs(signal["ppm"] - ppm) <= tolerance_ppm for signal in backbone):
        return Feedback("agrees", f"{ppm:.2f} ppm: {backbone[0]['what']}.")
    hit = _nearest(case.get("signals", []), ppm, tolerance_ppm)
    if hit:
        return Feedback(
            "look again",
            f"{ppm:.2f} ppm is {hit['what']}. The backbone signal is the alpha "
            "hydrogen: the hydrogen on the carbon next to the nitrogen.",
        )
    return Feedback("look again", f"No signal near {ppm:.2f} ppm in the key. Pick a peak from your list.")


def matches_published(entry: dict, case: dict) -> str:
    """For the shared results table: "yes" or "no" against the published call, or "unsure" when
    there is no published call or the member answered unsure (or nothing)."""
    call = plain_call(entry.get("call"))
    if not case.get("call") or call in ("", "unsure"):
        return "unsure"
    if call == plain_call(case["call"]):
        return "yes"
    return "no"
