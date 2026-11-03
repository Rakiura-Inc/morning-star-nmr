"""Bridge to the Rakiura notebook helper (`rakiura`), with a local offline mode.

The helper is installed by each notebook's setup cell:

    %pip install -q "rakiura @ git+https://github.com/Rakiura-Inc/rakiura-py@main"

When it is installed and the member is signed in, the calls below go to the portal exactly as
the helper documents:

    rakiura.start(notebook=..., repo=...)   opens a run (notebook path, repository, commit, where)
    rakiura.done(part, figures, numbers)    ticks the checklist item the PI linked to that part
    rakiura.stage_text(text, title, step)   adds a small file (the verdict JSON) to a step
    rakiura.submit(note=...)                sends the step for review, only when the member asks

Which step a part counts toward is set in Rakiura (Settings > Notebook links), keyed by the
notebook path and the part name; the notebooks carry no Rakiura ids. Staging a file needs a step
id, which is configurable (see `steps()` and `notebooks/rakiura_steps.json`).

Without the helper, or when it is not signed in, offline mode keeps the same calls in
`handin/rakiura_progress.json` with the helper's own validation, and nothing leaves the computer.

Modes (environment variable RAKIURA_LIVE):
    unset  live if the helper is installed and a key is available without a click
           (RAKIURA_KEY, Colab's Secrets panel, or a key saved by an earlier sign-in); else offline.
           connect(..., sign_in=True), the notebooks' Connect cell, also signs in with one click.
    "1"    live; signs in with one click if needed (prints a link)
    "0"    offline, always (even for sign_in=True)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def quietly(call: Callable[[], T], default: T) -> T:
    """call(), or default if it raises anything at all.

    The one broad catch in the package: the Rakiura helper is optional and talks to the network,
    and whatever goes wrong there, the notebook keeps running in offline mode."""
    try:
        return call()
    except Exception:  # noqa: BLE001 (any failure in the optional helper falls back to offline mode)
        return default


DEFAULT_REPO = "Rakiura-Inc/morning-star-nmr"
_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
MAX_NUMBERS = 20
MAX_TEXT = 200  # characters kept of a text value in `numbers`
DEFAULT_CREDENTIALS = Path("~/.config/rakiura/credentials")


def _default_handin_dir() -> str:
    return str(Path(os.environ.get("NMRTRAIN_HANDIN", "handin")).resolve())


@dataclass
class _State:
    helper: Any = None  # the real `rakiura` module when live
    mode: str = "offline"
    notebook: str | None = None
    handin_dir: str = field(default_factory=_default_handin_dir)
    log: list = field(default_factory=list)
    last_part: str | None = None


state = _State()


_HELPER_CALLS = ("start", "done", "stage_text", "submit")


def _import_rakiura():
    import rakiura  # only there when the helper is installed

    return rakiura


def _import_helper():
    """The Rakiura helper when it is installed, else None (any other package named rakiura is ignored)."""
    rakiura = quietly(_import_rakiura, None)
    if rakiura is not None and all(callable(getattr(rakiura, name, None)) for name in _HELPER_CALLS):
        return rakiura
    return None


def _key_without_click(helper) -> bool:
    """A key is available without a click: RAKIURA_KEY, a Colab secret, or a saved sign-in."""
    if os.environ.get("RAKIURA_KEY") or quietly(helper._colab_secret, None):
        return True
    path = quietly(helper._credentials_path, None) or DEFAULT_CREDENTIALS.expanduser()
    return Path(path).exists()


def _steps_file() -> Path | None:
    """The first steps file found: $NMRTRAIN_STEPS, then ./rakiura_steps.json, notebooks/, the checkout."""
    candidates = [
        os.environ.get("NMRTRAIN_STEPS"),
        "rakiura_steps.json",
        Path("notebooks", "rakiura_steps.json"),
        Path(__file__).parent.parent / "notebooks" / "rakiura_steps.json",
    ]
    return next((Path(c) for c in candidates if c and Path(c).exists()), None)


def steps(notebook: str | None = None) -> dict:
    """Step ids for staging files, from $NMRTRAIN_STEPS or notebooks/rakiura_steps.json.

    Returns {"project": ..., "step": ...} for one notebook (by file name), or the whole file.
    $RAKIURA_STEP overrides the step for the current notebook.
    """
    path = _steps_file()
    conf: dict = json.loads(path.read_text()) if path else {}
    if notebook is None:
        return conf
    entry = dict(conf.get("notebooks", {}).get(Path(notebook).name, {}))
    if os.environ.get("RAKIURA_STEP"):
        entry["step"] = os.environ["RAKIURA_STEP"]
    return entry


NOT_CONNECTED = "Not connected to Rakiura. Your work stays on this computer."


def connect(notebook: str, repo: str = DEFAULT_REPO, handin_dir: str | None = None, sign_in: bool = False) -> str:
    """Start this notebook's session. Returns "live" or "offline". Never raises.

    By default it connects only when that needs no click (see the module notes), so the setup cell
    never waits. ``sign_in=True`` (the Connect cell) also runs the helper's sign-in: it prints a
    link, the member checks the code and clicks Allow. RAKIURA_LIVE=0 keeps both offline.
    """
    try:
        return _connect(notebook, repo, handin_dir, sign_in)
    except Exception:  # noqa: BLE001 (never stop a notebook over the connection)
        state.helper, state.mode = None, "offline"
        print(NOT_CONNECTED)
        return "offline"


def _start_live(helper, notebook: str, repo: str, loud: bool) -> bool:
    """Open a run through the helper. Quiet unless a sign-in link may be needed."""
    try:
        return bool(helper.start(notebook=notebook, repo=repo, quiet=not loud))
    except Exception:  # noqa: BLE001 (a failed start means offline mode, never a stopped notebook)
        return False
    finally:
        _speak(helper)


def _connect(notebook: str, repo: str, handin_dir: str | None, sign_in: bool) -> str:
    state.notebook = notebook
    if handin_dir:
        state.handin_dir = str(Path(handin_dir).resolve())
    Path(state.handin_dir).mkdir(parents=True, exist_ok=True)
    flag = os.environ.get("RAKIURA_LIVE")
    helper = None if flag == "0" else _import_helper()
    wants_live = sign_in or flag == "1"
    can_try = helper is not None and (wants_live or _key_without_click(helper))
    if can_try and _start_live(helper, notebook, repo, loud=wants_live):
        state.helper, state.mode = helper, "live"
        name = _member_name(helper)
        print(f"Connected to Rakiura as {name}." if name else "Connected to Rakiura.")
        return "live"
    state.helper, state.mode = None, "offline"
    if sign_in and helper is None and flag != "0":
        print(NOT_CONNECTED + " The Rakiura helper is not installed: run the setup cell above, then this cell again.")
    elif sign_in:
        print(NOT_CONNECTED + " Run this cell again to try once more, or attach your files on the step page.")
    else:
        print(NOT_CONNECTED + " Run the Connect cell below to tick steps on Rakiura.")
    return "offline"


def _speak(helper) -> None:
    """Let the helper print its own lines again (ticks, staged files) after a quiet start."""

    def unmute():
        helper._session.quiet = False

    quietly(unmute, None)


def _member_name(helper) -> str | None:
    """The signed-in member's name, asked quietly; None if it cannot be had. Never the key."""

    def ask():
        helper._session.quiet = True
        name = ((helper.me(show=False) or {}).get("member") or {}).get("name")
        return name if isinstance(name, str) and name.strip() else None

    try:
        return quietly(ask, None)
    finally:
        _speak(helper)


def go_live(notebook: str | None = None, repo: str = DEFAULT_REPO) -> str:
    """Sign in now (one click) and switch this session to live. Same as the Connect cell."""
    return connect(notebook or state.notebook or "notebook.ipynb", repo, sign_in=True)


def _log_path() -> Path:
    return Path(state.handin_dir, "rakiura_progress.json")


def _clean_numbers(numbers: dict | None) -> dict | None:
    """Named single values as the portal takes them, or None if any value is not one (or too many).
    An answer left empty (None or "") is sent as "blank"."""
    clean = {}
    for name, value in (numbers or {}).items():
        if hasattr(value, "item"):
            value = value.item()  # a numpy scalar becomes a Python one
        if value is None or value == "":
            value = "blank"
        if not isinstance(value, (bool, int, float, str)):
            return None
        clean[str(name)] = value[:MAX_TEXT] if isinstance(value, str) else value
    return clean if len(clean) <= MAX_NUMBERS else None


def _offline_log(entry: dict) -> None:
    state.log.append({**entry, "at": dt.datetime.now().isoformat(timespec="seconds")})
    Path(state.handin_dir).mkdir(parents=True, exist_ok=True)
    _log_path().write_text(json.dumps(state.log, indent=2))


def _done_problem(part: str, figures: list, clean: dict | None) -> str | None:
    """Why a tick cannot be sent, in one line, or None when it can."""
    if not isinstance(part, str) or not _PART.match(part):
        return 'rakiura: a part name is letters, digits and . _ : - (for example "part-2").'
    if clean is None:
        return f"rakiura: numbers takes up to {MAX_NUMBERS} named single values, never a table or an array."
    if any(not getattr(figure, "axes", None) for figure in figures):
        return "rakiura: that figure is empty; pass the figure you drew on (fig, ax = plt.subplots())."
    return None


def done(part: str, figures: list | None = None, numbers: dict | None = None) -> None:
    """Tick a part. Live: rakiura.done(...). Offline: one line in the local log.

    Returns None, so a cell can end with it and print only its one line; `state.last_part` says
    whether the tick went through."""
    figures = list(figures or [])
    clean = _clean_numbers(numbers)
    problem = _done_problem(part, figures, clean)
    if problem:
        print(problem)
        return
    state.last_part = part
    if state.mode == "live":
        state.helper.done(part, figures=figures or None, numbers=clean or None)
        return
    _offline_log({"part": part, "figures": len(figures), "numbers": clean})
    print(f"{saved_words(part)} (offline mode: kept on this computer).")


# What a member reads when a part is ticked. The part name itself stays internal (the portal keys on it).
_SAVED = {
    "predict": "Prediction saved",
    "stack": "Stacked plot saved",
    "compare": "Comparison saved",
    "verdict": "Hand-in saved",
    "overlay": "Overlay saved",
}


def saved_words(part: str) -> str:
    """What a member reads when a part is ticked, from the part name's last word."""
    return _SAVED.get(part.rsplit("-", 1)[-1], "Progress saved")


def stage_file(text: str, title: str, mime: str = "text/plain") -> bool:
    """Add a small text file (up to 50 KB) to this notebook's step, when a step id is configured."""
    step = steps(state.notebook or "").get("step")
    if state.mode == "live" and step:
        return bool(state.helper.stage_text(text, title, step=step, mime=mime))
    if state.mode == "live":
        print(f"rakiura: no step id is set for this notebook, so attach {title} on the step page.")
        return False
    _offline_log({"staged": title, "bytes": len(text.encode()), "step": step})
    return True


def submit(note: str | None = None) -> bool:
    """Send the step for review. Only ever called by the member, explicitly."""
    if state.mode == "live":
        return bool(state.helper.submit(note=note))
    print("Offline mode: nothing was sent. When you are connected to Rakiura, this sends your step for review.")
    return False
