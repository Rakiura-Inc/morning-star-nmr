"""Stacked and zoomed plots. The ppm axis is always drawn high to low (NMR convention)."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

from .io import Spectrum
from .peaks import region_max

plt.rcParams.update({"figure.dpi": 100, "axes.spines.top": False, "axes.spines.right": False})


def colors(n: int):
    """n colours from the viridis map, dark to light (stopping short of its palest yellow)."""
    return plt.cm.viridis(np.linspace(0.0, 0.85, max(n, 1)))


def stack(
    spectra: list[Spectrum],
    lo: float = 0.0,
    hi: float = 13.0,
    norm: tuple | None = (1.0, 6.5),
    offset: float = 1.2,
    ax=None,
    title: str | None = None,
    labels: list[str] | None = None,
    shift: list[float] | None = None,
    legend: bool = True,
):
    """Traces stacked bottom to top in the order given.

    norm: the ppm region each trace is scaled to (its tallest point there becomes 1). None scales to
    the whole spectrum, which in this acid means scaling to the acid peak.
    shift: optional ppm shift per trace (for an alignment you chose yourself). Default: none; the
    instrument's ppm scale is kept.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 5))
    else:
        fig = ax.figure
    cs = colors(len(spectra))
    for i, s in enumerate(spectra):
        scale = region_max(s, *norm) if norm else float(np.max(s.y))
        dx = shift[i] if shift else 0.0
        ax.plot(
            s.ppm + dx, s.y / scale + offset * i, lw=0.8, color=cs[i], label=(labels[i] if labels else s.time_label)
        )
    ax.set_xlim(hi, lo)
    ax.set_ylim(-0.2, offset * (len(spectra) - 1) + 1.4)
    ax.set_yticks([])
    ax.set_xlabel("chemical shift (ppm)")
    if title:
        ax.set_title(title)
    if legend:
        h, lab = ax.get_legend_handles_labels()
        ax.legend(h[::-1], lab[::-1], frameon=False, fontsize=8, loc="upper left")
    return fig, ax


def mark(ax, peaks: list[dict], y0: float = 0.0, fmt: str = "{:.2f}") -> None:
    """Write each picked peak's ppm above it (peaks from `nmrtrain.peaks.pick`, heights 0..1)."""
    for d in peaks:
        ax.annotate(
            fmt.format(d["ppm"]),
            (d["ppm"], d["height"] + y0),
            xytext=(0, 5),
            textcoords="offset points",
            ha="center",
            fontsize=7.5,
            rotation=90,
        )


def compare(
    first: Spectrum,
    last: Spectrum,
    lo: float = 1.0,
    hi: float = 6.5,
    peaks_first=None,
    peaks_last=None,
    ax=None,
    title: str | None = None,
    offset: float = 1.15,
):
    """Two spectra (first at the bottom), scaled within lo..hi, with their picked peaks marked."""
    fig, ax = stack(
        [first, last],
        lo,
        hi,
        norm=(lo, hi),
        offset=offset,
        ax=ax,
        title=title or f"{first.sample_name}: {first.time_label} (bottom) vs {last.time_label} (top)",
    )
    if peaks_first:
        mark(ax, peaks_first, 0.0)
    if peaks_last:
        mark(ax, peaks_last, offset)
    ax.set_ylim(-0.1, offset + 1.6)
    return fig, ax


def explore(spectra: list[Spectrum], lo: float = 0.0, hi: float = 13.0, norm=(1.0, 6.5)):
    """An interactive stack (zoom, hover for ppm, click the legend to hide a trace). Needs plotly."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        print("The interactive view needs plotly: run  %pip install plotly  and then this cell again.")
        return None
    fig = go.Figure()
    for i, s in enumerate(spectra):
        scale = region_max(s, *norm) if norm else float(np.max(s.y))
        m = (s.ppm >= lo) & (s.ppm <= hi)
        fig.add_trace(
            go.Scattergl(x=s.ppm[m], y=s.y[m] / scale + 1.2 * i, name=s.label, mode="lines", line={"width": 1})
        )
    fig.update_xaxes(autorange="reversed", title="chemical shift (ppm)")
    fig.update_yaxes(showticklabels=False)
    fig.update_layout(height=500, margin={"l": 20, "r": 20, "t": 30, "b": 40})
    return fig


# The skeleton of a protonated dipeptide: atom -> (x, y, label), and bonds as (atom, atom, order).
# The alpha-carbon labels depend on the amino acid, so they are filled in by `_skeleton`.
_BACKBONE_ATOMS = {
    "N1": (0.0, 0.0, r"H$_3$N$^+$"),
    "A1": (1.3, 0.6, None),
    "C1": (2.6, 0.0, "C"),
    "O1": (2.6, -1.1, "O"),
    "N2": (3.9, 0.6, "NH"),
    "A2": (5.2, 0.0, None),
    "C2": (6.5, 0.6, "C"),
    "O2": (6.5, 1.7, "O"),
    "O3": (7.8, 0.0, "OH"),
}
_BACKBONE_BONDS = [
    ("N1", "A1", 1),
    ("A1", "C1", 1),
    ("C1", "O1", 2),
    ("C1", "N2", 1),
    ("N2", "A2", 1),
    ("A2", "C2", 1),
    ("C2", "O2", 2),
    ("C2", "O3", 1),
]
_ALANINE_METHYLS = {"S1": (1.3, 1.7, r"CH$_3$"), "S2": (5.2, -1.1, r"CH$_3$")}
_ALANINE_METHYL_BONDS = [("A1", "S1", 1), ("A2", "S2", 1)]
_ALPHA_LABEL = {"Ala": r"CH", "Gly": r"CH$_2$"}
_BOND_GAP = 0.07  # half the distance between the two lines of a double bond
_RING_COLOUR = "#E8590C"


def _skeleton(residue: str) -> tuple[dict, list]:
    """Atoms and bonds for Ala-Ala or Gly-Gly (any residue other than "Ala" is drawn as glycine)."""
    alpha = _ALPHA_LABEL["Ala" if residue == "Ala" else "Gly"]
    atoms = {name: (x, y, alpha if label is None else label) for name, (x, y, label) in _BACKBONE_ATOMS.items()}
    bonds = list(_BACKBONE_BONDS)
    if residue == "Ala":
        atoms.update(_ALANINE_METHYLS)
        bonds += _ALANINE_METHYL_BONDS
    return atoms, bonds


def _draw_bond(ax, start: tuple, end: tuple, order: int) -> None:
    (x1, y1, _), (x2, y2, _) = start, end
    dx, dy = x2 - x1, y2 - y1
    length = np.hypot(dx, dy)
    nx, ny = -dy / length * _BOND_GAP, dx / length * _BOND_GAP
    for k in [0] if order == 1 else [-1, 1]:
        ax.plot([x1 + k * nx, x2 + k * nx], [y1 + k * ny, y2 + k * ny], color="0.25", lw=1.4, zorder=1)


def draw_dipeptide(ax, residue: str, title: str, mark: dict | None = None, circle: dict | None = None) -> None:
    """Skeletal drawing of a protonated dipeptide. residue: "Ala" or "Gly".
    mark: optional {atom: (letter, colour)} to highlight proton environments
    (atoms: S1, S2 = methyls; A1, A2 = alpha carbons; C1, C2 = carbonyl carbons).
    circle: optional {atom: number}: a ring round each group of hydrogens on carbon, numbered."""
    atoms, bonds = _skeleton(residue)
    for a, b, order in bonds:
        _draw_bond(ax, atoms[a], atoms[b], order)
    for name, (x, y, label) in atoms.items():
        face = "white"
        if mark and name in mark:
            letter, face = mark[name]
            ax.text(x + 0.35, y + 0.32, letter, fontsize=11, weight="bold", color="0.1", zorder=3)
        ax.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=12,
            zorder=2,
            bbox={"boxstyle": "round,pad=0.25", "fc": face, "ec": "none"},
        )
    for name, number in (circle or {}).items():
        x, y, _ = atoms[name]
        ax.add_patch(Ellipse((x, y), 1.15, 0.85, fill=False, ec=_RING_COLOUR, lw=1.8, zorder=4))
        ax.text(x - 0.62, y + 0.42, str(number), fontsize=11, weight="bold", color=_RING_COLOUR, zorder=5)
    ax.set_title(title, fontsize=12)
    ax.set_xlim(-0.8, 8.6)
    ax.set_ylim(-1.7, 2.3)
    ax.set_aspect("equal")
    ax.axis("off")
