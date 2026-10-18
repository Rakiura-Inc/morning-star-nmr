# NMR training notebooks (Morning Star Missions)

Python notebooks for reading NMR stability data, using the public spectra behind three open papers
on molecules in concentrated sulfuric acid (the Venus cloud question). A small package, `nmrtrain`,
fetches, loads, processes and plots the spectra and runs the checks. The judgment stays in the
notebooks: what to compare, what the peaks say, and the verdict.

> **Answer keys:** the notebooks compare a verdict only with calls the papers state (Ala-Ala and
> Gly-Gly in 98% acid). For every other case, members check their call against the paper's
> tables. There is no PyPI package; the notebooks install `nmrtrain` from this repository.

## The notebooks

| # | Notebook | Where it is used | Time | Open in Colab |
|---|---|---|---|---|
| 01 | Do protein building blocks survive Venus's acid? Check the lab's answer yourself | Bootcamp (ONB-102), step 7 | 60 to 90 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rakiura-Inc/morning-star-nmr/blob/main/notebooks/01_capstone_ala_ala_vs_gly_gly.ipynb) |
| 02 | Does weaker acid change what survives? Test one small peptide at two acid strengths (you pick it) | NMR project (RES-102), step 1, after notebook 01 | 60 to 90 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rakiura-Inc/morning-star-nmr/blob/main/notebooks/02_one_dipeptide_both_acids.ipynb) |
| 03 | Can a molecule change but not fall apart? Find the change in an amino acid's spectra | NMR project (RES-102), step 2, after notebook 02 | 45 to 60 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rakiura-Inc/morning-star-nmr/blob/main/notebooks/03_amino_acid_side_chains.ipynb) |
| 04 | Can you trust the instrument's spectrum? Process the raw data yourself | NMR project (RES-102), step 3 | 30 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rakiura-Inc/morning-star-nmr/blob/main/notebooks/04_process_raw_fids.ipynb) |
| 05 | Did the molecule really split in two? Count the peaks in a carbon spectrum | NMR project (RES-102), an Extra (optional) | 30 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rakiura-Inc/morning-star-nmr/blob/main/notebooks/05_read_a_13c_series.ipynb) |

Each notebook has:

* a short introduction
* **predict, then reveal**: the reveal cell will not run until you enter a prediction
* worked cells that you run and read
* a **What you need** cell before every question: the facts it rests on, a figure or table where it
  helps, and the matching bootcamp or NMR step by name
* a **RECORD YOUR ANSWER** box above every cell a member fills in: what gets saved, where to look,
  how to fill it in, and two fold-out hints; each recording cell confirms what it saved
* the verdict recorded one field at a time, next to the plot that answers it, then shown as one
  table before the hand-in (with a filled example row)
* trap checks next to the cells they apply to
* a hand-in cell that saves the figures and a `verdict.json` and ticks the step on Rakiura

Cells carry tags (`context`, `setup`, `worked`, `predict`, `do`,
`reveal`, `check`, `handin`, `extra`); committed notebooks carry no outputs.

Executed copies are in `notebooks/executed/`: a first pass with blank answers, as a member first
sees it, with the traps firing.

## Try it locally

```sh
git clone https://github.com/Rakiura-Inc/morning-star-nmr.git
cd morning-star-nmr
make local          # creates .venv, installs nmrtrain (editable) and the Rakiura helper, opens Jupyter Lab
```

`make local` installs the Rakiura notebook helper from
[Rakiura-Inc/rakiura-py](https://github.com/Rakiura-Inc/rakiura-py) (use a local checkout with
`make local RAKIURA_HELPER=/path/to/rakiura-py`). If it cannot be installed, the notebooks run in
offline mode. Other targets:

```sh
make test           # pytest (about 10 s; no network)
make run            # execute all five notebooks headless into notebooks/executed/ (blank answers)
```

Without make:

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,notebooks,explore]"
.venv/bin/pip install "rakiura @ git+https://github.com/Rakiura-Inc/rakiura-py@main"   # optional: the Rakiura helper
.venv/bin/jupyter lab notebooks
```

**Data.** The first run of each notebook downloads only the spectra it needs (2 to 5 MB) from
Zenodo: one partial download per spectrum, at most about two requests a second, each checked
against its CRC and cached in `notebooks/nmr_data/`. If you are offline or already have the
archives, point `NMRTRAIN_LOCAL` at the folders that hold them (separated by `:`) and nothing is
downloaded:

```sh
NMRTRAIN_LOCAL=/path/to/zenodo/archives make local
```

If Zenodo refuses partial downloads, the package falls back to the whole archive once (100 to 270
MB, cached), and to `NMRTRAIN_MIRROR` (a base URL serving the inner zips) when one is set.

## Colab

The badges above open each notebook from GitHub. The setup cell installs the package and the
Rakiura helper (about 30 s):

```python
%pip install -q "nmrtrain @ git+https://github.com/Rakiura-Inc/morning-star-nmr@main"
%pip install -q "rakiura @ git+https://github.com/Rakiura-Inc/rakiura-py@main"
```

Pin `nmrtrain` to a release commit with `scripts/set_repo.py OWNER/NAME --pin <sha>`. A member
connects by running the Connect to Rakiura cell under the setup cell and clicking Allow on the link
it prints, again in each new Colab session (or adds a `RAKIURA_KEY` secret in Colab's Secrets panel). Not connected, the notebook runs in offline
mode and members attach the files from `handin/` on the step page.

## Connecting to Rakiura

`nmrtrain.portal` uses the Rakiura helper
([`rakiura`](https://github.com/Rakiura-Inc/rakiura-py)) when it is installed. When it is not, offline mode makes the same calls locally.

| Call in the notebook | Live (helper installed and connected) | Offline |
|---|---|---|
| `nt.portal.connect(NOTEBOOK)` | `rakiura.start(notebook=..., repo=...)`: opens a run with the notebook path, repository, commit and where it runs; prints "Connected to Rakiura as <name>." | prints "Not connected to Rakiura. ..." |
| `nt.portal.connect(NOTEBOOK, sign_in=True)` | the Connect cell: the same, and signs in with one click if no key is saved (prints a link) | as above |
| `nt.portal.done(part, figures, numbers)` | `rakiura.done(...)`: ticks the checklist item linked to that part, stages figures and up to 20 numbers | logs to `handin/rakiura_progress.json` |
| `nt.record.handin(part, ...)` | the above, plus `rakiura.stage_text(verdict.json, step=...)` when a step id is set | saves PNGs and `verdict.json` in `handin/<part>/` |
| `nt.portal.submit()` | `rakiura.submit()`: sends the step for review; never automatic | says nothing was sent |

Live mode starts on its own when the helper is installed and a key is available without a click
(`RAKIURA_KEY`, Colab Secrets, or a key saved by an earlier sign-in). The Connect cell
(`sign_in=True`, also `nt.portal.go_live()` or `RAKIURA_LIVE=1`) signs in with one click; the setup
cell never waits for one. `RAKIURA_LIVE=0` forces offline, Connect cell included.

**Part names** (link each to a checklist item in Rakiura under Settings > Notebook links; the
notebooks carry no Rakiura ids). Full list with descriptions: `notebooks/rakiura_steps.json`.

| Notebook | Project | Parts |
|---|---|---|
| 01 | ONB-102 | `capstone-predict`, `capstone-stack`, `capstone-compare`, `capstone-verdict` |
| 02 | RES-102 | `dipeptide-stack`, `dipeptide-verdict` |
| 03 | RES-102 | `amino-acid-stack`, `amino-acid-verdict` |
| 04 | RES-102 | `raw-overlay` |
| 05 | RES-102 | `c13-verdict` |

**Step ids** are needed only to stage the verdict file. Set `"step"` per notebook in
`notebooks/rakiura_steps.json` (for example `"ONB-102-D7"`), or `RAKIURA_STEP` for one session,
or point `NMRTRAIN_STEPS` at another file. Left `null`, members attach `verdict.json` by hand.
Research projects still close other members' threads on first approval (D19), so notebooks 02
to 05 need per-member mode before many members hand in on one step.

## Checks and answer keys

Trap checks run in every notebook and never stop it. They flag:

* a mirrored ppm axis (the acid peak must sit near 11.4 to 11.5 ppm in 98% acid, 11.7 to 12.1 in 81%)
* spectra out of time order (by label and by acquisition date)
* acid-peak drift over 0.2 ppm
* traces scaled to the acid peak
* broad early peaks
* fading NH signals
* signal loss with nothing new (possible precipitation)

Feedback compares a call with a published call where the key has one (Ala-Ala and Gly-Gly in
98% acid; Petkowski et al. 2024, *Scientific Reports* 14, 17083). For any other dipeptide case it
says: check your call against Table 1 (81%) and Table 2 (98%) of the paper. For the amino acids:
check it against Table 1 of M. D. Seager et al. 2024, *Astrobiology* 24, 386. It never grades.
"Unsure" is always accepted.

**Spectra are never re-referenced to the acid peak by default.** That peak drifts (about 0.07 ppm
over four months, in Ala-Ala and in Gly-Gly alike), and aligning on it distorts every comparison. Keep the instrument's ppm scale.

The keys and their sources: [`answer_keys/README.md`](answer_keys/README.md).

## Community replication table

`replication/` holds the schema, an empty `replications.csv`, and `update_table.py`. A maintainer
runs the script on the lines from approved notebook 02 hand-ins to append them and regenerate the
20 x 2 grid. See
[`replication/README.md`](replication/README.md).

## Data and attribution

Most spectra are not in this repository. They are fetched at run time from Zenodo, all
**CC BY 4.0**. Two exceptions, unchanged copies under the same licence: the three alanine practice
files in [`data/alanine/`](data/alanine/) (Zenodo 8381013; the notebooks load them from here
first and fall back to Zenodo) and one test fixture in `tests/fixtures/` (Zenodo 11223995).

* Petkowski, J. J., Seager, M. D., Bains, W., Seager, S. (2024). Supplementary datasets for
  *General instability of dipeptides in concentrated sulfuric acid as relevant for the Venus cloud
  habitability*, Zenodo, [10.5281/zenodo.11223995](https://doi.org/10.5281/zenodo.11223995).
  Paper: *Scientific Reports* 14, 17083 (2024), doi:10.1038/s41598-024-67342-w.
* Seager, M. D., Seager, S., Bains, W., Petkowski, J. J. (2023). Supplementary datasets for
  *Stability of 20 biogenic amino acids in concentrated sulfuric acid*, Zenodo,
  [10.5281/zenodo.8381013](https://doi.org/10.5281/zenodo.8381013). Paper: *Astrobiology* 24, 386 (2024).
* Petkowski, J. J., Seager, M. D., Bains, W., Grimes Jr, J. H., Seager, S. (2024). Supplementary
  datasets for *Mechanism for peptide bond solvolysis in 98% w/w concentrated sulfuric acid*,
  Zenodo, [10.5281/zenodo.11122291](https://doi.org/10.5281/zenodo.11122291).

`fetch` prints the citation every time it runs. Machine-readable: [`CITATION.cff`](CITATION.cff).

## Licence

MIT, copyright 2026 Rakiura Inc.: see [`LICENSE`](LICENSE). The licence does not cover the data:
the spectra (including `data/alanine/` and the test fixture in `tests/fixtures/`) stay under their
authors' CC BY 4.0, credited above under "Data and attribution".

## Publishing

From the repository folder:

```sh
gh repo create Rakiura-Inc/morning-star-nmr --public --source . --push
# optional: pin the notebooks' install line to the pushed commit, then push again
python scripts/set_repo.py Rakiura-Inc/morning-star-nmr --pin "$(git rev-parse HEAD)"
git commit -am "Pin notebooks to the package commit" && git push
```

`scripts/set_repo.py NEW_OWNER/NEW_NAME` renames the repository everywhere it appears (Colab
links, install lines, `CITATION.cff`, `nmrtrain/portal.py`, `nmrtrain/data.py`) if it ever moves.

## Layout

```
nmrtrain/        data (Zenodo fetch, manifests/), io, process, peaks, plot, checks, answers, record, portal
notebooks/       01 to 05, rakiura_steps.json, executed/
data/alanine/    the three alanine practice spectra (CC BY 4.0, Zenodo 8381013)
answer_keys/     published calls only (JSON), installed as nmrtrain.answer_keys
replication/     schema.json, replications.csv, update_table.py
scripts/         build_manifest.py, run_notebooks.py, set_repo.py
tests/           pytest, with one fixture spectrum
```
