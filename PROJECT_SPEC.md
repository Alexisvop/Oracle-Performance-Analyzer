# Public technical specification

This sanitized specification describes the implemented OSPA laboratory and its limits; it contains no private conversations or development-agent prompts.

## Implemented system

Python CLI -> approved SQL catalog and deterministic dataset/schema validation -> python-oracledb Thin -> owner-controlled Oracle laboratory. Query correctness uses independent Python/SQLite expectations. Estimated plans are captured with EXPLAIN PLAN / DBMS_XPLAN; the benchmark records perf_counter_ns client execute + full-fetch samples. Offline analysis regenerates JSON, CSV, Markdown and scientific charts. React/TypeScript renders reviewed public observations in EN/ES.

Synthetic profile small, seed 20261016: 42,500 business rows across CUSTOMERS, PRODUCTS, ORDERS and ORDER_ITEMS, plus one OSPA_DATASET record. Eight queries/ten variants; five historical experimental B-tree indexes; Stage A baselines, Group A index blocks and Group B same-cohort E04 histogram observations.

## Evidence contract

Keep sample counts, timestamps, latencies, SQL/result hashes, estimated plans and restoration observations intact. Public metadata derivatives are not byte-identical to private originals; mappings are recorded in [PROVENANCE.json](docs/evidence/PROVENANCE.json). Forty inputs drive Python report generation; 44 drive frontend curation. Additional closed fixtures exercise forensic and safety guards offline.

Client latency is not server CPU time; optimizer cost is not milliseconds; estimated E-Rows are not actual A-Rows. Sequential blocks have cache/order/host confounders. PAID and CANCELLED are not equivalent-result comparisons.

## Safety and deferred scope

No production/personal data. No arbitrary benchmark SQL. Check schema/PDB identity and approved allowlists before any lab operation. DDL has implicit commits and any attempted mutation consumes its specific authorization; stop on uncertain outcomes. This public preparation authorizes no Oracle operation, publication or Git history action.

Group C runtime cursor metrics, bind peeking inspection, advanced optimizer diagnostics, multi-scale experiments and Engineering Challenges are not implemented in this edition. See [architecture](docs/architecture.md), [methodology](docs/benchmark-methodology.md), [security](docs/security.md) and [development](docs/development.md).
