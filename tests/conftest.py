import os
import shutil
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import nmrtrain as nt  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
AA_1DAY = "SZSSea-AA-K-1day-1H-07212023_2.zip"   # Zenodo 11223995 (CC BY 4.0), see fixtures/README.md


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own data cache and hand-in folder, and never touches the network or Rakiura."""
    monkeypatch.setenv("NMRTRAIN_DATA", str(tmp_path / "nmr_data"))
    monkeypatch.setenv("NMRTRAIN_MIN_INTERVAL", "0")
    monkeypatch.setenv("RAKIURA_LIVE", "0")
    monkeypatch.delenv("NMRTRAIN_LOCAL", raising=False)
    monkeypatch.delenv("RAKIURA_KEY", raising=False)
    nt.data._local_index.cache_clear()
    nt.portal.state.handin_dir = str(tmp_path / "handin")
    nt.portal.state.log = []
    nt.portal.state.mode, nt.portal.state.helper = "offline", None
    monkeypatch.chdir(tmp_path)
    yield


@pytest.fixture
def aa_zip(tmp_path):
    dest = tmp_path / AA_1DAY
    shutil.copyfile(os.path.join(FIXTURES, AA_1DAY), dest)
    return str(dest)


def synthetic(peaks, sample="AA", acid="K", time="1day", lo=-1.0, hi=13.0, n=14000, width=0.004, acid_ppm=11.45,
              acid_height=20.0, nucleus="1H", sf=400.0):
    """A Lorentzian spectrum: peaks = [(ppm, height)], plus the acid peak."""
    ppm = np.linspace(hi, lo, n)
    y = np.zeros_like(ppm)
    for c, h in list(peaks) + ([(acid_ppm, acid_height)] if acid_ppm is not None else []):
        y += h / (1 + ((ppm - c) / width) ** 2)
    return nt.Spectrum(ppm=ppm, y=y, sample=sample, acid=acid, time=time, nucleus=nucleus, sf=sf)
