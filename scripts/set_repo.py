"""Publishing helper: rename the repository everywhere it appears, and pin the notebooks' install line.

    uv run scripts/set_repo.py OWNER/NAME             # replace the current name everywhere
    uv run scripts/set_repo.py OWNER/NAME --pin SHA   # also pin the notebooks' %pip install to a commit

The current name is Rakiura-Inc/morning-star-nmr (see README, "Publishing"). After a rename,
update CURRENT below to the new name.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CURRENT = "Rakiura-Inc/morning-star-nmr"
FILES = [
    ROOT / "README.md",
    ROOT / "CITATION.cff",
    ROOT / "nmrtrain" / "portal.py",
    ROOT / "nmrtrain" / "data.py",
    *sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.ipynb")),
]
FULL_SHA = re.compile(r"[0-9a-f]{40}")


def renamed(text: str, repo: str, pin: str | None) -> str:
    """text with the repository renamed and, when pin is set, its git install lines pinned to it."""
    new = text.replace(CURRENT, repo)
    if pin:
        new = re.sub(r"(git\+https://github\.com/" + re.escape(repo) + r")@[0-9A-Za-z._-]+", r"\1@" + pin, new)
    return new


def main(argv: list[str]) -> None:
    if not argv or "/" not in argv[0]:
        raise SystemExit(__doc__)
    repo = argv[0]
    pin = argv[argv.index("--pin") + 1] if "--pin" in argv else None
    if pin and not FULL_SHA.fullmatch(pin):
        msg = "--pin takes a full 40-character commit SHA"
        raise SystemExit(msg)
    for path in FILES:
        text = path.read_text()
        new = renamed(text, repo, pin)
        if new != text:
            path.write_text(new)
            print("updated", path.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
