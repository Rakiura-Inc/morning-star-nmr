"""Execute every notebook end to end (headless) and save executed copies in notebooks/executed/.

    python scripts/run_notebooks.py              # all notebooks
    python scripts/run_notebooks.py 01 03        # some of them

Runs from the notebooks/ folder, so the data cache (nmr_data/) and hand-ins (handin/) land there
(both gitignored). The member cells are left as committed (blank answers), so the run shows what
a member sees on a first pass.
"""
import glob
import os
import sys
import time

import nbformat
from nbclient import NotebookClient

HERE = os.path.dirname(os.path.abspath(__file__))
NB_DIR = os.path.join(HERE, "..", "notebooks")
OUT = os.path.join(NB_DIR, "executed")


def main(selected):
    os.makedirs(OUT, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(NB_DIR, "[0-9][0-9]_*.ipynb")))
    if selected:
        paths = [p for p in paths if any(os.path.basename(p).startswith(s) for s in selected)]
    results = []
    for path in paths:
        nb = nbformat.read(path, as_version=4)
        t0 = time.monotonic()
        NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": NB_DIR}}).execute()
        dt = time.monotonic() - t0
        errors = [o for c in nb.cells if c.cell_type == "code" for o in c.get("outputs", [])
                  if o.get("output_type") == "error"]
        out = os.path.join(OUT, os.path.basename(path).replace(".ipynb", ".executed.ipynb"))
        nbformat.write(nb, out)
        results.append((os.path.basename(path), dt, len(errors)))
        print(f"{os.path.basename(path):45s} {dt:6.1f} s   errors: {len(errors)}", flush=True)
    return 1 if any(e for _, _, e in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
