# Changelog

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
