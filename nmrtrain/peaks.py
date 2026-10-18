"""Peak picking and simple measurements on one spectrum."""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks, peak_widths

from .io import Spectrum


def region_max(s: Spectrum, lo: float = 1.0, hi: float = 6.5) -> float:
    _, y = s.region(lo, hi)
    return float(y.max()) if y.size else 1.0


def tallest_ppm(s: Spectrum, lo: float | None = None, hi: float | None = None) -> float:
    x, y = (s.ppm, s.y) if lo is None else s.region(lo, hi)
    return float(x[int(np.argmax(y))])


def pick(s: Spectrum, lo: float = 1.0, hi: float = 6.5, min_height: float = 0.03,
         prominence: float = 0.02, group_ppm: float = 0.03, ref: tuple | None = None) -> list[dict]:
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
    groups: list[list[tuple[float, float]]] = []
    for p, h in sorted(zip(x[idx], y[idx])):
        if groups and p - groups[-1][-1][0] < group_ppm:
            groups[-1].append((p, h))
        else:
            groups.append([(p, h)])
    out = [{"ppm": round(float(sum(p * h for p, h in g) / sum(h for _, h in g)), 3), "lines": len(g),
            "height": round(float(max(h for _, h in g)), 3)} for g in groups]
    return sorted(out, key=lambda d: -d["ppm"])


def ppms(peaks: list) -> list[float]:
    return [d["ppm"] if isinstance(d, dict) else float(d) for d in peaks]


def compare(early: list, late: list, tol: float = 0.05) -> dict:
    """Which signals are kept, lost or new between two peak lists (dicts or plain ppm values)."""
    a, b = ppms(early), ppms(late)

    def has(lst, p):
        return any(abs(q - p) <= tol for q in lst)

    return {"kept": [p for p in a if has(b, p)], "lost": [p for p in a if not has(b, p)],
            "new": [p for p in b if not has(a, p)]}


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
