"""Unpack Bruker experiments and label what nmrglue reads from them.

Reading a spectrum is part of the lesson, so the notebooks call nmrglue themselves
(`ng.bruker.read_pdata`, `ng.bruker.read`, `ng.fileiobase.uc_from_udic`). This module does the
plumbing around those calls: it unpacks one inner zip into the data folder, and wraps what nmrglue
returns in a `Spectrum` that carries the sample, acid and time point from the dataset's manifest.

The ppm scale is the instrument's own. Nothing here re-references a spectrum to the acid peak:
that peak drifts over the months (see the README).
"""

from __future__ import annotations

import datetime as dt
import zipfile
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from . import _nmrglue  # noqa: F401 (silences nmrglue's warnings before the notebooks call it)
from . import data as _data
from .names import ACID_STRENGTH, sample_name, time_label


@dataclass
class Spectrum:
    """One spectrum: its ppm axis (high to low), its intensity, and where it came from."""

    ppm: np.ndarray
    intensity: np.ndarray  # the real part of the spectrum
    sample: str = "?"  # the dataset's code, such as "AA"; sample_name gives the words
    acid: str = "?"  # "K" (98%) or "H" (81%)
    time: str = "?"  # the time label in the file name, such as "4Month"
    nucleus: str = "1H"
    acquired: dt.datetime | None = None  # when the instrument recorded it
    spectrometer_mhz: float = 400.0  # turns ppm into Hz: 1 ppm is this many Hz
    name: str = ""  # the inner zip's file name
    folder: str = ""  # the experiment folder's name inside the zip
    experiment_folder: str = ""  # where the experiment is unpacked on this computer
    processing: str = "pdata"  # "pdata" (the instrument's) or "raw" (processed in the notebook)
    meta: dict = field(default_factory=dict, repr=False)

    @property
    def sample_name(self) -> str:
        return sample_name(self.sample)

    @property
    def time_label(self) -> str:
        return time_label(self.time)

    @property
    def label(self) -> str:
        """For example "Ala-Ala in 98%, 1 day"."""
        if self.acid in ACID_STRENGTH:
            return f"{self.sample_name} in {ACID_STRENGTH[self.acid]}, {self.time_label}"
        return f"{self.sample_name}, {self.time_label}"

    def region(self, low_ppm: float, high_ppm: float) -> tuple[np.ndarray, np.ndarray]:
        """The ppm values and intensities between two ppm values (both ends included)."""
        inside = (self.ppm >= low_ppm) & (self.ppm <= high_ppm)
        return self.ppm[inside], self.intensity[inside]

    def with_data(self, ppm, intensity, **changes) -> Spectrum:
        """The same labels with a new axis or intensity (for example after shifting the axis)."""
        return replace(self, ppm=np.asarray(ppm), intensity=np.asarray(intensity), **changes)


def _unpack(zip_path: str, out: Path) -> None:
    """Unpack a zip into out, refusing any member that would land outside it."""
    root = out.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if not (root / member.filename).resolve().is_relative_to(root):
                msg = f"refusing to unpack {member.filename!r} outside the data folder"
                raise OSError(msg)
        archive.extractall(out)


def _acqus_files(folder: Path) -> list[Path]:
    return sorted(folder.rglob("acqus"))


def experiment_folder(zip_path: str) -> str:
    """Unpack one inner zip (once) and return the experiment folder: the one that holds `acqus`.

    nmrglue reads the raw signal from this folder (`ng.bruker.read`) and the instrument's
    spectrum from its `pdata/1` subfolder (`ng.bruker.read_pdata`)."""
    out = Path(_data.data_dir(), "_unpacked", Path(zip_path).name.removesuffix(".zip"))
    found = _acqus_files(out)
    if not found:
        out.mkdir(parents=True, exist_ok=True)
        _unpack(zip_path, out)
        found = _acqus_files(out)
    if not found:
        msg = f"{Path(zip_path).name} holds no Bruker experiment (no acqus file)"
        raise FileNotFoundError(msg)
    return str(found[0].parent)


def _acquired(dic: dict) -> dt.datetime | None:
    """When the instrument recorded the experiment, from its acqus DATE (seconds since 1970)."""
    try:
        return dt.datetime.fromtimestamp(int(dic["acqus"]["DATE"]), tz=dt.UTC)
    except (KeyError, TypeError, ValueError):
        return None


def labelled(zip_path: str, dic: dict, ppm, data, *, processing: str = "pdata") -> Spectrum:
    """A Spectrum from what nmrglue read out of one experiment, with its labels from the manifest.

    dic: nmrglue's parameter dictionary. ppm: the axis. data: the spectrum (its real part is kept).
    processing: "pdata" for the instrument's spectrum, "raw" for one processed in the notebook."""
    member = _data.member_for(zip_path) or {}
    # The instrument's spectrum is scaled with procs SF; a raw signal was recorded at acqus SFO1.
    spectrometer_mhz = float(dic["procs"]["SF"]) if processing == "pdata" else float(dic["acqus"]["SFO1"])
    folder = experiment_folder(zip_path)
    return Spectrum(
        ppm=np.asarray(ppm),
        intensity=np.asarray(np.real(data), dtype=float),
        sample=member.get("sample", "?"),
        acid=member.get("acid", "?"),
        time=member.get("time_group", "?"),
        nucleus=member.get("nucleus", "1H"),
        acquired=_acquired(dic),
        spectrometer_mhz=spectrometer_mhz,
        name=Path(zip_path).name,
        folder=Path(folder).parent.name,
        experiment_folder=folder,
        processing=processing,
        meta={"record": member.get("record"), "time_in_name": member.get("time")},
    )


def label_of(zip_path: str) -> str:
    """The words for one downloaded file, before it is read: "Ala-Ala in 98%, 1 day"."""
    member = _data.member_for(zip_path) or {}
    empty = np.array([])
    spectrum = Spectrum(
        empty, empty, sample=member.get("sample", "?"), acid=member.get("acid", "?"), time=member.get("time_group", "?")
    )
    return spectrum.label


def _recording_date(spectrum: Spectrum) -> dt.datetime:
    return spectrum.acquired


def by_recording_date(spectra: list[Spectrum]) -> list[Spectrum]:
    """The spectra in the order the instrument recorded them, first first."""
    return sorted(spectra, key=_recording_date)
