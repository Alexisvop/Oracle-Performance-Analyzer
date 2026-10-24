# OSPA demonstration

## Flow A — Offline demonstration (no Oracle required)

Install from the root [README](../README.md), run the offline unit tests, list the SQL catalog and regenerate reports:

~~~sh
.venv/bin/python -m oracle_spa.cli list-queries
.venv/bin/python -m pytest -q tests/unit
.venv/bin/python -m oracle_spa.cli report-all --output results/phase5
~~~

Inspect the generated results/phase5/report.md using the [offline reproducibility instructions](development.md#workflow-a--offline-verification) after generation and compare medians/IQR/p95 against [raw public evidence](evidence/README.md). Build the EN/ES [portfolio](../portfolio/README.md), explore baseline/index/storage views and inspect estimated-plan disclosures. Source links open approved local public assets.

## Recruiter walkthrough — static portfolio (no database access)

Open the [public portfolio](https://oracle-performance-analyzer.pages.dev/)
(owner-reported deployment; live revision not independently verified) and select
EN or ES. Begin with the three-case readout: E01 email lookup (**−53.17%**
median client latency), E03 date range (**+25.24%** with an index range scan)
and E04 histogram (**2,500 → 2,500 E-Rows**, an unchanged estimate—not actual
operator row counts). Follow each case's **Inspect result** and evidence link.
Then explore the fuller Group A, baseline and storage views and the recorded
statistics restoration. These are historical small-profile observations; the
website executes no Oracle SQL, and this walkthrough requires no credentials.

## Flow B — Live Oracle laboratory demonstration (rootless Podman on Arch Linux)

This is a separately authorized lab flow, not a command to start or modify an existing container. Inspect the lab identity and data first; never reuse historical authorization or execute arbitrary SQL. A guarded, read-only catalog/estimated-plan demonstration is described by the CLI help and [query catalog](query-catalog.md). Mutating index/statistics experiments require new scoped approval and exact restoration checks.

Q01 selects a synthetic email: SELECT customer_id, full_name, email FROM customers WHERE email = :email. The historical E01 observation compares the same result before/after an email B-tree index. It does not prove a universal speedup. Group C actual cursor metrics remain unavailable/not verified. [Safety principles](security.md).
