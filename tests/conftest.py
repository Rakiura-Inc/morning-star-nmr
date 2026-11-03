import shutil

import matplotlib
import pytest

import nmrtrain as nt

from .helpers import AA_1DAY, FIXTURES

matplotlib.use("Agg")


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
    nt.record._predictions.clear()
    nt.record._reveals.clear()
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def aa_zip(tmp_path):
    dest = tmp_path / AA_1DAY
    shutil.copyfile(FIXTURES / AA_1DAY, dest)
    return str(dest)
