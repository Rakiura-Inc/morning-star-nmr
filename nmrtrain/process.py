"""Turn a raw FID into a spectrum: the steps the instrument does, one function each.

The order (digital filter, line broadening, zero-fill, FFT, phase, reverse, baseline) is the one
the dry run proved against the instrument's own processing. Bruker spectra come out of the FFT
mirrored; `reverse` fixes that, and it is the only place in the package that touches direction.
"""
from __future__ import annotations

import warnings

import numpy as np

warnings.filterwarnings("ignore", module="nmrglue")
import nmrglue as ng  # noqa: E402

from .io import Spectrum, load_fid  # noqa: E402


def remove_digital_filter(dic: dict, fid: np.ndarray) -> np.ndarray:
    """Bruker's digital filter leaves a delay at the start of the FID; remove it."""
    return ng.bruker.remove_digital_filter(dic, fid)


def line_broaden(dic: dict, fid: np.ndarray, lb_hz: float = 0.5) -> np.ndarray:
    """Exponential smoothing; 0.5 Hz is what the instrument used for these spectra."""
    return ng.proc_base.em(fid, lb=lb_hz / float(dic["acqus"]["SW_h"]))


def zero_fill(fid: np.ndarray, size: int = 65536) -> np.ndarray:
    """Pad with zeros to `size` points: a finer ppm grid, no new information."""
    return ng.proc_base.zf_size(fid, size)


def fft(fid: np.ndarray) -> np.ndarray:
    return ng.proc_base.fft(fid)


def autophase(spec: np.ndarray) -> np.ndarray:
    """Automatic phase correction (ACME). Flips the sign if the peaks end up pointing down."""
    spec = ng.proc_autophase.autops(spec, "acme", disp=False)
    if abs(np.real(spec).min()) > np.real(spec).max():
        spec = -spec
    return spec


def reverse(spec: np.ndarray) -> np.ndarray:
    """Mirror the spectrum. Skip this and the acid peak lands near 0.6 ppm instead of 11.5."""
    return ng.proc_base.rev(spec)


def baseline(y: np.ndarray, order: int = 3, exclude_frac: float = 0.8) -> np.ndarray:
    """Subtract a smooth polynomial fitted to the quietest points (a simple baseline correction)."""
    y = np.asarray(y, dtype=float)
    x = np.linspace(-1, 1, y.size)
    keep = np.abs(y - np.median(y)) <= np.quantile(np.abs(y - np.median(y)), exclude_frac)
    coef = np.polynomial.polynomial.polyfit(x[keep], y[keep], order)
    return y - np.polynomial.polynomial.polyval(x, coef)


def ppm_axis(dic: dict, spec: np.ndarray) -> np.ndarray:
    uc = ng.fileiobase.uc_from_udic(ng.bruker.guess_udic(dic, spec))
    return uc.ppm_scale()


def process_fid(zip_path: str, *, reverse_axis: bool = True, size: int = 65536, lb_hz: float = 0.5,
                do_baseline: bool = True) -> Spectrum:
    """All the steps, in order. Returns a Spectrum on the same footing as `load_processed`."""
    dic, fid, template = load_fid(zip_path)
    fid = remove_digital_filter(dic, fid)
    fid = line_broaden(dic, fid, lb_hz)
    fid = zero_fill(fid, size)
    spec = autophase(fft(fid))
    if reverse_axis:
        spec = reverse(spec)
    y = np.real(spec)
    if do_baseline:
        y = baseline(y)
    return template.with_data(ppm_axis(dic, spec), y, processing="raw")
