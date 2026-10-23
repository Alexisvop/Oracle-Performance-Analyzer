# Benchmark methodology

The recorded metric is end-to-end client execute + complete-fetch latency, measured with perf_counter_ns and expressed in milliseconds. Each variant/state has five retained warmups and ten measured repetitions. All samples remain available; warmups are excluded from descriptive summaries and no outliers are removed.

Percentiles use sorted values and linear interpolation at rank (n - 1) * p. IQR = Q75 - Q25; p95 is a tail descriptor for this small sample, not a service-level guarantee. Percent changes use unrounded medians.

Stage A has five runs / 105 samples (35 warmups, 70 measured); Group A has ten runs / 180 samples (60 warmups, 120 measured); final Group B E04 has two runs / 60 samples (20 warmups, 40 measured). Sequential, single-host small-data blocks retain cache/order/host confounders. No buffer-cache flush or randomized state alternation establishes causal proof.

Same SQL/binds/result hashes are checked for equivalent comparisons. PAID and CANCELLED return different row counts and are NOT COMPARABLE as equivalent workloads; compare each cohort across A/B separately. Q03–Q05 have no Phase 4 latency measurements.

EXPLAIN PLAN yields optimizer estimates. Cost is not elapsed milliseconds, and E-Rows is not runtime A-Rows. An active ORDERS.STATUS FREQUENCY histogram did not give different bind-placeholder estimates in E04: both remained 2,500. Bind peeking behavior and actual cursor metrics require further privileged evidence; they are not established by these captures.

[Evidence](evidence/README.md), [results](phase4-results.md), [findings](findings.md).
