"""The house style for every figure, and the molecule drawings.

The spectra themselves are plotted in the notebooks with plain matplotlib, so a member can change
those plots. This module only draws what is not the lesson: the dipeptide skeletons with their
groups circled or coloured.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

# Every figure in the notebooks: 100 dots per inch on screen, no box on the top and right.
plt.rcParams.update({"figure.dpi": 100, "axes.spines.top": False, "axes.spines.right": False})


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

# Fill colours for marking groups in a drawing (draw_dipeptide's `mark`).
PALE_ORANGE = "#f6c9a8"
PALE_BLUE = "#b9d7f0"
PALE_GREEN = "#c8e6c3"


def _skeleton(residue: str) -> tuple[dict, list]:
    """Atoms and bonds for Ala-Ala or Gly-Gly (any residue other than "Ala" is drawn as glycine)."""
    alpha_label = _ALPHA_LABEL["Ala"] if residue == "Ala" else _ALPHA_LABEL["Gly"]
    atoms = {}
    for name, (x, y, label) in _BACKBONE_ATOMS.items():
        atoms[name] = (x, y, label or alpha_label)  # the alpha carbons have no fixed label
    bonds = list(_BACKBONE_BONDS)
    if residue == "Ala":
        atoms.update(_ALANINE_METHYLS)
        bonds += _ALANINE_METHYL_BONDS
    return atoms, bonds


def _draw_bond(ax, start: tuple, end: tuple, order: int) -> None:
    """A single bond as one line, a double bond as two lines either side of the atoms' centres."""
    (x1, y1, _), (x2, y2, _) = start, end
    dx, dy = x2 - x1, y2 - y1
    length = np.hypot(dx, dy)
    # A step at right angles to the bond, half the gap between the two lines of a double bond.
    across_x, across_y = -dy / length * _BOND_GAP, dx / length * _BOND_GAP
    sides = [0] if order == 1 else [-1, 1]
    for side in sides:
        xs = [x1 + side * across_x, x2 + side * across_x]
        ys = [y1 + side * across_y, y2 + side * across_y]
        ax.plot(xs, ys, color="0.25", lw=1.4, zorder=1)


def draw_dipeptide(ax, residue: str, title: str, mark: dict | None = None, *, circle: dict | None = None) -> None:
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
