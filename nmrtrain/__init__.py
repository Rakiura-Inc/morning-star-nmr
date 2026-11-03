"""nmrtrain: the plumbing behind the Morning Star Missions NMR training notebooks.

The notebooks do the analysis in the open, with nmrglue, scipy, numpy and matplotlib: reading a
spectrum, processing a raw signal, picking peaks, measuring areas and stacking plots. This package
does the rest: it fetches and caches the public spectra (`data`), unpacks and labels them (`io`,
`names`), runs the trap checks and the feedback against published calls (`checks`, `answers`),
records answers and hand-ins (`record`) and connects to Rakiura (`portal`).
"""

__version__ = "0.1.0"

# The version is set before the submodules load: `data` reads it for its User-Agent.
from . import answers, checks, data, io, names, peaks, plot, portal, record
from .io import Spectrum

__all__ = [
    "Spectrum",
    "answers",
    "checks",
    "data",
    "io",
    "names",
    "peaks",
    "plot",
    "portal",
    "record",
]
