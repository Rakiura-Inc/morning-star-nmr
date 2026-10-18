# Alanine practice files

Three hydrogen NMR spectra of alanine in 98% w/w D2SO4, used by the bootcamp alanine step and by
notebook 03 (Part 1). Each zip is one Bruker experiment (raw FID plus the instrument's processed
spectrum), copied unchanged from the Zenodo archive so you do not need the 275 MB download.

| Time in the acid | File |
|---|---|
| 1 day | `SZSSea-ALA-D2SO4lock-1H-04112023_1 (1).zip` |
| 1 week (named "8day") | `SZSSea-ALA-8day-D2SO4lock-1H-04182023_1.zip` |
| 1 month | `SZSSea-ALA-1month-D2SO4lock-1H-05102023_1.zip` |

Drag the zips into [NMRium](https://www.nmrium.org/) one at a time, oldest first, or let
`nmrtrain` load them (`nt.load_series("8381013", "ALA", acid="K", nucleus="1H")`).

## Licence and attribution

These files are **not** covered by this repository's MIT licence. They are licensed
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by their authors:

Seager, M. D., Seager, S., Bains, W., Petkowski, J. J. (2023). Supplementary datasets for
*Stability of 20 biogenic amino acids in concentrated sulfuric acid: implications for the
habitability of Venus' clouds*, Zenodo, [10.5281/zenodo.8381013](https://doi.org/10.5281/zenodo.8381013)
(Suppl. Dataset S1, "aa 1H 98" folders). Paper: *Astrobiology* 24, 386 (2024).

The files are unmodified; each matches the size and CRC listed for it in
`nmrtrain/manifests/8381013.json`.
