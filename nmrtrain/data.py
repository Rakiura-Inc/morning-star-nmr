"""Fetch only the spectra a notebook needs from the public Zenodo records.

Each record is one big zip of many small Bruker experiments (one inner zip per spectrum). The
manifest shipped with this package (`nmrtrain/manifests/<record>.json`) lists where each inner
zip sits in the big file, so one HTTP range request brings back one spectrum (about 0.5 MB)
instead of the whole archive (100 to 270 MB). Every file is checked against its CRC and cached in
`./nmr_data/` (or `$NMRTRAIN_DATA`), so a second run downloads nothing.

Order of sources for each spectrum:
  1. the cache;
  2. this repository's own copy (`data/`, see HOSTED), from the checkout when there is one;
  3. a local copy (`$NMRTRAIN_LOCAL`: folders holding the inner zips or the full archives);
  4. this repository's copy on GitHub (HOSTED spectra only);
  5. Zenodo, one range request per spectrum, at most about two requests a second;
  6. a mirror of the inner zips (`$NMRTRAIN_MIRROR`, a base URL), when one is set;
  7. if Zenodo refuses partial downloads: the whole archive, once, into the cache.

All three datasets are CC BY 4.0. `fetch` prints the citation every time it runs.
"""
from __future__ import annotations

import functools
import glob
import http.client
import io
import json
import os
import shutil
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from importlib import resources
from typing import Iterable

from . import __version__

USER_AGENT = f"nmrtrain/{__version__} (training notebooks; polite range reads)"
MIN_INTERVAL_S = float(os.environ.get("NMRTRAIN_MIN_INTERVAL", "0.5"))
MAX_TRIES = 4

RECORDS = {
    "11223995": {
        "doi": "10.5281/zenodo.11223995",
        "file": "Suplementary dataset S1.zip",
        "size": 187180468,
        "title": "General Instability of Dipeptides in Concentrated Sulfuric Acid as Relevant for the Venus "
                 "Cloud Habitability (Supplementary dataset S1)",
        "authors": "Petkowski, J. J.; Seager, M. D.; Bains, W.; Seager, S.",
        "year": 2024,
        "paper": "Petkowski et al. 2024, Scientific Reports 14, 17083, doi:10.1038/s41598-024-67342-w",
        "time_order": ["1day", "3day", "8day", "5week", "4Month", "4MonthR"],
    },
    "8381013": {
        "doi": "10.5281/zenodo.8381013",
        "file": "Suppl. Dataset S1 AA 1D NMR.zip",
        "size": 274559353,
        "title": "Stability of Biogenic Amino Acids in Concentrated Sulfuric Acid: Implications for the "
                 "Habitability of Venus' Clouds (Supplementary dataset S1)",
        "authors": "Seager, M. D.; Seager, S.; Bains, W.; Petkowski, J. J.",
        "year": 2023,
        "paper": "Seager et al. 2024, Astrobiology 24, 386 (ADS 2024AsBio..24..386S)",
        "time_order": ["1day", "1week", "1month"],
    },
    "11122291": {
        "doi": "10.5281/zenodo.11122291",
        "file": "SUPPLEMENTARY DATASETS 1-5.zip",
        "size": 101517923,
        "title": "Mechanism for Peptide Bond Solvolysis in 98% w/w Concentrated Sulfuric Acid "
                 "(Supplementary datasets 1 to 5)",
        "authors": "Petkowski, J. J.; Seager, M. D.; Bains, W.; Grimes Jr, J. H.; Seager, S.",
        "year": 2024,
        "paper": "Petkowski et al. 2024, ACS Omega (peptide bond solvolysis mechanism)",
        "time_order": ["ref", "1Week"],
    },
}

ACIDS = {"K": "98% w/w D2SO4", "H": "81% w/w D2SO4"}

# Spectra this repository hosts in data/<folder>/ (unchanged copies of the Zenodo inner zips, same
# CC BY 4.0 licence), so members get them from one place. Same CRC checks as every other source.
REPO = "Rakiura-Inc/morning-star-nmr"
REPO_REF = "main"
HOSTED = {
    "alanine": ("8381013", (
        "SZSSea-ALA-D2SO4lock-1H-04112023_1 (1).zip",      # alanine, 98%, 1H, 1 day
        "SZSSea-ALA-8day-D2SO4lock-1H-04182023_1.zip",     # 1 week (named 8day)
        "SZSSea-ALA-1month-D2SO4lock-1H-05102023_1.zip",   # 1 month
    )),
}
REPO_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def _record_file_url(record: str) -> str:
    key = urllib.parse.quote(RECORDS[record]["file"])
    return f"https://zenodo.org/api/records/{record}/files/{key}/content"


def citation(record: str) -> str:
    r = RECORDS[record]
    return (f"Data: {r['authors']} ({r['year']}). {r['title']}. Zenodo. https://doi.org/{r['doi']} "
            f"(CC BY 4.0). Paper: {r['paper']}.")


def data_dir() -> str:
    return os.path.abspath(os.environ.get("NMRTRAIN_DATA", "nmr_data"))


# ---------------------------------------------------------------------------------------------
# polite HTTP


_last_request = [0.0]


def _wait_turn() -> None:
    gap = time.monotonic() - _last_request[0]
    if gap < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - gap)
    _last_request[0] = time.monotonic()


def _get(url: str, start: int | None = None, end: int | None = None, timeout: float = 120):
    """GET with an optional byte range, a rate limit, and retries that respect Retry-After.
    Dropped connections are retried by `_get_bytes`, around this."""
    headers = {"User-Agent": USER_AGENT}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
    delay = 2.0
    for attempt in range(1, MAX_TRIES + 1):
        _wait_turn()
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < MAX_TRIES:
                wait = float(exc.headers.get("Retry-After") or delay)
                print(f"  Zenodo asked us to slow down; waiting {min(wait, 60):.0f} s")
                time.sleep(min(wait, 60))
                delay *= 2
                continue
            raise


_NET_ERRORS = (OSError, urllib.error.URLError, http.client.HTTPException)


def _get_bytes(url: str, start: int | None = None, end: int | None = None, timeout: float = 120,
               need_partial: bool = False) -> bytes:
    """Read a whole response (or byte range), retrying a dropped connection with backoff."""
    delay = 2.0
    for attempt in range(1, MAX_TRIES + 1):
        try:
            with _get(url, start, end, timeout) as r:
                if need_partial and r.status != 206:
                    raise PermissionError("the server does not support partial downloads")
                return r.read()
        except (PermissionError, urllib.error.HTTPError):
            raise
        except _NET_ERRORS:
            if attempt == MAX_TRIES:
                raise
            time.sleep(delay)
            delay *= 2


class HttpRangeFile(io.RawIOBase):
    """A read-only, seekable view of a remote file, so `zipfile` can read single members."""

    def __init__(self, url: str):
        self.url, self.pos = url, 0
        with _get(url, 0, 0, timeout=60) as r:
            if r.status != 206:
                raise OSError("the server does not support partial downloads")
            self.size = int(r.headers["Content-Range"].split("/")[-1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buf):
        if self.pos >= self.size:
            return 0
        end = min(self.pos + len(buf), self.size) - 1
        data = _get_bytes(self.url, self.pos, end)
        buf[: len(data)] = data
        self.pos += len(data)
        return len(data)


# ---------------------------------------------------------------------------------------------
# the manifest


@functools.lru_cache(maxsize=None)
def manifest(record: str) -> dict:
    """The list of spectra in a record (shipped with the package)."""
    if record not in RECORDS:
        raise KeyError(f"unknown record {record!r}; known: {', '.join(RECORDS)}")
    text = resources.files("nmrtrain").joinpath("manifests", f"{record}.json").read_text()
    return json.loads(text)


def _norm_record(record: str) -> str:
    return str(record).replace("10.5281/zenodo.", "").replace("zenodo.", "").strip()


def select(record: str, sample: str, acid: str | None = None, nucleus: str = "1H",
           times: str | Iterable[str] = "all", repeats: bool = False) -> list[dict]:
    """Manifest entries for one sample, in the order of the experiment (first time point first)."""
    record = _norm_record(record)
    order = RECORDS[record]["time_order"]
    rows = [m for m in manifest(record)["members"]
            if m["sample"] == sample and m["nucleus"] == nucleus and (acid is None or m["acid"] == acid)
            and (repeats or not m["repeat"])]
    if times != "all":
        wanted = [times] if isinstance(times, str) else list(times)
        rows = [m for m in rows if m["time_group"] in wanted or m["time"] in wanted]
    # one spectrum per time point: the last run (highest _n suffix in the file name) wins
    best: dict[tuple, dict] = {}
    for m in sorted(rows, key=lambda m: m["name"]):
        best[(m["acid"], m["time_group"], m["repeat"])] = m
    rows = list(best.values())
    rows.sort(key=lambda m: (m["acid"], order.index(m["time_group"]) if m["time_group"] in order else 99))
    if not rows:
        have = sorted({(m["sample"], m["acid"], m["nucleus"]) for m in manifest(record)["members"]})
        raise LookupError(f"no {nucleus} spectra for sample {sample!r}, acid {acid!r} in record {record}. "
                          f"Samples here: {', '.join(sorted({h[0] for h in have}))}")
    return rows


def samples(record: str) -> list[str]:
    return sorted({m["sample"] for m in manifest(_norm_record(record))["members"]})


# ---------------------------------------------------------------------------------------------
# getting one inner zip


def _crc_ok(path: str, member: dict) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) != member["size"]:
        return False
    crc = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            crc = zlib.crc32(chunk, crc)
    return (crc & 0xFFFFFFFF) == member["crc"]


@functools.lru_cache(maxsize=None)
def _local_index() -> dict:
    """Inner zips and full archives found under $NMRTRAIN_LOCAL (folders separated by os.pathsep)."""
    inner, outer = {}, {}
    sizes = {r["size"]: rec for rec, r in RECORDS.items()}
    for root in filter(None, os.environ.get("NMRTRAIN_LOCAL", "").split(os.pathsep)):
        for p in glob.glob(os.path.join(os.path.expanduser(root), "**", "*.zip"), recursive=True):
            size = os.path.getsize(p)
            if size in sizes:
                outer[sizes[size]] = p
            else:
                inner.setdefault(os.path.basename(p), []).append(p)
    return {"inner": inner, "outer": outer}


def _hosted_folder(record: str, member: dict) -> str | None:
    for folder, (rec, names) in HOSTED.items():
        if rec == record and member["name"] in names:
            return folder
    return None


def _hosted_url(folder: str, name: str) -> str:
    return (f"https://raw.githubusercontent.com/{REPO}/{REPO_REF}/data/{folder}/"
            f"{urllib.parse.quote(name)}")


def _write_verified(data: bytes, dest: str, member: dict) -> bool:
    if len(data) != member["size"] or (zlib.crc32(data) & 0xFFFFFFFF) != member["crc"]:
        return False
    with open(dest + ".part", "wb") as out:
        out.write(data)
    os.replace(dest + ".part", dest)
    return True


def _from_member_bytes(blob: bytes, member: dict) -> bytes:
    """Strip the zip local header from a range read and return the member's bytes."""
    sig, *_rest = struct.unpack("<IHHHHHIIIHH", blob[:30])
    if sig != 0x04034B50:
        raise OSError("unexpected bytes at the manifest offset (the archive may have changed)")
    name_len, extra_len = struct.unpack("<HH", blob[26:30])
    start = 30 + name_len + extra_len
    raw = blob[start:start + member["compress_size"]]
    if member["compress_type"] == 0:
        return raw
    if member["compress_type"] == 8:
        return zlib.decompress(raw, -15)
    raise OSError(f"compression type {member['compress_type']} is not supported")


def _range_get(record: str, member: dict) -> bytes:
    start = member["offset"]
    end = start + 30 + len(member["path"].encode()) + 2048 + member["compress_size"]
    return _from_member_bytes(_get_bytes(_record_file_url(record), start, end, need_partial=True), member)


def _whole_archive(record: str) -> str:
    path = os.path.join(data_dir(), record, RECORDS[record]["file"])
    if not (os.path.exists(path) and os.path.getsize(path) == RECORDS[record]["size"]):
        mb = RECORDS[record]["size"] / 1e6
        print(f"  Partial downloads are not available right now; downloading the whole archive "
              f"({mb:.0f} MB) once. Later runs reuse it.")
        with _get(_record_file_url(record), timeout=600) as r, open(path + ".part", "wb") as out:
            shutil.copyfileobj(r, out, 1 << 20)
        os.replace(path + ".part", path)
    return path


def fetch_member(record: str, member: dict, quiet: bool = False) -> str:
    """Path to one verified inner zip in the cache, getting it if needed."""
    record = _norm_record(record)
    folder = os.path.join(data_dir(), record)
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, member["name"])
    if _crc_ok(dest, member):
        return dest
    hosted = _hosted_folder(record, member)
    if hosted:
        cand = os.path.join(REPO_DATA, hosted, member["name"])
        if _crc_ok(cand, member):
            shutil.copyfile(cand, dest)
            return dest
    idx = _local_index()
    for cand in idx["inner"].get(member["name"], []):
        if _crc_ok(cand, member):
            shutil.copyfile(cand, dest)
            return dest
    if record in idx["outer"]:
        with zipfile.ZipFile(idx["outer"][record]) as z:
            if _write_verified(z.read(member["path"]), dest, member):
                return dest
    errors = []
    if hosted:
        try:
            if _write_verified(_get_bytes(_hosted_url(hosted, member["name"])), dest, member):
                if not quiet:
                    print(f"  got {member['name']} ({member['size'] / 1e6:.1f} MB) from {REPO}")
                return dest
            errors.append(f"checksum mismatch on the copy in {REPO}")
        except _NET_ERRORS as exc:
            errors.append(str(exc))
    try:
        if _write_verified(_range_get(record, member), dest, member):
            if not quiet:
                print(f"  got {member['name']} ({member['size'] / 1e6:.1f} MB)")
            return dest
        errors.append("checksum mismatch on the range read")
    except _NET_ERRORS as exc:
        errors.append(str(exc))
    mirror = os.environ.get("NMRTRAIN_MIRROR")
    if mirror:
        try:
            if _write_verified(_get_bytes(mirror.rstrip("/") + "/" + urllib.parse.quote(member["name"])), dest, member):
                return dest
        except _NET_ERRORS as exc:
            errors.append(str(exc))
    try:
        with zipfile.ZipFile(_whole_archive(record)) as z:
            if _write_verified(z.read(member["path"]), dest, member):
                return dest
    except (_NET_ERRORS + (zipfile.BadZipFile, KeyError)) as exc:
        errors.append(str(exc))
    raise OSError(f"Could not get {member['name']} ({'; '.join(errors)}). If you are offline, try again "
                  f"later, or download https://doi.org/{RECORDS[record]['doi']} and point NMRTRAIN_LOCAL at it.")


def fetch(record: str, sample: str, acid: str | None = "K", nucleus: str = "1H",
          times: str | Iterable[str] = "all", quiet: bool = False) -> list[str]:
    """Download (or find) the spectra for one sample and return their paths, first time point first.

    record: "11223995" (dipeptides), "8381013" (amino acids) or "11122291" (mechanism); a DOI works too.
    acid: "K" (98% w/w) or "H" (81% w/w); None for both.
    """
    record = _norm_record(record)
    rows = select(record, sample, acid, nucleus, times)
    need = [m for m in rows if not _crc_ok(os.path.join(data_dir(), record, m["name"]), m)]
    if not quiet:
        mb = sum(m["size"] for m in need) / 1e6
        what = f"{len(rows)} spectra" + (f", downloading {len(need)} ({mb:.1f} MB)" if need else ", all cached")
        print(f"{sample} {nucleus} {ACIDS.get(acid, 'both acids') if acid else 'both acids'}: {what}")
    paths = [fetch_member(record, m, quiet=quiet) for m in rows]
    if not quiet:
        print(citation(record))
    return paths


def member_for(path: str) -> dict | None:
    """The manifest entry for a cached inner zip, found by file name."""
    name = os.path.basename(path)
    for record in RECORDS:
        for m in manifest(record)["members"]:
            if m["name"] == name:
                return {**m, "record": record}
    return None
