"""Bridge to the Rakiura notebook helper (`rakiura`), with a local offline mode.

When the real helper is installed and can sign in without a prompt, the calls below go to the
portal exactly as the helper documents:

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
           (RAKIURA_KEY, Colab's Secrets panel, or a key saved by an earlier sign-in); else offline
    "1"    live; signs in with one click if needed (prints a link)
    "0"    offline, always
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re

DEFAULT_REPO = "Rakiura-Inc/morning-star-nmr"
_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
MAX_NUMBERS = 20


class _State:
    helper = None          # the real `rakiura` module when live
    mode = "offline"
    notebook: str | None = None
    handin_dir = os.path.abspath(os.environ.get("NMRTRAIN_HANDIN", "handin"))
    log: list = []
    last_part: str | None = None


state = _State()


def _import_helper():
    try:
        import rakiura  # type: ignore
        return rakiura
    except ImportError:
        return None


def _key_without_click(helper) -> bool:
    if os.environ.get("RAKIURA_KEY"):
        return True
    try:
        if helper._colab_secret():
            return True
    except Exception:
        pass
    try:
        path = helper._credentials_path()
    except Exception:
        path = os.path.join(os.path.expanduser("~"), ".config", "rakiura", "credentials")
    return os.path.exists(path)


def steps(notebook: str | None = None) -> dict:
    """Step ids for staging files, from $NMRTRAIN_STEPS or notebooks/rakiura_steps.json.

    Returns {"project": ..., "step": ...} for one notebook (by file name), or the whole file.
    $RAKIURA_STEP overrides the step for the current notebook.
    """
    cands = [os.environ.get("NMRTRAIN_STEPS"), "rakiura_steps.json",
             os.path.join("notebooks", "rakiura_steps.json"),
             os.path.join(os.path.dirname(__file__), "..", "notebooks", "rakiura_steps.json")]
    conf: dict = {}
    for c in filter(None, cands):
        if os.path.exists(c):
            with open(c) as fh:
                conf = json.load(fh)
            break
    if notebook is None:
        return conf
    entry = dict(conf.get("notebooks", {}).get(os.path.basename(notebook), {}))
    if os.environ.get("RAKIURA_STEP"):
        entry["step"] = os.environ["RAKIURA_STEP"]
    return entry


def connect(notebook: str, repo: str = DEFAULT_REPO, handin_dir: str | None = None) -> str:
    """Start this notebook's session. Returns "live" or "offline". Never raises."""
    state.notebook = notebook
    if handin_dir:
        state.handin_dir = os.path.abspath(handin_dir)
    os.makedirs(state.handin_dir, exist_ok=True)
    flag = os.environ.get("RAKIURA_LIVE")
    helper = None if flag == "0" else _import_helper()
    if helper is not None and (flag == "1" or _key_without_click(helper)):
        try:
            if helper.start(notebook=notebook, repo=repo):
                state.helper, state.mode = helper, "live"
                return "live"
        except Exception as exc:  # the helper never raises, but be safe
            print(f"rakiura: {exc}")
        print("rakiura: could not connect, so this session runs in offline mode.")
    state.helper, state.mode = None, "offline"
    hint = ("" if helper is None else
            " To connect to Rakiura, run  nt.portal.go_live()")
    print(f"Offline mode: progress is kept in {os.path.relpath(_log_path())}.{hint}")
    return "offline"


def go_live(notebook: str | None = None, repo: str = DEFAULT_REPO) -> str:
    """Sign in now (one click) and switch this session to live."""
    os.environ["RAKIURA_LIVE"] = "1"
    return connect(notebook or state.notebook or "notebook.ipynb", repo)


def _log_path() -> str:
    return os.path.join(state.handin_dir, "rakiura_progress.json")


def _clean_numbers(numbers: dict | None):
    clean = {}
    for name, value in (numbers or {}).items():
        value = value.item() if hasattr(value, "item") else value
        if value is None:
            value = "blank"
        if not isinstance(value, (bool, int, float, str)):
            return None
        clean[str(name)] = value[:200] if isinstance(value, str) else value
    return clean if len(clean) <= MAX_NUMBERS else None


def _offline_log(entry: dict) -> None:
    state.log.append({**entry, "at": _dt.datetime.now().isoformat(timespec="seconds")})
    os.makedirs(state.handin_dir, exist_ok=True)
    with open(_log_path(), "w") as fh:
        json.dump(state.log, fh, indent=2)


def done(part: str, figures: list | None = None, numbers: dict | None = None) -> bool:
    """Tick a part. Live: rakiura.done(...). Offline: one line in the local log."""
    if not isinstance(part, str) or not _PART.match(part):
        print('rakiura: a part name is letters, digits and . _ : - (for example "part-2").')
        return False
    clean = _clean_numbers(numbers)
    if clean is None:
        print(f"rakiura: numbers takes up to {MAX_NUMBERS} named single values, never a table or an array.")
        return False
    figures = list(figures or [])
    if any(not getattr(f, "axes", None) for f in figures):
        print("rakiura: that figure is empty; pass the figure you drew on (fig, ax = plt.subplots()).")
        return False
    state.last_part = part
    if state.mode == "live":
        return bool(state.helper.done(part, figures=figures or None, numbers=clean or None))
    _offline_log({"part": part, "figures": len(figures), "numbers": clean})
    print(f"{saved_words(part)} (offline mode: kept on this computer).")
    return True


# What a member reads when a part is ticked. The part name itself stays internal (the portal keys on it).
_SAVED = {"predict": "Prediction saved", "stack": "Stacked plot saved", "compare": "Comparison saved",
          "verdict": "Hand-in saved", "overlay": "Overlay saved"}


def saved_words(part: str) -> str:
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
