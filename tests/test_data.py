"""Fetching: manifest selection, one range request per spectrum, CRC checks, cache, fallbacks."""
import io
import os
import re
import threading
import zipfile
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import nmrtrain as nt
from conftest import AA_1DAY, FIXTURES


def test_manifests_cover_the_three_records():
    for rec, n in (("11223995", 398), ("8381013", 160), ("11122291", 12)):
        assert len(nt.data.manifest(rec)["members"]) == n


def test_select_returns_time_order_not_name_order():
    rows = nt.data.select("11223995", "AA", "K", "1H")
    assert [r["time_group"] for r in rows] == ["1day", "3day", "8day", "5week", "4Month"]
    assert sorted(r["time_group"] for r in rows) != [r["time_group"] for r in rows]  # the trap is real


def test_select_handles_gaps_and_odd_names():
    assert "4Month" not in [r["time_group"] for r in nt.data.select("11223995", "QQ", "K")]
    arg = nt.data.select("8381013", "ARG", "K", "1H", times=["1month"])
    assert len(arg) == 1 and arg[0]["name"].startswith("SZSSea-ARG-1month")  # named "13H" in the archive
    assert [r["time_group"] for r in nt.data.select("8381013", "ASN", "H")] == ["1day", "1week", "1month"]
    with pytest.raises(LookupError):
        nt.data.select("11223995", "ZZ", "K")


def test_doi_is_accepted_as_record():
    assert nt.data.select("10.5281/zenodo.11223995", "GG", "K", times="1day")[0]["sample"] == "GG"


# --- a fake Zenodo serving a small archive that holds the fixture ------------------------------


def _archive(tmp_path):
    inner = open(os.path.join(FIXTURES, AA_1DAY), "rb").read()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("readme.txt", "padding " * 100)
        z.writestr(f"Suplementary dataset S1/{AA_1DAY}", inner)
    data = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        zi = z.getinfo(f"Suplementary dataset S1/{AA_1DAY}")
    member = {"path": zi.filename, "name": AA_1DAY, "offset": zi.header_offset, "compress_size": zi.compress_size,
              "size": zi.file_size, "compress_type": 0, "crc": zi.CRC, "sample": "AA", "acid": "K",
              "time": "1day", "time_group": "1day", "nucleus": "1H", "repeat": False}
    return data, member


class Zenodo(BaseHTTPRequestHandler):
    data = b""
    ranges = True
    requests: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        Zenodo.requests.append(self.headers.get("Range"))
        rng = self.headers.get("Range")
        if rng and Zenodo.ranges:
            a, b = map(int, re.match(r"bytes=(\d+)-(\d+)", rng).groups())
            b = min(b, len(self.data) - 1)
            body = self.data[a:b + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(self.data)}")
        else:
            body = self.data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_zenodo(tmp_path, monkeypatch):
    data, member = _archive(tmp_path)
    Zenodo.data, Zenodo.ranges, Zenodo.requests = data, True, []
    httpd = HTTPServer(("127.0.0.1", 0), Zenodo)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_port}/archive.zip"
    monkeypatch.setattr(nt.data, "_record_file_url", lambda record: url)
    monkeypatch.setitem(nt.data.RECORDS["11223995"], "size", len(data))
    yield member
    httpd.shutdown()


def test_one_range_request_per_spectrum_then_cache(fake_zenodo, capsys):
    path = nt.data.fetch_member("11223995", fake_zenodo)
    assert os.path.getsize(path) == fake_zenodo["size"]
    assert len(Zenodo.requests) == 1 and Zenodo.requests[0].startswith("bytes=")
    nt.data.fetch_member("11223995", fake_zenodo)
    assert len(Zenodo.requests) == 1  # cached, CRC verified, no second request


def test_a_changed_archive_is_never_trusted(fake_zenodo):
    bad = dict(fake_zenodo, crc=(fake_zenodo["crc"] + 1) & 0xFFFFFFFF)
    with pytest.raises(OSError):
        nt.data.fetch_member("11223995", bad)


def test_falls_back_to_the_whole_archive_when_ranges_are_refused(fake_zenodo, capsys):
    Zenodo.ranges = False
    path = nt.data.fetch_member("11223995", fake_zenodo)
    assert zlib.crc32(open(path, "rb").read()) & 0xFFFFFFFF == fake_zenodo["crc"]
    assert "whole archive" in capsys.readouterr().out


def test_local_copy_is_used_before_the_network(tmp_path, monkeypatch, fake_zenodo):
    folder = tmp_path / "mirror"
    folder.mkdir()
    (folder / AA_1DAY).write_bytes(open(os.path.join(FIXTURES, AA_1DAY), "rb").read())
    monkeypatch.setenv("NMRTRAIN_LOCAL", str(folder))
    nt.data._local_index.cache_clear()
    nt.data.fetch_member("11223995", fake_zenodo)
    assert Zenodo.requests == []


def test_fetch_prints_the_citation(fake_zenodo, monkeypatch, capsys):
    monkeypatch.setattr(nt.data, "select", lambda *a, **k: [fake_zenodo])
    nt.data.fetch("11223995", "AA", "K", times="1day")
    out = capsys.readouterr().out
    assert "10.5281/zenodo.11223995" in out and "CC BY 4.0" in out


# --- the alanine spectra hosted in this repository (data/alanine/) ------------------------------


def _no_network(*a, **k):
    raise AssertionError("the network was used")


def test_hosted_alanine_files_match_the_manifest():
    folder, (record, names) = "alanine", nt.data.HOSTED["alanine"]
    rows = nt.data.select(record, "ALA", "K", "1H")
    assert sorted(m["name"] for m in rows) == sorted(names)
    for m in rows:
        assert nt.data._crc_ok(os.path.join(nt.data.REPO_DATA, folder, m["name"]), m)


def test_hosted_alanine_loads_from_the_checkout_before_the_network(monkeypatch):
    monkeypatch.setattr(nt.data, "_get", _no_network)
    paths = nt.data.fetch("8381013", "ALA", "K", "1H", quiet=True)
    assert [os.path.basename(p) for p in paths] == [m["name"] for m in nt.data.select("8381013", "ALA", "K", "1H")]
    assert all(nt.data.member_for(p) for p in paths)


def test_hosted_alanine_comes_from_github_without_a_checkout(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(nt.data, "REPO_DATA", str(tmp_path / "no-checkout"))
    here = os.path.join(os.path.dirname(__file__), "..", "data", "alanine")
    urls = []

    def raw(url, *a, **k):
        urls.append(url)
        name = url.rsplit("/", 1)[-1].replace("%20", " ").replace("%28", "(").replace("%29", ")")
        return open(os.path.join(here, name), "rb").read()

    monkeypatch.setattr(nt.data, "_get_bytes", raw)
    monkeypatch.setattr(nt.data, "_range_get", _no_network)
    nt.data.fetch("8381013", "ALA", "K", "1H", times="1day")
    assert urls == ["https://raw.githubusercontent.com/Rakiura-Inc/morning-star-nmr/main/data/alanine/"
                    "SZSSea-ALA-D2SO4lock-1H-04112023_1%20%281%29.zip"]
    assert "from Rakiura-Inc/morning-star-nmr" in capsys.readouterr().out


def test_hosted_copy_falls_back_to_zenodo(tmp_path, monkeypatch):
    monkeypatch.setattr(nt.data, "REPO_DATA", str(tmp_path / "no-checkout"))
    calls = []

    def missing(url, *a, **k):
        calls.append("github")
        raise OSError("404")

    m = nt.data.select("8381013", "ALA", "K", "1H", times="1day")[0]
    blob = open(os.path.join(os.path.dirname(__file__), "..", "data", "alanine", m["name"]), "rb").read()
    monkeypatch.setattr(nt.data, "_get_bytes", missing)
    monkeypatch.setattr(nt.data, "_range_get", lambda record, member: calls.append("zenodo") or blob)
    assert nt.data._crc_ok(nt.data.fetch_member("8381013", m), m)
    assert calls == ["github", "zenodo"]
