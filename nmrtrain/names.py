"""The words the steps use, and the codes the datasets' file names use for the same things.

The steps say "glycine", "Ala-Ala" and "98% acid"; the Zenodo file names say GLY, AA and K. Every
function in the package that takes a sample or an acid accepts either, so a notebook never has to
use a code it was not taught.
"""

from __future__ import annotations

import csv
import re
from importlib import resources

# The datasets code the two acid strengths (w/w D2SO4 in D2O) as K and H in their file names.
ACID_STRENGTH = {"K": "98%", "H": "81%"}
ACID_WT_PCT = {"K": 98, "H": 81}


def _read_sample_names() -> dict[str, str]:
    """{code: name} from samples.csv (one row per sample code found in the three datasets)."""
    text = resources.files("nmrtrain").joinpath("samples.csv").read_text()
    return {row["code"]: row["name"] for row in csv.DictReader(text.splitlines())}


SAMPLE_NAMES = _read_sample_names()


def sample_name(code: str) -> str:
    """The name the steps use for a sample code: "GG" -> "Gly-Gly". Unknown codes come back as they are."""
    return SAMPLE_NAMES.get(code, code)


def sample_code(sample: str) -> str:
    """The file-name code for a sample, given its name or its code: "glycine" -> "GLY"."""
    for code, name in SAMPLE_NAMES.items():
        if name == sample:
            return code
    return sample


def acid_code(acid: str | None) -> str | None:
    """The file-name code for an acid, given "98%", "81%", a code, or None (both acids)."""
    for code, strength in ACID_STRENGTH.items():
        if strength == acid:
            return code
    return acid


# A time label in a file name: a number, a unit, and an R when the spectrum was run again ("4MonthR").
_TIME_LABEL = re.compile(r"(\d+)\s*([A-Za-z]+?)(R?)$")


def time_label(time: str) -> str:
    """A file name's time label in words: "4Month" -> "4 months", "1day" -> "1 day"."""
    if time == "ref":
        return "reference"
    found = _TIME_LABEL.match(time)
    if found is None:
        return time
    number = int(found.group(1))
    unit = found.group(2).lower().rstrip("s")
    if number != 1:
        unit += "s"
    words = f"{number} {unit}"
    if found.group(3):
        words += " (repeat)"
    return words
