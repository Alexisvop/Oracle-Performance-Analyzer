# Historical Phase 4 results — public summary

These observations are historical and were not rerun for this export. The final evidence contains 17 benchmark runs, 345 samples (115 warmups, 230 measured), 23 variant/state measurements and ten report comparison rows; two within-run cross-status comparisons are marked NOT COMPARABLE. The frontend emphasizes six index and two same-cohort histogram comparisons.

Index medians/deltas are in the [README results table](../README.md). Full precision and raw samples are available in the [evidence inventory](evidence/README.md). Unfavorable index observations are retained.

E04 Scenario A/B: compare PAID with PAID and CANCELLED with CANCELLED; the full captured estimated tree is SELECT STATEMENT -> SORT ORDER BY -> TABLE ACCESS FULL ORDERS, plan hash 36248429, root cost 16, table cost 15, E-Rows 2,500. This corrects older prose; no HASH JOIN is present. Estimates are not actual operator metrics.

The historical recovery receipt records import-recovery PASS; field comparisons report no differences and MAXDIFFPCT = 0. Active statistics restoration is a recorded historical observation, not a new live Oracle check.

[Methodology](benchmark-methodology.md), [findings](findings.md), [closure](phase4-final-audit.md).
