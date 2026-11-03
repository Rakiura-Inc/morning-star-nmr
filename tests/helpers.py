"""Shared test data: the fixture spectrum and a synthetic spectrum builder."""

from pathlib import Path

import numpy as np

import nmrtrain as nt

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
AA_1DAY = "SZSSea-AA-K-1day-1H-07212023_2.zip"  # Zenodo 11223995 (CC BY 4.0), see fixtures/README.md
NOTEBOOKS = sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb"))


def synthetic(
    peaks,
    sample="AA",
    acid="K",
    time="1day",
    lo=-1.0,
    hi=13.0,
    n=14000,
    width=0.004,
    acid_ppm=11.45,
    acid_height=20.0,
    nucleus="1H",
    sf=400.0,
):
    """A Lorentzian spectrum: peaks = [(ppm, height)], plus the acid peak."""
    ppm = np.linspace(hi, lo, n)
    y = np.zeros_like(ppm)
    for c, h in list(peaks) + ([(acid_ppm, acid_height)] if acid_ppm is not None else []):
        y += h / (1 + ((ppm - c) / width) ** 2)
    return nt.Spectrum(ppm=ppm, intensity=y, sample=sample, acid=acid, time=time, nucleus=nucleus, spectrometer_mhz=sf)


def notebook_functions(name):
    """The functions and constants a notebook defines in its own cells, as a namespace.

    Only top-level `def`s and ALL_CAPS constants with literal values are run, with the setup
    cell's imports, so the teaching code can be tested without running the notebook."""
    import ast
    import json

    import matplotlib.pyplot as plt
    import nmrglue as ng
    from scipy.signal import find_peaks, peak_widths

    path = next(p for p in NOTEBOOKS if p.name.startswith(name))
    namespace = {"nt": nt, "ng": ng, "np": np, "plt": plt, "find_peaks": find_peaks, "peak_widths": peak_widths}
    for cell in json.loads(path.read_text())["cells"]:
        source = "".join(cell["source"])
        if cell["cell_type"] != "code" or "%pip" in source:
            continue
        for node in ast.parse(source).body:
            is_constant = (
                isinstance(node, ast.Assign)
                and all(isinstance(t, ast.Name) and t.id.isupper() for t in node.targets)
                and _is_literal(node.value)
            )
            if isinstance(node, ast.FunctionDef) or is_constant:
                exec(compile(ast.Module([node], []), str(path), "exec"), namespace)  # noqa: S102 (our own notebooks)
    return namespace


def _is_literal(node):
    import ast

    try:
        ast.literal_eval(node)
    except ValueError:
        return isinstance(node, ast.BinOp)  # such as 1 / 3
    return True
