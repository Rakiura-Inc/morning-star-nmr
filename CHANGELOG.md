# Changelog

## 0.1.0 (2026-10-18, not published)
- Repository named `Rakiura-Inc/morning-star-nmr`; code under MIT (data stays CC BY 4.0);
  the no-helper fallback is now called offline mode.
- The three alanine practice spectra (98%, 1H, 1 day / 1 week / 1 month; Zenodo 8381013, CC BY 4.0)
  are hosted in `data/alanine/`; `nmrtrain` loads them from the repository first, then Zenodo.
- First local version: `nmrtrain` package (Zenodo range fetch with manifests, Bruker loading, raw
  processing, plots, peak picking, trap checks, feedback, portal bridge), five notebooks, answer
  keys holding only the calls the papers state (Ala-Ala and Gly-Gly in 98% acid), replication
  table schema and script.
