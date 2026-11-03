"""Peak picking and simple measurements on one spectrum."""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks, peak_widths

from .io import Spectrum


def region_max(s: Spectrum, lo: float = 1.0, hi: float = 6.5) -> float:
    """The tallest point between lo and hi ppm (1.0 when the region is empty)."""
    _, y = s.region(lo, hi)
    return float(y.max()) if y.size else 1.0


def tallest_ppm(s: Spectrum, lo: float | None = None, hi: float | None = None) -> float:
    """Position of the tallest point, in the whole spectrum or between lo and hi ppm."""
    x, y = (s.ppm, s.y) if lo is None else s.region(lo, hi)
    return float(x[int(np.argmax(y))])


def _merge_lines(lines: list[tuple[float, float]], group_ppm: float) -> list[list[tuple[float, float]]]:
    """Group (ppm, height) lines, low ppm first: a line closer than group_ppm to the previous one joins
    its group."""
    groups: list[list[tuple[float, float]]] = []
    for p, h in sorted(lines):
        if groups and p - groups[-1][-1][0] < group_ppm:
            groups[-1].append((p, h))
        else:
            groups.append([(p, h)])
    return groups


def _signal(group: list[tuple[float, float]]) -> dict:
    """One signal from a group of lines: its height-weighted centre, line count and tallest line."""
    total = sum(h for _, h in group)
    centre = sum(p * h for p, h in group) / total
    return {"ppm": round(float(centre), 3), "lines": len(group), "height": round(float(max(h for _, h in group)), 3)}


def pick(
    s: Spectrum,
    lo: float = 1.0,
    hi: float = 6.5,
    min_height: float = 0.03,
    prominence: float = 0.02,
    group_ppm: float = 0.03,
    ref: tuple | None = None,
) -> list[dict]:
    """Signals between lo and hi ppm, high ppm first: [{"ppm", "lines", "height"}].

    min_height is a fraction of the tallest peak in the region (or in the `ref` region, when given:
    use that to look for small peaks in a narrow window). Lines closer than group_ppm merge into one
    signal, so a doublet counts once (its ppm is the height-weighted centre).
    """
    x, y = s.region(lo, hi)
    if y.size == 0:
        return []
    y = y / (region_max(s, *ref) if ref else y.max())
    idx, _ = find_peaks(y, height=min_height, prominence=prominence)
    signals = [_signal(g) for g in _merge_lines(list(zip(x[idx], y[idx], strict=True)), group_ppm)]
    return sorted(signals, key=lambda d: -d["ppm"])


def ppms(peaks: list) -> list[float]:
    """The ppm values of a peak list (dicts from `pick`, or plain numbers)."""
    return [d["ppm"] if isinstance(d, dict) else float(d) for d in peaks]


def compare(early: list, late: list, tol: float = 0.05) -> dict:
    """Which signals are kept, lost or new between two peak lists (dicts or plain ppm values)."""
    a, b = ppms(early), ppms(late)

    def has(lst, p):
        return any(abs(q - p) <= tol for q in lst)

    return {
        "kept": [p for p in a if has(b, p)],
        "lost": [p for p in a if not has(b, p)],
        "new": [p for p in b if not has(a, p)],
    }


def match(found: list, expected: list[float], tol: float = 0.05) -> dict:
    """Expected ppm values that are (and are not) in a peak list."""
    f = ppms(found)
    hit = [p for p in expected if any(abs(p - q) <= tol for q in f)]
    return {"found": hit, "missing": [p for p in expected if p not in hit]}


def linewidth_hz(s: Spectrum, center: float, half: float = 0.06) -> tuple[float, float]:
    """(position, full width at half height in Hz) of the tallest peak within center +/- half ppm."""
    m = (s.ppm > center - half) & (s.ppm < center + half)
    x, y = s.ppm[m], s.y[m]
    i = int(np.argmax(y))
    width_points = peak_widths(y, [i], rel_height=0.5)[0][0]
    return float(x[i]), float(width_points * abs(x[1] - x[0]) * s.sf)


def area(s: Spectrum, lo: float, hi: float) -> float:
    """Sum of intensity between lo and hi ppm (rough: these spectra were not run for exact areas)."""
    _, y = s.region(lo, hi)
    return float(y.sum())


def similarity(a: Spectrum, b: Spectrum, lo: float = 1.0, hi: float = 6.5) -> float:
    """Pearson correlation of two spectra within lo..hi ppm, on b's ppm grid."""
    m = (b.ppm >= lo) & (b.ppm <= hi)
    order = np.argsort(a.ppm)
    ya = np.interp(b.ppm[m], a.ppm[order], a.y[order])
    return float(np.corrcoef(ya, b.y[m])[0, 1])


# The acid's own peak (sulfuric acid and its water) sits between 11.4 and 12.1 ppm in these datasets.
ACID_AREA = (10.0, 13.0)


def _ratio(s: Spectrum, window: tuple, reference: tuple) -> float:
    """A peak's area against a reference peak's area in the same file (0 when the reference is empty)."""
    ref = area(s, *reference)
    return max(area(s, *window) / ref, 0.0) if ref > 0 else 0.0


def _fraction_of_first(ratios: list[float]) -> list[float]:
    """Each ratio as a fraction of the first one (1.0 at the first time point)."""
    return [r / ratios[0] if ratios[0] > 0 else 0.0 for r in ratios]


def against_acid(s: Spectrum, window: tuple, acid: tuple = ACID_AREA) -> float:
    """A peak's area (window, in ppm) divided by the acid peak's area in the same file.

    These samples have no internal standard, and raw areas cannot be compared between files (each
    file's intensity is scaled differently), so a peak is measured against the acid peak, which is
    the same in every file of a series."""
    return _ratio(s, window, acid)


def left_of_first(series: list, window: tuple, acid: tuple = ACID_AREA) -> list[float]:
    """How much is left at each time point: the peak against the acid peak, as a fraction of the
    same ratio in the first file of the series (1.0 at the first time point)."""
    return _fraction_of_first([against_acid(s, window, acid) for s in series])


# Below this fraction of day 1 (against the acid peak), a peak counts as lost.
CLEAR_LOSS_BELOW = 1 / 3


def left_band(fraction: float) -> str:
    """The two levels the steps use: under one third of day 1 is "little or none" (clear loss); one
    third or more is "no clear loss" (decide from the spectra). Survivors drift between about half
    and one and a half times their day 1 value against the acid peak, so only a fall below one third
    counts as loss."""
    return "no clear loss" if fraction >= CLEAR_LOSS_BELOW else "little or none"


def against_own_peak(series: list, window: tuple, other: tuple) -> list[float]:
    """One of the molecule's peaks (window, in ppm) against another of its own peaks (other) in the
    same file, as a fraction of the same ratio in the first file. This does not use the acid peak,
    which collects the hydrogens the sample hands over: a surviving molecule's peaks keep their
    sizes relative to each other."""
    return _fraction_of_first([_ratio(s, window, other) for s in series])


def second_peak_ppm(
    s: Spectrum, lo: float, hi: float, away_from: float, gap: float = 0.1, min_height: float = 0.03
) -> float | None:
    """The tallest signal between lo and hi ppm that sits at least `gap` ppm from `away_from`."""
    found = [p for p in pick(s, lo, hi, min_height) if abs(p["ppm"] - away_from) >= gap]
    return max(found, key=lambda p: p["height"])["ppm"] if found else None


def line_differences(
    mine: Spectrum, theirs: Spectrum, lo: float = 1.0, hi: float = 6.5, min_height: float = 0.03
) -> dict:
    """Compare two spectra line by line between lo and hi ppm. Each line of a split signal counts on
    its own (no grouping). For every line in `theirs`, the nearest line in `mine`; returns the
    largest of those distances, the line it belongs to, and how many lines were compared."""
    a = pick(theirs, lo, hi, min_height, group_ppm=0.0)
    b = pick(mine, lo, hi, min_height, group_ppm=0.0)
    if not a or not b:
        return {"largest_ppm": None, "at_ppm": None, "lines": 0}
    dist = [(min(abs(p["ppm"] - q["ppm"]) for q in b), p["ppm"]) for p in a]
    d, at = max(dist)
    return {"largest_ppm": round(d, 4), "at_ppm": at, "lines": len(a)}
