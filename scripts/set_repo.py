"""Publishing helper: rename the repository everywhere it appears, and pin the notebooks' install line.

    python scripts/set_repo.py OWNER/NAME             # replace the current name everywhere
    python scripts/set_repo.py OWNER/NAME --pin SHA   # also pin the notebooks' %pip install to a commit

The current name is Rakiura-Inc/morning-star-nmr (see README, "Publishing"). After a rename,
update CURRENT below to the new name.
"""
import glob
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CURRENT = "Rakiura-Inc/morning-star-nmr"
FILES = (["README.md", "CITATION.cff", "nmrtrain/portal.py", "nmrtrain/data.py"]
         + glob.glob(os.path.join(ROOT, "notebooks", "[0-9][0-9]_*.ipynb")))


def main(argv):
    if not argv or "/" not in argv[0]:
        raise SystemExit(__doc__)
    repo = argv[0]
    pin = argv[argv.index("--pin") + 1] if "--pin" in argv else None
    if pin and not re.fullmatch(r"[0-9a-f]{40}", pin):
        raise SystemExit("--pin takes a full 40-character commit SHA")
    for f in FILES:
        path = f if os.path.isabs(f) else os.path.join(ROOT, f)
        text = open(path).read()
        new = text.replace(CURRENT, repo)
        if pin:
            new = re.sub(r"(git\+https://github\.com/" + re.escape(repo) + r")@[0-9A-Za-z._-]+", r"\1@" + pin, new)
        if new != text:
            open(path, "w").write(new)
            print("updated", os.path.relpath(path, ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
