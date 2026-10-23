# Engineering findings

Selective email/customer B-trees had lower observed median client latency in these blocks. An index was not sufficient for lower latency: E03 range used INDEX RANGE SCAN and was slower; E03 TRUNC and E05 retained full scans. Small-table overhead, caching and block order are possible explanations, not measured causal mechanisms.

E04 preserves the actual skew: PAID 5,876; SHIPPED 2,523; NEW 1,060; CANCELLED 541. The observed FREQUENCY histogram endpoints are cumulative [541, 1601, 7477, 10000]. Estimated E-Rows remained 2,500 for each bind-placeholder query. Actual row counts are known from complete fetch/correctness checks, not privileged runtime operator counters.

Exact statistics restoration was checked field-by-field and with DIFF_TABLE_STATS_IN_STATTAB MAXDIFFPCT = 0. Preserve this evidence separately from descriptive latency interpretation. Runtime cursor metrics, bind peeking inspection, advanced diagnostics and multi-scale experiments remain future work.

[Full numerical results](phase4-results.md), [benchmark limitations](benchmark-methodology.md), [public evidence](evidence/README.md).
