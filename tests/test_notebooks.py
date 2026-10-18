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


def _visible(text):
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


def test_markdown_stays_short():
    # Fold-out hints are opt-in, so only the always-visible text counts.
    for path in NOTEBOOKS:
        words = sum(len(_visible("".join(c["source"])).split()) for c in _nb(path)["cells"]
                    if c["cell_type"] == "markdown")
        assert words <= 2400, (os.path.basename(path), words)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=os.path.basename)
def test_every_fill_in_cell_is_scaffolded(path):
    """Each cell a member writes in sits under a RECORD YOUR ANSWER box that says what is saved,
    where to look and how to fill it in, with two fold-out hints; a What you need cell with a link
    to the longer step comes before it."""
    cells = _nb(path)["cells"]
    for i, c in enumerate(cells):
        tags = c["metadata"]["tags"]
        if c["cell_type"] != "code" or not {"predict", "do"} & set(tags):
            continue
        above = "".join(cells[i - 1]["source"])
        assert cells[i - 1]["cell_type"] == "markdown" and "**RECORD YOUR ANSWER:" in above, c["source"][:2]
        for part in ("**What gets saved:**", "**Where to look:**", "**How to fill this in:**",
                     "Stuck? Open hint 1", "Stuck? Open hint 2"):
            assert part in above, (part, c["source"][:2])
        before = "\n".join("".join(x["source"]) for x in cells[max(0, i - 4):i] if x["cell_type"] == "markdown")
        assert "### What you need" in before and "Longer version:" in before, c["source"][:2]
        assert "#" in "".join(c["source"]), "each line a member fills carries a comment"
    handins = [i for i, c in enumerate(cells) if "handin" in c["metadata"]["tags"]]
    assert handins and all("**SAVE YOUR HAND-IN:" in "".join(cells[i - 1]["source"]) for i in handins)


def test_training_not_exam_language():
    exam = re.compile(r"\b(score|scored|grade|graded|exam|quiz|correct answer|wrong answer|pass mark)\b", re.I)
    for path in NOTEBOOKS:
        for c in _nb(path)["cells"]:
            text = "".join(c["source"])
            assert not exam.search(text), (os.path.basename(path), exam.search(text).group(0))
            for jargon in ("residue", "alpha-H", "[look again]", "[agrees]"):
                assert jargon not in text, (os.path.basename(path), jargon)
