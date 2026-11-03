"""Maintainer script: build nmrtrain/manifests/<record>.json from the Zenodo archives.

A manifest lists every Bruker experiment (an inner zip) inside a record's archive, with its byte
offset, size and CRC, and the sample, acid, time point and nucleus read from its name. With it,
`nmrtrain.data.fetch` pulls one spectrum with a single HTTP range request and verifies it.

Usage:
    uv run scripts/build_manifest.py                      # reads the archives from Zenodo by range
    uv run scripts/build_manifest.py --local DIR [DIR..]  # reads local copies of the archives instead

Local copies must be byte-identical to the Zenodo files (the script checks the size).
"""

from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

from nmrtrain.data import RECORDS, HttpRangeFile, _record_file_url

OUT = Path(__file__).resolve().parent.parent / "nmrtrain" / "manifests"
READ_BUFFER = 1 << 16

# 11223995: everything is in the file name.
_DIPEPTIDE_NAME = re.compile(r"SZSSea-([A-Z]{2})-([HK])-(\w+?)-(1H|13C)-\d+_\d+\.zip$")
_REPEAT_OF = {"4MonthR": "4Month"}

# 8381013: the folder says the acid and the time point; the file name says the amino acid and nucleus.
_AA_FOLDER = re.compile(r"aa 1H(?: and 13C)? (81|98) (1day|1week|1month) original data$")
_AA_NAME = re.compile(r"SZSSea-([A-Z]{3})-(?:H-)?(?:(\d+day|1month)-)?D2SO?4?lock-(1H|13C|13H)-")
_ACID = {"98": "K", "81": "H"}
# O-sulfoserine, the reference compound for serine in 98% acid, sits in the folder of modified
# amino acids. Only its 98% (K) files are used; the A files are in heavy water.
_MODIFIED_FOLDER = "sulfSer-oxMet-oxCys-sulfCys 1H and 13C 98 1day original data"
_O_SULFOSERINE_NAME = re.compile(r"SZSSea-(OSulfLSer)-K-1Day-(1H|13C)-")

# 11122291: the mechanism study; dataset S5 is not used by the notebooks.
_MECHANISM_NAME = re.compile(r"SZSSea-(AA\+A|AA|LAlaninamide|LGlycinamide)-(?:([HK])-)?(?:(1Week)-)?(1H|13C)-")


def _fields(sample: str, acid: str, time: str, group: str, nucleus: str, *, repeat: bool = False) -> dict:  # noqa: PLR0917 (the manifest's fields, in its order)
    return {"sample": sample, "acid": acid, "time": time, "time_group": group, "nucleus": nucleus, "repeat": repeat}


def _parse_dipeptide(name: str, _folder: str) -> dict | None:
    m = _DIPEPTIDE_NAME.match(name)
    if not m:
        return None
    sample, acid, time, nuc = m.groups()
    return _fields(sample, acid, time, _REPEAT_OF.get(time, time), nuc, repeat=time.endswith("R"))


def _parse_amino_acid(name: str, folder: str) -> dict | None:
    if folder.endswith(_MODIFIED_FOLDER):
        m = _O_SULFOSERINE_NAME.match(name)
        if not m:
            return None
        return _fields(m.group(1), "K", "1day", "1day", m.group(2))
    fm = _AA_FOLDER.search(folder)
    if not fm:
        return None  # contaminant tests and the other modified amino acids: not used by the notebooks
    acid, group = _ACID[fm.group(1)], fm.group(2)
    m = _AA_NAME.match(name)
    if not m:
        return None
    sample, time, nuc = m.groups()
    nuc = "1H" if nuc == "13H" else nuc  # one file is named 13H; it is a 1H experiment
    return _fields(sample, acid, time or group, group, nuc)


def _parse_mechanism(name: str, folder: str) -> dict | None:
    m = _MECHANISM_NAME.match(name)
    if not m or "Dataset S5" in folder:
        return None
    sample, acid, time, nuc = m.groups()
    return _fields(sample, acid or "K", time or "ref", time or "ref", nuc)


_PARSERS = {"11223995": _parse_dipeptide, "8381013": _parse_amino_acid, "11122291": _parse_mechanism}


def parse(record: str, path: str) -> dict | None:
    """The sample, acid, time point and nucleus of one inner zip, or None if the notebooks skip it."""
    parser = _PARSERS.get(record)
    p = PurePosixPath(path)
    return parser(p.name, str(p.parent) if str(p.parent) != "." else "") if parser else None


def _open_archive(record: str, local_dirs: list[str]):
    """A local copy of the record's archive if one has the right size, else a range reader on Zenodo."""
    info = RECORDS[record]
    for d in local_dirs:
        for cand in (Path(d, info["file"]), Path(d, info["file"].replace(" ", "_"))):
            if cand.exists() and cand.stat().st_size == info["size"]:
                print(f"{record}: reading local copy {cand}")
                return cand.open("rb")
    print(f"{record}: reading the archive's directory from Zenodo by range")
    return io.BufferedReader(HttpRangeFile(_record_file_url(record)), buffer_size=READ_BUFFER)


def _entry(zi: zipfile.ZipInfo, fields: dict) -> dict:
    return {
        "path": zi.filename,
        "name": PurePosixPath(zi.filename).name,
        "offset": zi.header_offset,
        "compress_size": zi.compress_size,
        "size": zi.file_size,
        "compress_type": zi.compress_type,
        "crc": zi.CRC,
        **fields,
    }


def build(record: str, local_dirs: list[str]) -> dict:
    """The manifest of one record."""
    info = RECORDS[record]
    with _open_archive(record, local_dirs) as fh, zipfile.ZipFile(fh) as z:
        members = [
            _entry(zi, fields)
            for zi in z.infolist()
            if zi.filename.endswith(".zip") and (fields := parse(record, zi.filename))
        ]
    return {"record": record, "file": info["file"], "file_size": info["size"], "members": members}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", nargs="*", default=[], help="folders holding local copies of the archives")
    ap.add_argument("records", nargs="*", default=list(RECORDS))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for record in args.records:
        manifest = build(record, args.local)
        path = OUT / f"{record}.json"
        path.write_text(json.dumps(manifest, indent=0, sort_keys=True) + "\n")
        print(f"  wrote {path.relative_to(OUT.parent.parent)}: {len(manifest['members'])} spectra")


if __name__ == "__main__":
    main()
