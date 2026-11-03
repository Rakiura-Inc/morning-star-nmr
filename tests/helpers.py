"""Shared test data: the fixture spectrum and a synthetic spectrum builder."""

from pathlib import Path

import numpy as np

import nmrtrain as nt

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
AA_1DAY = "SZSSea-AA-K-1day-1H-07212023_2.zip"  # Zenodo 11223995 (CC BY 4.0), see fixtures/README.md
NOTEBOOKS = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"))


def synthetic(
    peaks,
    sample="AA",
    acid="K",
    time="1day",
    lo=-1.0,
    hi=13.0,
    n=14000,
    width=0.004,
    acid_ppm=11.45,
    acid_height=20.0,
    nucleus="1H",
    sf=400.0,
):
    """A Lorentzian spectrum: peaks = [(ppm, height)], plus the acid peak."""
    ppm = np.linspace(hi, lo, n)
    y = np.zeros_like(ppm)
    for c, h in list(peaks) + ([(acid_ppm, acid_height)] if acid_ppm is not None else []):
        y += h / (1 + ((ppm - c) / width) ** 2)
    return nt.Spectrum(ppm=ppm, y=y, sample=sample, acid=acid, time=time, nucleus=nucleus, sf=sf)
