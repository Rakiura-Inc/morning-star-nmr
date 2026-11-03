"""Execute every notebook end to end (headless) and save executed copies in notebooks/executed/.

    uv run scripts/run_notebooks.py              # all notebooks
    uv run scripts/run_notebooks.py 01 03        # some of them

Runs from the notebooks/ folder, so the data cache (nmr_data/) and hand-ins (handin/) land there
(both gitignored). The member cells are left as committed (blank answers), so the run shows what
a member sees on a first pass. Exits 1 if any cell raised an error.
"""

import sys
import time
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NB_DIR = Path(__file__).resolve().parent.parent / "notebooks"
OUT = NB_DIR / "executed"
CELL_TIMEOUT_S = 900


def error_count(nb) -> int:
    """How many code cells ended in an error."""
    return sum(
        1 for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", []) if o.get("output_type") == "error"
    )


def run(path: Path) -> int:
    """Execute one notebook, save its executed copy, print one line, return its error count."""
    nb = nbformat.read(path, as_version=4)
    t0 = time.monotonic()
    client = NotebookClient(
        nb, timeout=CELL_TIMEOUT_S, kernel_name="python3", resources={"metadata": {"path": str(NB_DIR)}}
    )
    client.execute()
    errors = error_count(nb)
    nbformat.write(nb, OUT / path.name.replace(".ipynb", ".executed.ipynb"))
    print(f"{path.name:45s} {time.monotonic() - t0:6.1f} s   errors: {errors}", flush=True)
    return errors


def main(selected: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = sorted(NB_DIR.glob("[0-9][0-9]_*.ipynb"))
    if selected:
        paths = [p for p in paths if p.name.startswith(tuple(selected))]
    errors = [run(p) for p in paths]
    return 1 if any(errors) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
