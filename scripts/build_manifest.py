"""Maintainer script: build nmrtrain/manifests/<record>.json from the Zenodo archives.

A manifest lists every Bruker experiment (an inner zip) inside a record's archive, with its byte
offset, size and CRC, and the sample, acid, time point and nucleus read from its name. With it,
`nmrtrain.data.fetch` pulls one spectrum with a single HTTP range request and verifies it.

Usage:
    python scripts/build_manifest.py                      # reads the archives from Zenodo by range
    python scripts/build_manifest.py --local DIR [DIR..]  # reads local copies of the archives instead

Local copies must be byte-identical to the Zenodo files (the script checks the size).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from nmrtrain.data import RECORDS, HttpRangeFile, _record_file_url  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "nmrtrain", "manifests")

# 8381013: the folder says the acid and the time point; the file name says the amino acid and nucleus.
_AA_FOLDER = re.compile(r"aa 1H(?: and 13C)? (81|98) (1day|1week|1month) original data$")
_ACID = {"98": "K", "81": "H"}


def parse(record: str, path: str) -> dict | None:
    name = os.path.basename(path)
    folder = os.path.dirname(path)
    if record == "11223995":
        m = re.match(r"SZSSea-([A-Z]{2})-([HK])-(\w+?)-(1H|13C)-\d+_\d+\.zip$", name)
        if not m:
            return None
        sample, acid, time, nuc = m.groups()
        group = {"4MonthR": "4Month"}.get(time, time)
        return {"sample": sample, "acid": acid, "time": time, "time_group": group, "nucleus": nuc,
                "repeat": time.endswith("R")}
    if record == "8381013":
        fm = _AA_FOLDER.search(folder)
        if not fm:
            return None  # contaminant tests and modified amino acids: not used by the notebooks
        acid, group = _ACID[fm.group(1)], fm.group(2)
        m = re.match(r"SZSSea-([A-Z]{3})-(?:H-)?(?:(\d+day|1month)-)?D2SO?4?lock-(1H|13C|13H)-", name)
        if not m:
            return None
        sample, time, nuc = m.groups()
        nuc = "1H" if nuc == "13H" else nuc  # one file is named 13H; it is a 1H experiment
        return {"sample": sample, "acid": acid, "time": time or group, "time_group": group, "nucleus": nuc,
                "repeat": False}
    if record == "11122291":
        m = re.match(r"SZSSea-(AA\+A|AA|LAlaninamide|LGlycinamide)-(?:([HK])-)?(?:(1Week)-)?(1H|13C)-", name)
        if not m or "Dataset S5" in folder:
            return None
        sample, acid, time, nuc = m.groups()
        return {"sample": sample, "acid": acid or "K", "time": time or "ref", "time_group": time or "ref",
                "nucleus": nuc, "repeat": False}
    return None


def build(record: str, local_dirs: list[str]) -> dict:
    info = RECORDS[record]
    fh = None
    for d in local_dirs:
        for cand in (os.path.join(d, info["file"]), os.path.join(d, info["file"].replace(" ", "_"))):
            if os.path.exists(cand) and os.path.getsize(cand) == info["size"]:
                fh = open(cand, "rb")
                print(f"{record}: reading local copy {cand}")
    if fh is None:
        print(f"{record}: reading the archive's directory from Zenodo by range")
        fh = io.BufferedReader(HttpRangeFile(_record_file_url(record)), buffer_size=1 << 16)
    members = []
    with zipfile.ZipFile(fh) as z:
        for zi in z.infolist():
            if not zi.filename.endswith(".zip"):
                continue
            fields = parse(record, zi.filename)
            if not fields:
                continue
            members.append({"path": zi.filename, "name": os.path.basename(zi.filename),
                            "offset": zi.header_offset, "compress_size": zi.compress_size,
                            "size": zi.file_size, "compress_type": zi.compress_type, "crc": zi.CRC, **fields})
    return {"record": record, "file": info["file"], "file_size": info["size"], "members": members}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", nargs="*", default=[], help="folders holding local copies of the archives")
    ap.add_argument("records", nargs="*", default=list(RECORDS))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for record in args.records:
        manifest = build(record, args.local)
        path = os.path.join(OUT, f"{record}.json")
        with open(path, "w") as out:
            json.dump(manifest, out, indent=0, sort_keys=True)
        print(f"  wrote {os.path.relpath(path)}: {len(manifest['members'])} spectra")


if __name__ == "__main__":
    main()
