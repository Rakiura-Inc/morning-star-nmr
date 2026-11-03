# Changelog

## Unreleased
- The teaching that left the Morning Star steps (tickets v1) now lives in the notebooks. Notebook 01
  carries the bootcamp's three NMR steps in order: a new Part 0 reads glycine and explains what NMR
  measures, splitting, solvent shifts and fading peaks; a new Part 1 judges alanine over a month
  (part `alanine-verdict`); Ala-Ala becomes Parts 2 to 5, with a What to look at in Gly-Gly cell,
  the full match rule and both candidate products in the decision, and the alaninamide overlay
  (now with alanine beside it) before the decision. Notebook 02 gains the stuck notes, the acid
  shifts, and Look at every time point. Notebook 03 gains the worked case (asparagine in 81% acid
  against aspartic acid), a carbon check of asparagine in 98% acid, and Part 5, the Extra on serine
  against O-sulfoserine (part `serine-verdict`). Notebook 04 gains the step's thresholds and Your
  own code (optional); notebook 05 the mechanism and Read the mechanism paper. Steps are named by
  title, never by number, and the "Longer version" lines are gone.
- `docs/triage-score-sheet.md` and `docs/working-in-nmrium.md`.
- O-sulfoserine in 98% acid (`OSulfLSer`, 1H and 13C) is in the 8381013 manifest.
- `nt.load_series` takes the names the steps use ("glycine", "98%") as well as the dataset codes.
- `nt.record.saved` and `nt.record.write_down` return None, so a cell can end with one without a `;`.
- `nt.record.saved` says "Not saved yet" for an empty list or string, not "Saved".
- Tooling brought up to date; nothing the notebooks print or save changes. Python 3.11 to 3.15 (3.10 is end of
  life). uv for everything, with a committed `uv.lock`; the package builds with hatchling.
- ruff lints and formats the package, scripts, tests and notebooks; prek runs the git hooks
  (nbstripout keeps committed notebooks free of outputs). Tests run in parallel and in random order.
- CI: tests on every supported Python, a wheel build and import, and a run of all five notebooks on
  every pull request; every action pinned to a commit. Renovate keeps dependencies current.
- Readability pass on the package with the same behaviour: the record list is in
  `nmrtrain/records.json`, long functions are split, magic numbers are named. The answer keys
  moved to `nmrtrain/answer_keys/`.

## 0.1.0 (2026-10-18, not published)
- How much is left is measured against the acid peak in the same file, as a fraction of day 1
  (`nt.peaks.against_acid`, `left_of_first`, `left_band`), in notebooks 01 and 02, at the two levels
  NMR step 1 uses: under one third is "little or none" (clear loss), one third or more is "no clear
  loss" (decide from the spectra). Ala-Ala's 1.99 ppm methyl: 100, 91, 57, 7, 0% of day 1, shown as
  an approximate illustration with the step's caveat. The share of all peaks from hydrogens on carbon
  is no longer used for this, because that total shrinks as a molecule breaks down.
- Survives, as in the steps: the molecule's peaks keep their sizes relative to each other (not
  against the acid peak, which collects the hydrogens the sample hands over), and no new peaks
  appear. `nt.peaks.against_own_peak` and `second_peak_ppm`; notebook 01 prints Ala-Ala's 5.17 ppm
  alpha against its 4.92 ppm alpha (100, 85, 69, 27, 5%), notebook 02 your peak against your next
  tallest. Notebook 02's `SIGNAL_PPM` and `OTHER_PPM` are set per acid.
- Gly-Gly in notebooks 01 and 02 in the steps' words: survives at least 4 months; the 4.77 ppm peak
  weakens to about a third of day 1 against the acid peak, unexplained by the paper; its second line
  from 5 weeks; the 4.33 ppm peak from about 8 days.
- One match rule in notebooks 01 to 03: same pattern and within 0.05 ppm is a match, 0.05 to 0.1 ppm
  needs the carbon spectra, over 0.1 ppm is not a match.
- "Community replication table" is now "Shared results table" (README, replication/README.md).
- Notebook 04 prints the acid peak in both spectra and the largest difference between matching
  lines (`nt.peaks.line_differences`, `nt.checks.line_feedback`) next to the similarity, and records
  a yes / no / unsure decision. A zero-fill below the recording's size no longer crashes; the hint
  offers 32768 (the instrument's choice) and 131072.
- Notebook 03 offers asparagine in 98% acid (`CASE = "ASN-K"`), the NMR project step 2 hand-in.
- Clarity pass on all five notebooks: the Ala-Ala mechanism as the mechanism study gives it
  (alaninamide plus acrylic acid, from the end alanine's C-N bond breaking), member text and
  feedback say "decision" for the call, "Look again." replaces "Not quite.", titles match the steps.
- Each notebook has a Connect to Rakiura cell under the setup cell (`nt.portal.connect(NOTEBOOK,
  sign_in=True)`): it prints a sign-in link, the member checks the code and clicks Allow. The setup
  cell still connects only without a click, and now prints "Connected to Rakiura as <name>." or
  "Not connected to Rakiura. Your work stays on this computer. ..."
- Each notebook's setup cell installs the Rakiura helper from GitHub
  (`Rakiura-Inc/rakiura-py`), so a member can connect in Colab; `make local` installs it too.
- Every question is scaffolded: a What you need cell (facts, a figure or table, the matching step by
  name), a RECORD YOUR ANSWER box with fold-out hints, and a comment on each line to fill in.
- Predictions are judged against the typical ranges the notebook teaches, never against this
  dataset; the measured ranges appear only after the member reads the plots (`check_reading`).
- Verdicts are recorded one field at a time (`nt.record.write_down`) and shown as one table
  (`nt.record.build_verdict`), with a filled Gly-Gly (or alanine) example row.
- Feedback in plain words: "Yes." / "Not quite." instead of bracketed labels; plain call words
  ("breaks down", "side chain changed"; the older words still work); ticks print "Prediction saved"
  instead of the internal part name.
- Repository named `Rakiura-Inc/morning-star-nmr`; code under MIT (data stays CC BY 4.0);
  the no-helper fallback is now called offline mode.
- The three alanine practice spectra (98%, 1H, 1 day / 1 week / 1 month; Zenodo 8381013, CC BY 4.0)
  are hosted in `data/alanine/`; `nmrtrain` loads them from the repository first, then Zenodo.
- First local version: `nmrtrain` package (Zenodo range fetch with manifests, Bruker loading, raw
  processing, plots, peak picking, trap checks, feedback, portal bridge), five notebooks, answer
  keys holding only the calls the papers state (Ala-Ala and Gly-Gly in 98% acid), replication
  table schema and script.
