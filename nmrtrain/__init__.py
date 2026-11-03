"""nmrtrain: the plumbing behind the Morning Star Missions NMR training notebooks.

Library for plumbing, notebook for judgment: this package finds and loads the spectra, fixes
the axis direction once, draws the plots and runs the checks. Choosing what to compare, reading
the peaks and making the call stay in the notebooks.
"""

__version__ = "0.1.0"

# The version is set before the submodules load: `data` reads it for its User-Agent.
from . import answers, checks, data, io, peaks, plot, portal, process, record
from .io import Spectrum, load_fid, load_processed, load_series

__all__ = [
    "Spectrum",
    "answers",
    "checks",
    "data",
    "io",
    "load_fid",
    "load_processed",
    "load_series",
    "peaks",
    "plot",
    "portal",
    "process",
    "record",
]
