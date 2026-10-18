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
    assert "nt.portal.go_live()" in capsys.readouterr().out
