"""Notebook policy: clean commits, cell tags, the hand-in, part names, and member-facing copy."""
import glob
import json
import os
import re

import pytest

HERE = os.path.dirname(__file__)
ROOT = os.path.join(HERE, "..")
NOTEBOOKS = sorted(glob.glob(os.path.join(ROOT, "notebooks", "[0-9][0-9]_*.ipynb")))
TAGS = {"context", "setup", "worked", "predict", "do", "reveal", "check", "handin", "extra"}
DASHES = re.compile("[–—]")   # en and em dashes


def _nb(path):
    with open(path) as fh:
        return json.load(fh)


def test_there_are_five_notebooks():
    assert [os.path.basename(p)[:2] for p in NOTEBOOKS] == ["01", "02", "03", "04", "05"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=os.path.basename)
def test_committed_clean_and_tagged(path):
    nb = _nb(path)
    for c in nb["cells"]:
        tags = set(c.get("metadata", {}).get("tags", []))
        assert tags and tags <= TAGS, c["source"][:80]
        if c["cell_type"] == "code":
            assert c.get("outputs") == [] and c.get("execution_count") is None
    kinds = [t for c in nb["cells"] for t in c["metadata"]["tags"]]
    for needed in ("setup", "predict", "handin"):
        assert needed in kinds, needed


@pytest.mark.parametrize("path", NOTEBOOKS, ids=os.path.basename)
def test_parts_are_listed_for_the_portal(path):
    with open(os.path.join(ROOT, "notebooks", "rakiura_steps.json")) as fh:
        conf = json.load(fh)["notebooks"][os.path.basename(path)]
    src = "\n".join("".join(c["source"]) for c in _nb(path)["cells"] if c["cell_type"] == "code")
    used = set(re.findall(r'nt\.portal\.done\("([^"]+)"', src)) | set(re.findall(r'handin\(\s*"([^"]+)"', src))
    assert used and used <= set(conf["parts"]), used - set(conf["parts"])
    assert conf["project"] in ("ONB-102", "RES-102")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=os.path.basename)
def test_notebook_names_itself_by_its_repo_path(path):
    src = "".join(_nb(path)["cells"][1]["source"])
    assert f'NOTEBOOK = "notebooks/{os.path.basename(path)}"' in src


def test_no_dashes_in_member_facing_text():
    texts = []
    for path in NOTEBOOKS:
        texts += ["".join(c["source"]) for c in _nb(path)["cells"]]
    for path in glob.glob(os.path.join(ROOT, "nmrtrain", "*.py")) + glob.glob(os.path.join(ROOT, "answer_keys", "*.json")):
        with open(path) as fh:
            texts.append(fh.read())
    bad = [t[:60] for t in texts if DASHES.search(t)]
    assert not bad, bad


def test_markdown_stays_short():
    for path in NOTEBOOKS:
        words = sum(len("".join(c["source"]).split()) for c in _nb(path)["cells"] if c["cell_type"] == "markdown")
        assert words <= 1500, (os.path.basename(path), words)
