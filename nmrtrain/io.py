"""Load Bruker experiments (one inner zip each) as `Spectrum` objects.

`load_processed` reads the spectrum the instrument already processed (`pdata/1`): the default for
every notebook except the raw-processing one. `load_fid` reads the raw signal (the FID) for
`nmrtrain.process`.

The ppm scale is the instrument's own. Nothing here re-references a spectrum to the acid peak:
that peak drifts over the months (see the README).
"""

from __future__ import annotations

import datetime as _dt
import re
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from . import data as _data
from ._nmrglue import ng

ACID_PCT = {"K": "98%", "H": "81%"}
ACID_WT_PCT = {"K": 98, "H": 81}
# The sample codes used in the datasets' file names: two-letter homodipeptides, three-letter amino
# acids, and the mechanism study's reference compounds.
NAMES = {
    "AA": "Ala-Ala",
    "CC": "Cys-Cys",
    "DD": "Asp-Asp",
    "EE": "Glu-Glu",
    "FF": "Phe-Phe",
    "GG": "Gly-Gly",
    "HH": "His-His",
    "II": "Ile-Ile",
    "KK": "Lys-Lys",
    "LL": "Leu-Leu",
    "MM": "Met-Met",
    "NN": "Asn-Asn",
    "PP": "Pro-Pro",
    "QQ": "Gln-Gln",
    "RR": "Arg-Arg",
    "SS": "Ser-Ser",
    "TT": "Thr-Thr",
    "VV": "Val-Val",
    "WW": "Trp-Trp",
    "YY": "Tyr-Tyr",
    "ALA": "alanine",
    "ARG": "arginine",
    "ASN": "asparagine",
    "ASP": "aspartic acid",
    "CYS": "cysteine",
    "GLN": "glutamine",
    "GLU": "glutamic acid",
    "GLY": "glycine",
    "HIS": "histidine",
    "ILE": "isoleucine",
    "LEU": "leucine",
    "LYS": "lysine",
    "MET": "methionine",
    "PHE": "phenylalanine",
    "PRO": "proline",
    "SER": "serine",
    "THR": "threonine",
    "TRP": "tryptophan",
    "TYR": "tyrosine",
    "VAL": "valine",
    "OSulfLSer": "O-sulfoserine",
    "LAlaninamide": "L-alaninamide",
    "LGlycinamide": "L-glycinamide",
    "AA+A": "Ala-Ala + alanine",
}


# The steps say "glycine" and "98% acid"; the file names say GLY and K. `load_series` takes either.
SAMPLE_CODES = {name: code for code, name in NAMES.items()}
ACID_CODES = {pct: code for code, pct in ACID_PCT.items()}


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
    ppm: np.ndarray  # chemical shift axis, high to low
    y: np.ndarray  # intensity (real part)
    sample: str = "?"
    acid: str = "?"
    time: str = "?"
    nucleus: str = "1H"
    acquired: _dt.datetime | None = None
    sf: float = 400.0  # spectrometer frequency in MHz (turns ppm into Hz)
    name: str = ""  # inner zip name
    folder: str = ""  # experiment folder name inside the zip
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

    def with_data(self, ppm, y, **changes) -> Spectrum:
        return replace(self, ppm=np.asarray(ppm), y=np.asarray(y), **changes)


def _safe_extract(zip_path: str, out: Path) -> None:
    """Unpack a zip into out, refusing any member that would land outside it."""
    root = out.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if not (root / info.filename).resolve().is_relative_to(root):
                msg = f"refusing to unpack {info.filename!r} outside the data folder"
                raise OSError(msg)
        z.extractall(out)


def _acqus_files(folder: Path) -> list[str]:
    return sorted(str(p) for p in folder.rglob("acqus"))


def experiment_dir(zip_path: str) -> str:
    """Unpack one inner zip (once) and return the folder that holds `acqus`."""
    out = Path(_data.data_dir(), "_unpacked", Path(zip_path).name[: -len(".zip")])
    found = _acqus_files(out)
    if not found:
        out.mkdir(parents=True, exist_ok=True)
        _safe_extract(zip_path, out)
        found = _acqus_files(out)
    if not found:
        msg = f"{Path(zip_path).name} holds no Bruker experiment (no acqus file)"
        raise FileNotFoundError(msg)
    return str(Path(found[0]).parent)


def _meta_from(zip_path: str, nucleus: str | None) -> dict:
    """The labels for one experiment, read from the manifest entry that matches its file name."""
    m = _data.member_for(zip_path) or {}
    return {
        "sample": m.get("sample", "?"),
        "acid": m.get("acid", "?"),
        "time": m.get("time_group", "?"),
        "nucleus": m.get("nucleus", nucleus or "1H"),
        "name": Path(zip_path).name,
        "meta": {"record": m.get("record"), "time_in_name": m.get("time")},
    }


def _acquired(dic: dict) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromtimestamp(int(dic["acqus"]["DATE"]), tz=_dt.UTC)
    except (KeyError, TypeError, ValueError):
        return None


def load_processed(zip_path: str, **overrides) -> Spectrum:
    """The instrument-processed spectrum (`pdata/1`) of one experiment."""
    expdir = experiment_dir(zip_path)
    dic, y = ng.bruker.read_pdata(str(Path(expdir, "pdata", "1")))
    uc = ng.fileiobase.uc_from_udic(ng.bruker.guess_udic(dic, y))
    info = {**_meta_from(zip_path, None), **overrides}
    return Spectrum(
        ppm=uc.ppm_scale(),
        y=np.asarray(y, dtype=float),
        acquired=_acquired(dic),
        sf=float(dic["procs"]["SF"]),
        folder=Path(expdir).parent.name,
        expdir=expdir,
        processing="pdata",
        **info,
    )


def load_fid(zip_path: str) -> tuple[dict, np.ndarray, Spectrum]:
    """The raw FID: (Bruker parameters, complex FID, an empty Spectrum carrying the labels)."""
    expdir = experiment_dir(zip_path)
    dic, fid = ng.bruker.read(expdir)
    info = _meta_from(zip_path, None)
    template = Spectrum(
        ppm=np.array([]),
        y=np.array([]),
        acquired=_acquired(dic),
        sf=float(dic["acqus"]["SFO1"]),
        folder=Path(expdir).parent.name,
        expdir=expdir,
        processing="raw",
        **info,
    )
    return dic, fid, template


def load_series(
    record: str, sample: str, acid: str | None = "K", nucleus: str = "1H", times="all", quiet: bool = False
) -> list[Spectrum]:
    """Fetch and load one sample's time series (instrument-processed), first time point first.

    sample: the dataset's code ("GLY") or the name the steps use ("glycine").
    acid: "K" or "98%", "H" or "81%"; None for both.
    """
    sample = SAMPLE_CODES.get(sample, sample)
    acid = ACID_CODES.get(acid, acid)
    return [load_processed(p) for p in _data.fetch(record, sample, acid, nucleus, times, quiet=quiet)]
