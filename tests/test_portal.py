"""The hand-in path: offline mode, and live mode through the real `rakiura` helper (when installed)
against a fake portal on localhost. Nothing here touches the real Rakiura."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import matplotlib.pyplot as plt
import pytest

import nmrtrain as nt

KEY = "rknb_" + "b" * 64


def _fig():
    fig, ax = plt.subplots(figsize=(2, 2))
    ax.plot([0, 1], [0, 1])
    return fig


def test_offline_mode_logs_and_saves_files(tmp_path, capsys):
    assert nt.portal.connect("notebooks/01_capstone_ala_ala_vs_gly_gly.ipynb") == "offline"
    nt.record.predict("q", {"a": 1})
    assert nt.record.revealed("q")
    rec = nt.record.handin("capstone-verdict", figures={"stack": _fig()}, verdict={"AA": {"call": "unsure"}},
                           numbers={"AA_call": "unsure"}, question="q", traps=2)
    out = os.path.join(nt.portal.state.handin_dir, "capstone-verdict")
    assert os.path.exists(os.path.join(out, "stack.png"))
    saved = json.load(open(os.path.join(out, "verdict.json")))
    assert saved["predicted_before_reveal"] is True and saved["traps_flagged"] == 2
    log = json.load(open(os.path.join(nt.portal.state.handin_dir, "rakiura_progress.json")))
    assert log[0]["part"] == "capstone-verdict" and log[0]["numbers"]["AA_call"] == "unsure"
    assert rec["ppm_scale"].startswith("instrument")
    assert nt.portal.submit() is False   # offline mode never sends anything


def test_offline_ticks_print_plain_words_not_part_names(capsys):
    nt.portal.connect("notebooks/01_capstone_ala_ala_vs_gly_gly.ipynb")
    capsys.readouterr()
    assert nt.portal.done("capstone-predict")
    out = capsys.readouterr().out
    assert out.strip() == "Prediction saved (offline mode: kept on this computer)."
    log = json.load(open(os.path.join(nt.portal.state.handin_dir, "rakiura_progress.json")))
    assert log[-1]["part"] == "capstone-predict"   # the portal still gets the part name


def test_reveal_refuses_before_a_prediction(capsys):
    nt.record.predict("blank", {"a": ...})
    assert nt.record.revealed("blank") is False
    assert "prediction in the cell above first" in capsys.readouterr().out


def test_part_names_and_numbers_are_validated(capsys):
    nt.portal.connect("nb.ipynb")
    assert nt.portal.done("bad part!") is False
    assert nt.portal.done("ok", numbers={"x": [1, 2]}) is False
    assert nt.portal.done("ok", numbers={f"n{i}": i for i in range(21)}) is False
    assert nt.portal.done("ok", figures=[plt.figure()]) is False


def test_fill_keeps_the_notebook_running(capsys):
    assert nt.record.fill(..., (1.0, 6.5), "REGION") == (1.0, 6.5)
    assert "To do: REGION" in capsys.readouterr().out
    assert nt.record.fill((0.5, 9.5), (1.0, 6.5), "REGION") == (0.5, 9.5)


def test_replication_row_matches_the_schema():
    import csv
    row = nt.record.replication_row("LL", "K", {"call": "Degrades"}, ["1day", "4Month"], matches="unsure")
    here = os.path.dirname(__file__)
    with open(os.path.join(here, "..", "replication", "replications.csv")) as fh:
        header = next(csv.reader(fh))
    assert list(row) == header == nt.record.REPLICATION_COLUMNS
    assert row["verdict"] == "degrades" and row["acid_wt_pct"] == 98 and row["contributor"] == "Rakiura member"


def test_every_setup_cell_installs_the_helper_from_github():
    import glob
    here = os.path.dirname(__file__)
    line = '%pip install -q "rakiura @ git+https://github.com/Rakiura-Inc/rakiura-py@main"'
    for path in sorted(glob.glob(os.path.join(here, "..", "notebooks", "[0-9][0-9]_*.ipynb"))):
        setup = "".join(json.load(open(path))["cells"][1]["source"])
        assert line in setup and "morning-star-nmr@main" in setup, path


# --- the Connect cell, with a stand-in helper -------------------------------------------------

def _fake_helper(monkeypatch, start=True, name="Test Member", boom=False):
    import sys
    import types
    calls = []
    mod = types.ModuleType("rakiura")
    mod._session = types.SimpleNamespace(quiet=False)

    def _start(**kw):
        calls.append(("start", kw))
        if boom:
            raise RuntimeError("network down")
        return start

    mod.start = _start
    mod.me = lambda show=True: {"member": {"name": name}, "lab": {"name": "Lab"}}
    mod.done = mod.stage_text = mod.submit = lambda *a, **k: True
    mod._colab_secret = lambda: None
    mod._credentials_path = lambda: "/nonexistent/creds"
    monkeypatch.setitem(sys.modules, "rakiura", mod)
    monkeypatch.delenv("RAKIURA_LIVE", raising=False)
    return mod, calls


def test_setup_cell_does_not_start_a_sign_in_without_a_key(monkeypatch, capsys):
    _, calls = _fake_helper(monkeypatch)
    assert nt.portal.connect("nb.ipynb") == "offline"
    assert calls == []
    assert capsys.readouterr().out.strip() == ("Not connected to Rakiura. Your work stays on this computer. "
                                               "Run the Connect cell below to tick steps on Rakiura.")


def test_connect_cell_signs_in_and_names_the_member(monkeypatch, capsys):
    mod, calls = _fake_helper(monkeypatch)
    assert nt.portal.connect("nb.ipynb", sign_in=True) == "live"
    assert calls == [("start", {"notebook": "nb.ipynb", "repo": nt.portal.DEFAULT_REPO, "quiet": False})]
    out = capsys.readouterr().out
    assert out.strip() == "Connected to Rakiura as Test Member."
    assert "rknb_" not in out and mod._session.quiet is False


def test_setup_cell_connects_quietly_with_a_key(monkeypatch, capsys):
    _, calls = _fake_helper(monkeypatch)
    monkeypatch.setenv("RAKIURA_KEY", KEY)
    assert nt.portal.connect("nb.ipynb") == "live"
    assert calls[0][1]["quiet"] is True
    out = capsys.readouterr().out
    assert out.strip() == "Connected to Rakiura as Test Member." and KEY not in out


@pytest.mark.parametrize("kw", [{"start": False}, {"boom": True}])
def test_connect_cell_never_raises(monkeypatch, capsys, kw):
    _fake_helper(monkeypatch, **kw)
    assert nt.portal.connect("nb.ipynb", sign_in=True) == "offline"
    assert capsys.readouterr().out.startswith("Not connected to Rakiura. Your work stays on this computer.")
    assert nt.portal.state.mode == "offline"


def test_connect_cell_stays_offline_when_forced(monkeypatch, capsys):
    _, calls = _fake_helper(monkeypatch)
    monkeypatch.setenv("RAKIURA_LIVE", "0")
    assert nt.portal.connect("nb.ipynb", sign_in=True) == "offline"
    assert calls == []


def test_connect_cell_without_the_helper_says_what_to_do(monkeypatch, capsys):
    monkeypatch.setattr(nt.portal, "_import_helper", lambda: None)
    monkeypatch.delenv("RAKIURA_LIVE", raising=False)
    assert nt.portal.connect("nb.ipynb", sign_in=True) == "offline"
    assert "run the setup cell above" in capsys.readouterr().out


@pytest.mark.parametrize("path", sorted(__import__("glob").glob(
    os.path.join(os.path.dirname(__file__), "..", "notebooks", "[0-9][0-9]_*.ipynb"))), ids=os.path.basename)
def test_every_notebook_has_the_connect_cell_after_setup(path):
    cells = json.load(open(path))["cells"]
    box, code = "".join(cells[2]["source"]), "".join(cells[3]["source"])
    assert "nt.portal.connect(NOTEBOOK)" in "".join(cells[1]["source"])   # the setup cell never waits
    assert box.startswith("> **CONNECT TO RAKIURA (optional, recommended)**")
    for part in ("**What it does:**", "**How:**", "**Skipping it is fine:**", "Allow", "RAKIURA_KEY",
                 "once per session", "Nothing is sent until you connect"):
        assert part in box, part
    assert "nt.portal.connect(NOTEBOOK, sign_in=True)" in code


def test_another_package_named_rakiura_is_not_used(monkeypatch, capsys):
    import sys
    import types
    monkeypatch.setitem(sys.modules, "rakiura", types.ModuleType("rakiura"))
    monkeypatch.setenv("RAKIURA_LIVE", "1")
    assert nt.portal._import_helper() is None
    assert nt.portal.connect("nb.ipynb") == "offline"


# --- live mode through the real helper ---------------------------------------------------------

rakiura = pytest.importorskip("rakiura", reason="the Rakiura helper is not installed (see README)")


class Portal(BaseHTTPRequestHandler):
    received: list = []

    def log_message(self, *a):
        pass

    def _reply(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        Portal.received.append((self.path, None, self.headers.get("Authorization")))
        if self.path.endswith("/me"):
            return self._reply({"ok": True, "member": {"name": "Test Member"},
                                "lab": {"name": "Morning Star Missions"}, "deliverables": []})
        self._reply({"ok": False})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        Portal.received.append((self.path, body, self.headers.get("Authorization")))
        step = {"id": "d7", "displayId": "ONB-102-D7", "name": "Capstone", "url": "https://labs.example.test/s"}
        if self.path.endswith("/runs"):
            return self._reply({"ok": True, "run": {"id": "run-1"}, "lab": {"name": "Morning Star Missions"},
                                "member": {"name": "Test Member"},
                                "parts": [{"part": "capstone-verdict", "step": step}]})
        if self.path.endswith("/checkpoint"):
            return self._reply({"ok": True, "deliverable": step, "changed": True,
                                "item": {"key": body.get("checkpoint"), "label": "Verdict"},
                                "progress": {"done": 1, "total": 4}})
        if self.path.endswith("/artifacts"):
            return self._reply({"ok": True, "deliverable": step, "created": True,
                                "artifact": {"id": "a1", "title": body.get("title")}})
        if self.path.endswith("/submit"):
            return self._reply({"ok": True, "deliverable": step, "attached": 3})
        self._reply({"ok": False})


@pytest.fixture
def portal_server(tmp_path, monkeypatch):
    Portal.received = []
    httpd = HTTPServer(("127.0.0.1", 0), Portal)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setenv("RAKIURA_URL", f"http://127.0.0.1:{httpd.server_port}")
    monkeypatch.setenv("RAKIURA_KEY", KEY)
    monkeypatch.setenv("RAKIURA_CREDENTIALS", str(tmp_path / "creds"))
    monkeypatch.setenv("RAKIURA_NO_BROWSER", "1")
    monkeypatch.delenv("RAKIURA_LIVE", raising=False)
    steps = tmp_path / "steps.json"
    steps.write_text(json.dumps({"notebooks": {"01_capstone_ala_ala_vs_gly_gly.ipynb": {"step": "ONB-102-D7"}}}))
    monkeypatch.setenv("NMRTRAIN_STEPS", str(steps))
    rakiura.logout(forget=False)
    yield
    rakiura.logout(forget=False)
    httpd.shutdown()


def test_live_mode_ticks_stages_and_submits_through_the_helper(portal_server, capsys):
    assert nt.portal.connect("notebooks/01_capstone_ala_ala_vs_gly_gly.ipynb") == "live"
    assert capsys.readouterr().out.strip() == "Connected to Rakiura as Test Member."
    nt.record.handin("capstone-verdict", figures={"stack": _fig()}, verdict={"AA": {"call": "degrades"}},
                     numbers={"AA_call": "degrades"})
    paths = [p for p, _, _ in Portal.received]
    assert paths[0].endswith("/api/notebook/v1/runs")
    run = Portal.received[0][1]
    assert run["notebookPath"].endswith("01_capstone_ala_ala_vs_gly_gly.ipynb") and run["repo"]
    tick = next(b for p, b, _ in Portal.received if p.endswith("/checkpoint"))
    assert tick["checkpoint"] == "capstone-verdict" and tick["numbers"]["AA_call"] == "degrades"
    arts = [b for p, b, _ in Portal.received if p.endswith("/artifacts")]
    assert any(a.get("mimeType") == "image/png" and a.get("checkpoint") == "capstone-verdict" for a in arts)
    verdict = next(a for a in arts if a.get("mimeType") == "text/plain")
    assert verdict["deliverableRef"] == "ONB-102-D7" and "degrades" in verdict["fileText"]
    assert all(auth == f"Bearer {KEY}" for _, _, auth in Portal.received)
    assert not any(p.endswith("/submit") for p in paths)      # never submitted on its own
    assert nt.portal.submit(note="ready") is True
    sub = next(b for p, b, _ in Portal.received if p.endswith("/submit"))
    assert sub["checkpoint"] == "capstone-verdict" and sub["note"] == "ready"


def test_without_a_key_the_helper_is_not_asked_to_sign_in(monkeypatch, capsys):
    monkeypatch.delenv("RAKIURA_LIVE", raising=False)
    monkeypatch.setenv("RAKIURA_CREDENTIALS", "/nonexistent/creds")
    assert nt.portal.connect("nb.ipynb") == "offline"
    assert "Run the Connect cell below" in capsys.readouterr().out
