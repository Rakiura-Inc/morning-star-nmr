"""The measurements the trap checks make on a spectrum.

The notebooks teach peak picking, comparing and areas in their own cells (`pick_peaks`,
`compare_peaks`, `peak_area`, and `peak_width_hz` for line widths), with scipy and numpy in
the open. The trap checks in `checks.py` need
the same measurements without reaching into a member's notebook, so they use this module.
`tests/test_notebook_methods.py` runs the notebooks' versions against these on the same spectra,
so the two stay in step: change both, or neither.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks, peak_widths

from .io import Spectrum

# Where the acid's own peak (sulfuric acid and its water) sits: 11.4 to 12.1 ppm in these datasets.
ACID_REGION_PPM = (10.0, 13.0)
READ_PPM = (1.0, 6.5)  # the hydrogens on carbon of the dipeptides sit in here
SAME_PEAK_PPM = 0.05  # two peaks this close, in two spectra of one sample, are the same peak
PROMINENCE = 0.02  # a line must stand this far (a share of the tallest) above its surroundings
GROUP_PPM = 0.03  # lines closer than this belong to one signal (a doublet's two lines are 0.016 apart)


def tallest_ppm(spectrum: Spectrum, low_ppm: float | None = None, high_ppm: float | None = None) -> float:
    """Position of the tallest point, in the whole spectrum or between two ppm values."""
    if low_ppm is None:
        ppm, intensity = spectrum.ppm, spectrum.intensity
    else:
        ppm, intensity = spectrum.region(low_ppm, high_ppm)
    return float(ppm[int(np.argmax(intensity))])


def _group_lines(lines: list[tuple[float, float]], group_ppm: float) -> list[list[tuple[float, float]]]:
    """Group (ppm, height) lines, low ppm first: a line closer than group_ppm to the one before
    joins its group."""
    groups = []
    previous_ppm = None
    for ppm, height in lines:
        if previous_ppm is not None and ppm - previous_ppm < group_ppm:
            groups[-1].append((ppm, height))
        else:
            groups.append([(ppm, height)])
        previous_ppm = ppm
    return groups


def _signal(lines: list[tuple[float, float]]) -> dict:
    """One signal from its lines: the height-weighted centre, the number of lines, the tallest line."""
    total_height = sum(height for _, height in lines)
    centre_ppm = sum(ppm * height for ppm, height in lines) / total_height
    tallest = max(height for _, height in lines)
    return {"ppm": round(float(centre_ppm), 3), "lines": len(lines), "height": round(float(tallest), 3)}


def pick_peaks(spectrum: Spectrum, low_ppm: float = 1.0, high_ppm: float = 6.5, min_height: float = 0.03) -> list[dict]:
    """Signals between two ppm values, high ppm first: [{"ppm", "lines", "height"}].

    min_height is a share of the tallest point in the region. Lines closer than GROUP_PPM merge into
    one signal, so a doublet counts once, at its height-weighted centre."""
    ppm, intensity = spectrum.region(low_ppm, high_ppm)
    heights = intensity / intensity.max()
    found, _ = find_peaks(heights, height=min_height, prominence=PROMINENCE)
    lines = sorted(zip(ppm[found], heights[found], strict=True))
    signals = [_signal(group) for group in _group_lines(lines, GROUP_PPM)]
    return signals[::-1]


def compare_peaks(first_ppm: list[float], last_ppm: list[float], tolerance_ppm: float = SAME_PEAK_PPM) -> dict:
    """Signals kept, lost and new between two lists of positions."""
    changes = {"kept": [], "lost": [], "new": []}
    for ppm in first_ppm:
        if any(abs(ppm - later) <= tolerance_ppm for later in last_ppm):
            changes["kept"].append(ppm)
        else:
            changes["lost"].append(ppm)
    for ppm in last_ppm:
        if not any(abs(ppm - earlier) <= tolerance_ppm for earlier in first_ppm):
            changes["new"].append(ppm)
    return changes


def linewidth_hz(spectrum: Spectrum, near_ppm: float, half_window_ppm: float = 0.06) -> float:
    """Full width at half height, in Hz, of the tallest point within near_ppm +/- half_window_ppm."""
    inside = (spectrum.ppm > near_ppm - half_window_ppm) & (spectrum.ppm < near_ppm + half_window_ppm)
    ppm, intensity = spectrum.ppm[inside], spectrum.intensity[inside]
    top = int(np.argmax(intensity))
    widths_in_points = peak_widths(intensity, [top], rel_height=0.5)[0]
    ppm_per_point = abs(ppm[1] - ppm[0])
    return float(widths_in_points[0] * ppm_per_point * spectrum.spectrometer_mhz)


def peak_area(spectrum: Spectrum, low_ppm: float, high_ppm: float) -> float:
    """Sum of intensity between two ppm values (rough: these spectra were not run for exact areas)."""
    _, intensity = spectrum.region(low_ppm, high_ppm)
    return float(intensity.sum())
