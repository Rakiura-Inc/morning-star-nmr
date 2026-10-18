# Answer keys

The keys hold only calls that a published paper states. Nothing here is our own reading of the
spectra.

| Key | Notebook | Cases | Source |
|---|---|---|---|
| `capstone.json` | 01 | Ala-Ala degrades, Gly-Gly survives (98% acid, 1H) | Petkowski et al. 2024, *Scientific Reports* 14, 17083. The Ala-Ala product (alaninamide): Petkowski et al., *ACS Omega* 2025, "Mechanism for peptide bond solvolysis in 98% w/w concentrated sulfuric acid" |
| `dipeptides.json` | 02 | Ala-Ala degrades, Gly-Gly survives (98% acid) | Petkowski et al. 2024, *Scientific Reports* 14, 17083 |
| `c13_series.json` | 05 | Ala-Ala degrades, Gly-Gly survives (98% acid, 13C) | Petkowski et al. 2024, *Scientific Reports* 14, 17083 |

`capstone.json` also holds the prediction ranges for Part 0 of notebook 01: how many C-H signals
each structure gives and where those signals sit in this acid.

**Every other case has no key.** Members check their call against the paper's tables:

* dipeptides (notebook 02, and any other condition): Table 1 (81%) and Table 2 (98%) of
  Petkowski et al. 2024, *Scientific Reports* 14, 17083
* amino acids (notebook 03): Table 1 of M. D. Seager et al. 2024, *Astrobiology* 24, 386

The feedback compares a call with a key only where one exists, and never grades. "Unsure" is
always accepted. All ppm values in the notebooks are on the instrument's scale: spectra are never
re-referenced to the acid peak, because that peak drifts over the months.
