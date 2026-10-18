"""nmrtrain: the plumbing behind the Morning Star Missions NMR training notebooks.

Library for plumbing, notebook for judgment: this package finds and loads the spectra, fixes
the axis direction once, draws the plots and runs the checks. Choosing what to compare, reading
the peaks and making the call stay in the notebooks.
"""

__version__ = "0.1.0"

from . import data, io, process, peaks, plot, checks, answers, portal, record  # noqa: E402,F401
from .io import Spectrum, load_processed, load_fid, load_series  # noqa: E402,F401
