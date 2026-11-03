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
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from . import __version__

USER_AGENT = f"nmrtrain/{__version__} (training notebooks; polite range reads)"
MIN_INTERVAL_S = float(os.environ.get("NMRTRAIN_MIN_INTERVAL", "0.5"))
MAX_TRIES = 4
FIRST_RETRY_DELAY_S = 2.0
LONGEST_WAIT_S = 60
RETRY_STATUS = (429, 500, 502, 503, 504)
CHUNK = 1 << 20  # bytes read at a time when checking or copying a file

# A zip member starts with a 30-byte local header (signature, ..., name length, extra length), then
# its name and an extra field. A range read asks for this much room for the extra field.
ZIP_LOCAL_SIGNATURE = 0x04034B50
ZIP_LOCAL_HEADER_SIZE = 30
ZIP_NAME_LENGTHS_AT = 26
ZIP_EXTRA_FIELD_ROOM = 2048
ZIP_STORED, ZIP_DEFLATED = 0, 8

# The records and their citations live in records.json, next to this module.
RECORDS: dict[str, dict] = json.loads(resources.files("nmrtrain").joinpath("records.json").read_text())

ACIDS = {"K": "98% w/w D2SO4", "H": "81% w/w D2SO4"}

# Spectra this repository hosts in data/<folder>/ (unchanged copies of the Zenodo inner zips, same
# CC BY 4.0 licence), so members get them from one place. Same CRC checks as every other source.
REPO = "Rakiura-Inc/morning-star-nmr"
REPO_REF = "main"
HOSTED = {
    "alanine": (
        "8381013",
        (
            "SZSSea-ALA-D2SO4lock-1H-04112023_1 (1).zip",  # alanine, 98%, 1H, 1 day
            "SZSSea-ALA-8day-D2SO4lock-1H-04182023_1.zip",  # 1 week (named 8day)
            "SZSSea-ALA-1month-D2SO4lock-1H-05102023_1.zip",  # 1 month
        ),
    ),
}
REPO_DATA = str(Path(__file__).resolve().parent.parent / "data")


def _record_file_url(record: str) -> str:
    key = urllib.parse.quote(RECORDS[record]["file"])
    return f"https://zenodo.org/api/records/{record}/files/{key}/content"


def citation(record: str) -> str:
    """The data and paper citation for one record, as printed by `fetch`."""
    r = RECORDS[record]
    return (
        f"Data: {r['authors']} ({r['year']}). {r['title']}. Zenodo. https://doi.org/{r['doi']} "
        f"(CC BY 4.0). Paper: {r['paper']}."
    )


def data_dir() -> str:
    """The folder that caches downloaded spectra ($NMRTRAIN_DATA, default ./nmr_data)."""
    return str(Path(os.environ.get("NMRTRAIN_DATA", "nmr_data")).resolve())


# ---------------------------------------------------------------------------------------------
# polite HTTP


class _RateLimit:
    """Keeps requests at least MIN_INTERVAL_S apart."""

    last = 0.0

    @classmethod
    def wait_turn(cls) -> None:
        gap = time.monotonic() - cls.last
        if gap < MIN_INTERVAL_S:
            time.sleep(MIN_INTERVAL_S - gap)
        cls.last = time.monotonic()


def _get(url: str, start: int | None = None, end: int | None = None, timeout: float = 120):
    """GET with an optional byte range, a rate limit, and retries that respect Retry-After.
    Dropped connections are retried by `_get_bytes`, around this."""
    headers = {"User-Agent": USER_AGENT}
    if start is not None:
        headers["Range"] = f"bytes={start}-{end}"
    delay = FIRST_RETRY_DELAY_S
    for attempt in range(1, MAX_TRIES + 1):
        _RateLimit.wait_turn()
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)  # noqa: S310 (Zenodo, GitHub or the mirror a maintainer set)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUS or attempt == MAX_TRIES:
                raise
            wait = min(float(exc.headers.get("Retry-After") or delay), LONGEST_WAIT_S)
            print(f"  Zenodo asked us to slow down; waiting {wait:.0f} s")
            time.sleep(wait)
            delay *= 2


_NET_ERRORS = (OSError, urllib.error.URLError, http.client.HTTPException)


def _read_body(response, need_partial: bool) -> bytes:
    if need_partial and response.status != http.client.PARTIAL_CONTENT:
        msg = "the server does not support partial downloads"
        raise PermissionError(msg)
    return response.read()


def _get_bytes(
    url: str, start: int | None = None, end: int | None = None, timeout: float = 120, need_partial: bool = False
) -> bytes:
    """Read a whole response (or byte range), retrying a dropped connection with backoff."""
    delay = FIRST_RETRY_DELAY_S
    for attempt in range(1, MAX_TRIES + 1):
        try:
            with _get(url, start, end, timeout) as r:
                return _read_body(r, need_partial)
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
            if r.status != http.client.PARTIAL_CONTENT:
                msg = "the server does not support partial downloads"
                raise OSError(msg)
            self.size = int(r.headers["Content-Range"].split("/")[-1])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        self.pos = {io.SEEK_SET: offset, io.SEEK_CUR: self.pos + offset, io.SEEK_END: self.size + offset}[whence]
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


@functools.cache
def manifest(record: str) -> dict:
    """The list of spectra in a record (shipped with the package)."""
    if record not in RECORDS:
        msg = f"unknown record {record!r}; known: {', '.join(RECORDS)}"
        raise KeyError(msg)
    text = resources.files("nmrtrain").joinpath("manifests", f"{record}.json").read_text()
    return json.loads(text)


def _norm_record(record: str) -> str:
    return str(record).replace("10.5281/zenodo.", "").replace("zenodo.", "").strip()


def _wanted(m: dict, sample: str, acid: str | None, nucleus: str, repeats: bool) -> bool:
    return (
        m["sample"] == sample
        and m["nucleus"] == nucleus
        and (acid is None or m["acid"] == acid)
        and (repeats or not m["repeat"])
    )


def _last_run_per_time_point(rows: list[dict]) -> list[dict]:
    """One spectrum per time point: the last run (highest _n suffix in the file name) wins."""
    best: dict[tuple, dict] = {}
    for m in sorted(rows, key=lambda m: m["name"]):
        best[m["acid"], m["time_group"], m["repeat"]] = m
    return list(best.values())


def select(
    record: str,
    sample: str,
    acid: str | None = None,
    nucleus: str = "1H",
    times: str | Iterable[str] = "all",
    repeats: bool = False,
) -> list[dict]:
    """Manifest entries for one sample, in the order of the experiment (first time point first)."""
    record = _norm_record(record)
    members = manifest(record)["members"]
    order = RECORDS[record]["time_order"]
    rows = [m for m in members if _wanted(m, sample, acid, nucleus, repeats)]
    if times != "all":
        wanted = [times] if isinstance(times, str) else list(times)
        rows = [m for m in rows if m["time_group"] in wanted or m["time"] in wanted]
    rows = _last_run_per_time_point(rows)
    unknown_time = len(order)  # sorts after every known time point
    rows.sort(key=lambda m: (m["acid"], order.index(m["time_group"]) if m["time_group"] in order else unknown_time))
    if not rows:
        known = ", ".join(sorted({m["sample"] for m in members}))
        msg = f"no {nucleus} spectra for sample {sample!r}, acid {acid!r} in record {record}. Samples here: {known}"
        raise LookupError(msg)
    return rows


def samples(record: str) -> list[str]:
    """Every sample name in a record."""
    return sorted({m["sample"] for m in manifest(_norm_record(record))["members"]})


# ---------------------------------------------------------------------------------------------
# getting one inner zip


def _crc32(data: bytes, crc: int = 0) -> int:
    return zlib.crc32(data, crc) & 0xFFFFFFFF


def _crc_ok(path: str | Path, member: dict) -> bool:
    """True when the file exists with the member's size and CRC."""
    path = Path(path)
    if not path.exists() or path.stat().st_size != member["size"]:
        return False
    crc = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            crc = _crc32(chunk, crc)
    return crc == member["crc"]


@functools.cache
def _local_index() -> dict:
    """Inner zips and full archives found under $NMRTRAIN_LOCAL (folders separated by os.pathsep)."""
    inner: dict[str, list[str]] = {}
    outer: dict[str, str] = {}
    record_by_size = {r["size"]: rec for rec, r in RECORDS.items()}
    for root in filter(None, os.environ.get("NMRTRAIN_LOCAL", "").split(os.pathsep)):
        for p in sorted(Path(root).expanduser().rglob("*.zip")):
            size = p.stat().st_size
            if size in record_by_size:
                outer[record_by_size[size]] = str(p)
            else:
                inner.setdefault(p.name, []).append(str(p))
    return {"inner": inner, "outer": outer}


def _hosted_folder(record: str, member: dict) -> str | None:
    for folder, (rec, names) in HOSTED.items():
        if rec == record and member["name"] in names:
            return folder
    return None


def _hosted_url(folder: str, name: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{REPO_REF}/data/{folder}/{urllib.parse.quote(name)}"


def _write_verified(data: bytes, dest: str, member: dict) -> bool:
    """Write data to dest only when it has the member's size and CRC."""
    if len(data) != member["size"] or _crc32(data) != member["crc"]:
        return False
    part = Path(dest + ".part")
    part.write_bytes(data)
    part.replace(dest)
    return True


def _copy_first_verified(candidates: Iterable[str | Path], dest: str, member: dict) -> bool:
    for cand in candidates:
        if _crc_ok(cand, member):
            shutil.copyfile(cand, dest)
            return True
    return False


def _from_member_bytes(blob: bytes, member: dict) -> bytes:
    """Strip the zip local header from a range read and return the member's bytes."""
    (signature,) = struct.unpack_from("<I", blob)
    if signature != ZIP_LOCAL_SIGNATURE:
        msg = "unexpected bytes at the manifest offset (the archive may have changed)"
        raise OSError(msg)
    name_len, extra_len = struct.unpack_from("<HH", blob, ZIP_NAME_LENGTHS_AT)
    start = ZIP_LOCAL_HEADER_SIZE + name_len + extra_len
    raw = blob[start : start + member["compress_size"]]
    if member["compress_type"] == ZIP_STORED:
        return raw
    if member["compress_type"] == ZIP_DEFLATED:
        return zlib.decompress(raw, -zlib.MAX_WBITS)
    msg = f"compression type {member['compress_type']} is not supported"
    raise OSError(msg)


def _range_get(record: str, member: dict) -> bytes:
    start = member["offset"]
    end = start + ZIP_LOCAL_HEADER_SIZE + len(member["path"].encode()) + ZIP_EXTRA_FIELD_ROOM + member["compress_size"]
    return _from_member_bytes(_get_bytes(_record_file_url(record), start, end, need_partial=True), member)


def _whole_archive(record: str) -> str:
    path = Path(data_dir(), record, RECORDS[record]["file"])
    if not (path.exists() and path.stat().st_size == RECORDS[record]["size"]):
        mb = RECORDS[record]["size"] / 1e6
        print(
            f"  Partial downloads are not available right now; downloading the whole archive "
            f"({mb:.0f} MB) once. Later runs reuse it."
        )
        part = path.with_name(path.name + ".part")
        with _get(_record_file_url(record), timeout=600) as r, part.open("wb") as out:
            shutil.copyfileobj(r, out, CHUNK)
        part.replace(path)
    return str(path)


def _read_from_archive(archive: str, member: dict) -> bytes:
    with zipfile.ZipFile(archive) as z:
        return z.read(member["path"])


@dataclass(frozen=True)
class _Download:
    """One network source for a spectrum, tried in turn by `fetch_member`."""

    read: Callable[[], bytes]
    got: str | None = None  # printed on success
    mismatch: str | None = None  # recorded when the bytes fail the CRC check
    errors: tuple[type[BaseException], ...] = _NET_ERRORS  # recorded and skipped


def _downloads(record: str, member: dict, hosted: str | None) -> list[_Download]:
    """The network sources for one spectrum, in the order they are tried."""
    name, mb = member["name"], member["size"] / 1e6
    sources = []
    if hosted:
        sources.append(
            _Download(
                read=lambda: _get_bytes(_hosted_url(hosted, name)),
                got=f"  got {name} ({mb:.1f} MB) from {REPO}",
                mismatch=f"checksum mismatch on the copy in {REPO}",
            )
        )
    sources.append(
        _Download(
            read=lambda: _range_get(record, member),
            got=f"  got {name} ({mb:.1f} MB)",
            mismatch="checksum mismatch on the range read",
        )
    )
    mirror = os.environ.get("NMRTRAIN_MIRROR")
    if mirror:
        sources.append(_Download(read=lambda: _get_bytes(mirror.rstrip("/") + "/" + urllib.parse.quote(name))))
    sources.append(
        _Download(
            read=lambda: _read_from_archive(_whole_archive(record), member),
            errors=(*_NET_ERRORS, zipfile.BadZipFile, KeyError),
        )
    )
    return sources


def _from_local_copies(record: str, member: dict, dest: str, hosted: str | None) -> bool:
    """The checkout's own copy, then the copies under $NMRTRAIN_LOCAL. No network."""
    if hosted and _copy_first_verified([Path(REPO_DATA, hosted, member["name"])], dest, member):
        return True
    idx = _local_index()
    if _copy_first_verified(idx["inner"].get(member["name"], []), dest, member):
        return True
    return record in idx["outer"] and _write_verified(_read_from_archive(idx["outer"][record], member), dest, member)


def fetch_member(record: str, member: dict, quiet: bool = False) -> str:
    """Path to one verified inner zip in the cache, getting it if needed."""
    record = _norm_record(record)
    folder = Path(data_dir(), record)
    folder.mkdir(parents=True, exist_ok=True)
    dest = str(folder / member["name"])
    hosted = _hosted_folder(record, member)
    if _crc_ok(dest, member) or _from_local_copies(record, member, dest, hosted):
        return dest
    errors = []
    for source in _downloads(record, member, hosted):
        try:
            if _write_verified(source.read(), dest, member):
                if source.got and not quiet:
                    print(source.got)
                return dest
            if source.mismatch:
                errors.append(source.mismatch)
        except source.errors as exc:
            errors.append(str(exc))
    msg = (
        f"Could not get {member['name']} ({'; '.join(errors)}). If you are offline, try again "
        f"later, or download https://doi.org/{RECORDS[record]['doi']} and point NMRTRAIN_LOCAL at it."
    )
    raise OSError(msg)


def fetch(
    record: str,
    sample: str,
    acid: str | None = "K",
    nucleus: str = "1H",
    times: str | Iterable[str] = "all",
    quiet: bool = False,
) -> list[str]:
    """Download (or find) the spectra for one sample and return their paths, first time point first.

    record: "11223995" (dipeptides), "8381013" (amino acids) or "11122291" (mechanism); a DOI works too.
    acid: "K" (98% w/w) or "H" (81% w/w); None for both.
    """
    record = _norm_record(record)
    rows = select(record, sample, acid, nucleus, times)
    need = [m for m in rows if not _crc_ok(Path(data_dir(), record, m["name"]), m)]
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
    name = Path(path).name
    for record in RECORDS:
        for m in manifest(record)["members"]:
            if m["name"] == name:
                return {**m, "record": record}
    return None
