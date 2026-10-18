# Community replication table

Twenty homodipeptides, two acid strengths: forty conditions. Each reviewed dipeptide hand-in
(notebook 02) adds one row per acid to [`replications.csv`](replications.csv). GitHub shows the
CSV as a searchable table.

* **Who writes it:** a maintainer, with `update_table.py`, from approved hand-ins only. Members
  never edit the file; the reviewer's approval is the gate.
* **Credit:** a contributor's display name appears only with their opt-in; otherwise "Rakiura member".
* **Public data only:** rows come from the public dipeptide dataset
  ([10.5281/zenodo.11223995](https://doi.org/10.5281/zenodo.11223995), CC BY 4.0). Verdicts on a
  lab's unpublished molecules never enter this table.
* **Reference rows** (`REF-<dipeptide>-<acid>`) carry the calls the paper states outright
  (Ala-Ala and Gly-Gly in 98%; Petkowski et al. 2024, *Scientific Reports* 14, 17083). Every
  other condition has no reference row: check it against Table 1 (81%) and Table 2 (98%) of the
  paper.

Columns: see [`schema.json`](schema.json).

```sh
python replication/update_table.py --reference
python replication/update_table.py --rows path/to/replication_rows.csv --reviewed-on 2026-11-02
```

## Grid

<!-- grid:begin -->
0 of 40 conditions replicated by 0 contributor(s). Updated 2026-10-18.

| Dipeptide | 98% (K) | 81% (H) |
|---|---|---|
| AA | open | open |
| CC | open | open |
| DD | open | open |
| EE | open | open |
| FF | open | open |
| GG | open | open |
| HH | open | open |
| II | open | open |
| KK | open | open |
| LL | open | open |
| MM | open | open |
| NN | open | open |
| PP | open | open |
| QQ | open | open |
| RR | open | open |
| SS | open | open |
| TT | open | open |
| VV | open | open |
| WW | open | open |
| YY | open | open |
<!-- grid:end -->
