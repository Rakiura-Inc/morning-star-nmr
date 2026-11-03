"""Silence nmrglue's warnings before anything reads a spectrum.

nmrglue warns about every Bruker file it reads (missing optional parameter files), which would bury
the lines a member needs to read. The notebooks call nmrglue themselves; importing nmrtrain first
(the setup cell does) puts this filter in place.
"""

import warnings

warnings.filterwarnings("ignore", module="nmrglue")
