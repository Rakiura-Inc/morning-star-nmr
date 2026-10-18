"""Load Bruker experiments (one inner zip each) as `Spectrum` objects.

`load_processed` reads the spectrum the instrument already processed (`pdata/1`): the default for
every notebook except the raw-processing one. `load_fid` reads the raw signal (the FID) for
`nmrtrain.process`.

The ppm scale is the instrument's own. Nothing here re-references a spectrum to the acid peak:
that peak drifts over the months (see the README).
"""
from __future__ import annotations

import datetime as _dt
import glob
import os
import re
import warnings
import zipfile
from dataclasses import dataclass, field, replace

import numpy as np

warnings.filterwarnings("ignore", module="nmrglue")
import nmrglue as ng  # noqa: E402

from . import data as _data  # noqa: E402

ACID_PCT = {"K": "98%", "H": "81%"}
NAMES = {  # one- and three-letter codes used in the datasets
    "AA": "Ala-Ala", "CC": "Cys-Cys", "DD": "Asp-Asp", "EE": "Glu-Glu", "FF": "Phe-Phe", "GG": "Gly-Gly",
    "HH": "His-His", "II": "Ile-Ile", "KK": "Lys-Lys", "LL": "Leu-Leu", "MM": "Met-Met", "NN": "Asn-Asn",
    "PP": "Pro-Pro", "QQ": "Gln-Gln", "RR": "Arg-Arg", "SS": "Ser-Ser", "TT": "Thr-Thr", "VV": "Val-Val",
    "WW": "Trp-Trp", "YY": "Tyr-Tyr",
    "ALA": "alanine", "ARG": "arginine", "ASN": "asparagine", "ASP": "aspartic acid", "CYS": "cysteine",
    "GLN": "glutamine", "GLU": "glutamic acid", "GLY": "glycine", "HIS": "histidine", "ILE": "isoleucine",
    "LEU": "leucine", "LYS": "lysine", "MET": "methionine", "PHE": "phenylalanine", "PRO": "proline",
    "SER": "serine", "THR": "threonine", "TRP": "tryptophan", "TYR": "tyrosine", "VAL": "valine",
    "LAlaninamide": "L-alaninamide", "LGlycinamide": "L-glycinamide", "AA+A": "Ala-Ala + alanine",
}


def time_label(t: str) -> str:
    """'4Month' -> '4 months', '1day' -> '1 day', 'ref' -> 'reference'."""
    if t == "ref":
        return "reference"
    m = re.match(r"(\d+)\s*([A-Za-z]+?)(R?)$", t)
    if not m:
        return t
    n, unit, rep = int(m.group(1)), m.group(2).lower().rstrip("s"), m.group(3)
    return f"{n} {unit}{'s' if n != 1 else ''}" + (" (repeat)" if rep else "")


@dataclass
class Spectrum:
    ppm: np.ndarray            # chemical shift axis, high to low
    y: np.ndarray              # intensity (real part)
    sample: str = "?"
    acid: str = "?"
    time: str = "?"
    nucleus: str = "1H"
    acquired: _dt.datetime | None = None
    sf: float = 400.0          # spectrometer frequency in MHz (turns ppm into Hz)
    name: str = ""             # inner zip name
    folder: str = ""           # experiment folder name inside the zip
    expdir: str = ""
    processing: str = "pdata"  # "pdata" (instrument) or "raw" (processed here)
    meta: dict = field(default_factory=dict, repr=False)

    @property
    def sample_name(self) -> str:
        return NAMES.get(self.sample, self.sample)

    @property
    def time_label(self) -> str:
        return time_label(self.time)

    @property
    def label(self) -> str:
        acid = f" in {ACID_PCT[self.acid]}" if self.acid in ACID_PCT else ""
        return f"{self.sample_name}{acid}, {self.time_label}"

    def region(self, lo: float, hi: float) -> tuple[np.ndarray, np.ndarray]:
        m = (self.ppm >= lo) & (self.ppm <= hi)
        return self.ppm[m], self.y[m]

    def with_data(self, ppm, y, **changes) -> "Spectrum":
        return replace(self, ppm=np.asarray(ppm), y=np.asarray(y), **changes)


def _safe_extract(zip_path: str, out: str) -> None:
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = os.path.realpath(os.path.join(out, info.filename))
            if not target.startswith(os.path.realpath(out) + os.sep) and target != os.path.realpath(out):
                raise OSError(f"refusing to unpack {info.filename!r} outside the data folder")
        z.extractall(out)


def experiment_dir(zip_path: str) -> str:
    """Unpack one inner zip (once) and return the folder that holds `acqus`."""
    out = os.path.join(_data.data_dir(), "_unpacked", os.path.basename(zip_path)[:-4])
    found = sorted(glob.glob(os.path.join(out, "**", "acqus"), recursive=True))
    if not found:
        os.makedirs(out, exist_ok=True)
        _safe_extract(zip_path, out)
        found = sorted(glob.glob(os.path.join(out, "**", "acqus"), recursive=True))
    if not found:
        raise FileNotFoundError(f"{os.path.basename(zip_path)} holds no Bruker experiment (no acqus file)")
    return os.path.dirname(found[0])


def _meta_from(zip_path: str, nucleus: str | None) -> dict:
    m = _data.member_for(zip_path) or {}
    return {"sample": m.get("sample", "?"), "acid": m.get("acid", "?"), "time": m.get("time_group", "?"),
            "nucleus": m.get("nucleus", nucleus or "1H"), "name": os.path.basename(zip_path),
            "meta": {"record": m.get("record"), "time_in_name": m.get("time")}}


def _acquired(dic: dict) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromtimestamp(int(dic["acqus"]["DATE"]), tz=_dt.timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None


def load_processed(zip_path: str, **overrides) -> Spectrum:
    """The instrument-processed spectrum (`pdata/1`) of one experiment."""
    expdir = experiment_dir(zip_path)
    dic, y = ng.bruker.read_pdata(os.path.join(expdir, "pdata", "1"))
    uc = ng.fileiobase.uc_from_udic(ng.bruker.guess_udic(dic, y))
    info = {**_meta_from(zip_path, None), **overrides}
    return Spectrum(ppm=uc.ppm_scale(), y=np.asarray(y, dtype=float), acquired=_acquired(dic),
                    sf=float(dic["procs"]["SF"]), folder=os.path.basename(os.path.dirname(expdir)),
                    expdir=expdir, processing="pdata", **info)


def load_fid(zip_path: str) -> tuple[dict, np.ndarray, Spectrum]:
    """The raw FID: (Bruker parameters, complex FID, an empty Spectrum carrying the labels)."""
    expdir = experiment_dir(zip_path)
    dic, fid = ng.bruker.read(expdir)
    info = _meta_from(zip_path, None)
    template = Spectrum(ppm=np.array([]), y=np.array([]), acquired=_acquired(dic),
                        sf=float(dic["acqus"]["SFO1"]), folder=os.path.basename(os.path.dirname(expdir)),
                        expdir=expdir, processing="raw", **info)
    return dic, fid, template


def load_series(record: str, sample: str, acid: str | None = "K", nucleus: str = "1H",
                times="all", quiet: bool = False) -> list[Spectrum]:
    """Fetch and load one sample's time series (instrument-processed), first time point first."""
    return [load_processed(p) for p in _data.fetch(record, sample, acid, nucleus, times, quiet=quiet)]
