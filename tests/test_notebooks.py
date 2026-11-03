"""Notebook policy: clean commits, cell tags, the hand-in, part names, and member-facing copy."""

import json
import re

import pytest

from .helpers import NOTEBOOKS, ROOT

TAGS = {"context", "setup", "worked", "predict", "do", "reveal", "check", "handin", "extra"}
DASHES = re.compile("[\u2013\u2014]")  # en and em dashes


def _name(path):
    return path.name


def _nb(path):
    return json.loads(path.read_text())


def test_there_are_five_notebooks():
    assert [p.name[:2] for p in NOTEBOOKS] == ["01", "02", "03", "04", "05"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_name)
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


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_name)
def test_parts_are_listed_for_the_portal(path):
    conf = json.loads((ROOT / "notebooks" / "rakiura_steps.json").read_text())["notebooks"][path.name]
    src = "\n".join("".join(c["source"]) for c in _nb(path)["cells"] if c["cell_type"] == "code")
    used = set(re.findall(r'nt\.portal\.done\("([^"]+)"', src)) | set(re.findall(r'handin\(\s*"([^"]+)"', src))
    assert used and used <= set(conf["parts"]), used - set(conf["parts"])
    assert conf["project"] in ("ONB-102", "RES-102")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_name)
def test_notebook_names_itself_by_its_repo_path(path):
    src = "".join(_nb(path)["cells"][1]["source"])
    assert f'NOTEBOOK = "notebooks/{path.name}"' in src


def test_no_dashes_in_member_facing_text():
    texts = []
    for path in NOTEBOOKS:
        texts += ["".join(c["source"]) for c in _nb(path)["cells"]]
    package = ROOT / "nmrtrain"
    texts += [
        p.read_text() for p in [*package.glob("*.py"), *package.glob("*.json"), *package.glob("answer_keys/*.json")]
    ]
    bad = [t[:60] for t in texts if DASHES.search(t)]
    assert not bad, bad


def _visible(text):
    return re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)


# Visible words a notebook may hold. The steps on Rakiura are short tickets (tickets v1), so the
# teaching they used to carry lives here. Each cap sits about 3 to 10% above the notebook's size
# when tickets v1 landed (01: 4,033; 02: 2,548; 03: 2,815; 04: 1,381; 05: 1,535), so new text has
# to replace old text rather than pile on. Notebook 01 carries the bootcamp's three NMR steps;
# notebook 03 a project step and the serine Extra.
MAX_VISIBLE_WORDS = {"01": 4150, "02": 2700, "03": 3000, "04": 1500, "05": 1700}


def test_markdown_stays_short():
    # Fold-out hints are opt-in, so only the always-visible text counts.
    for path in NOTEBOOKS:
        words = sum(
            len(_visible("".join(c["source"])).split()) for c in _nb(path)["cells"] if c["cell_type"] == "markdown"
        )
        limit = MAX_VISIBLE_WORDS[path.name[:2]]
        assert words <= limit, (path.name, words, limit)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=_name)
def test_every_fill_in_cell_is_scaffolded(path):
    """Each cell a member writes in sits under a RECORD YOUR ANSWER box that says what is saved,
    where to look and how to fill it in, with two fold-out hints; a section that teaches what the
    answer needs (What you need, What to look at, or the part's own heading) comes before it. The
    steps on Rakiura are short tickets, so the teaching is here, not behind a "Longer version" link."""
    cells = _nb(path)["cells"]
    for i, c in enumerate(cells):
        tags = c["metadata"]["tags"]
        if c["cell_type"] != "code" or not {"predict", "do"} & set(tags):
            continue
        above = "".join(cells[i - 1]["source"])
        assert cells[i - 1]["cell_type"] == "markdown" and "**RECORD YOUR ANSWER:" in above, c["source"][:2]
        for part in (
            "**What gets saved:**",
            "**Where to look:**",
            "**How to fill this in:**",
            "Stuck? Open hint 1",
            "Stuck? Open hint 2",
        ):
            assert part in above, (part, c["source"][:2])
        before = "\n".join("".join(x["source"]) for x in cells[max(0, i - 4) : i] if x["cell_type"] == "markdown")
        assert re.search(r"^#{2,3} ", before, re.MULTILINE), c["source"][:2]
        assert "Longer version:" not in before, c["source"][:2]
        assert "#" in "".join(c["source"]), "each line a member fills carries a comment"
    handins = [i for i, c in enumerate(cells) if "handin" in c["metadata"]["tags"]]
    assert handins and all("**SAVE YOUR HAND-IN:" in "".join(cells[i - 1]["source"]) for i in handins)


def test_training_not_exam_language():
    exam = re.compile(r"\b(score|scored|grade|graded|exam|quiz|correct answer|wrong answer|pass mark)\b", re.IGNORECASE)
    for path in NOTEBOOKS:
        for c in _nb(path)["cells"]:
            text = "".join(c["source"])
            assert not exam.search(text), (path.name, exam.search(text).group(0))
            for jargon in ("residue", "alpha-H", "[look again]", "[agrees]"):
                assert jargon not in text, (path.name, jargon)
