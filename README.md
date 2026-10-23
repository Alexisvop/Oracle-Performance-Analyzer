# Oracle SQL Performance Analyzer — Public Edition

A reproducible database performance engineering laboratory with a bilingual React portfolio.

**Published public source edition:** [Oracle-Performance-Analyzer](https://github.com/Alexisvop/Oracle-Performance-Analyzer) is an independent, sanitized codebase licensed under MIT. It includes reviewed historical evidence and explicitly labeled public derivatives with verifiable SHA-256 provenance. Private development history, personal context, credentials and host diagnostics are excluded. **Public portfolio:** [oracle-performance-analyzer.pages.dev](https://oracle-performance-analyzer.pages.dev/), reported published by the owner. Automated hosted verification currently receives HTTP 403; this branch has not been verified as the deployed revision. Local reproduction remains available. See [provenance](docs/provenance.md), [MIT license](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).

> OSPA is an independent educational and engineering project. It is not an official Oracle product and is not affiliated with or certified by Oracle Corporation. It does not replace Oracle Real Application Testing, SQL Performance Analyzer or SQL Tuning Advisor.

## Engineering scope

OSPA investigates SQL plans, selectivity, B-tree indexes, optimizer statistics and descriptive benchmarking. The Python CLI uses python-oracledb Thin mode with an approved query catalog and explicit safety guards. Offline reports and the website need no Oracle connection.

The reproducible small dataset uses seed 20261016: 2,000 customers, 500 products, 10,000 orders and 30,000 order items — **42,500 business rows**. OSPA_DATASET holds one additional metadata row. Eight catalog queries have ten variants. Five experimental indexes were evaluated in isolated historical blocks.

Implemented phases cover connectivity/diagnostics; deterministic datasets/schema validation; query correctness/estimated plans; benchmark/index/histogram experiments with exact statistics recovery; offline reports/tests/CI. Privileged runtime cursor metrics (Group C), bind peeking inspection, advanced diagnostics, multi-scale experiments and Engineering Challenges remain **Not Implemented / Future Work**.

## Install and verify offline

Use Python 3.14 for the validated pinned dependency environment; the package metadata requires Python >=3.12. Oracle installation is unnecessary for this flow.

~~~sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python -m pip check
.venv/bin/python -m oracle_spa.cli --help
.venv/bin/python -m oracle_spa.cli list-queries
env -u ORACLE_DSN -u ORACLE_USER -u ORACLE_PASSWORD .venv/bin/python -m pytest -q tests/unit
env -u ORACLE_DSN -u ORACLE_USER -u ORACLE_PASSWORD .venv/bin/python -m oracle_spa.cli report-all --output results/phase5
~~~

Generated artifacts are ignored local output, not committed source files. Follow the [offline reproducibility instructions](docs/development.md#workflow-a--offline-verification) to create results/phase5/report.md, measurements.csv, comparisons.csv, manifest.json and charts/. These artifacts are unavailable immediately after a clean clone. The portfolio builds from committed public inputs without requiring this output directory.

## Portfolio

~~~sh
npm --prefix portfolio ci
npm --prefix portfolio run data:check
npm --prefix portfolio run typecheck
npm --prefix portfolio run lint
npm --prefix portfolio test
npm --prefix portfolio run build
npm --prefix portfolio run dev
~~~

Open the loopback URL printed by Vite. English is the default; EN/ES switches the same document. Vite base is / for future root-hosted Cloudflare Pages. The site serves reviewed local evidence/documentation/source references; it does not link to the private repository. The [public repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) is available; the owner has supplied the Cloudflare Pages URL above. GitHub Pages is not used. [Frontend guide](portfolio/README.md).

## Results and interpretation

All reported timings are end-to-end **client execute + complete-fetch latency**, including driver/Python materialization, in milliseconds. Measurements are descriptive sequential blocks on a small synthetic dataset: cache, order and host load are confounders, so they do not establish causal or universal speedups.

| Index experiment | Median before -> after (ms, rounded) | Change |
| --- | --- | --- |
| E01 email | 0.931 -> 0.436 | -53.17% |
| E02 simple customer | 1.699 -> 0.954 | -43.85% |
| E02 composite customer/date | 1.593 -> 1.156 | -27.43% |
| E03 TRUNC | 2.983 -> 3.091 | +3.63% |
| E03 range | 1.433 -> 1.794 | +25.24% |
| E05 Top-N | 1.884 -> 2.087 | +10.77% |

Percentages are computed from unrounded medians. Favorable and unfavorable observations are retained. E03 range selected an index and was slower; E05 kept the optimizer's full-scan choice. E04 compares PAID before/after and CANCELLED before/after separately; those cohorts are different workloads. EXPLAIN PLAN estimates, including E04 E-Rows = 2,500 with bind placeholders, are not actual cursor metrics. Optimizer cost is not milliseconds. See [methodology](docs/benchmark-methodology.md), [findings](docs/findings.md), [results](docs/phase4-results.md) and [public evidence inventory](docs/evidence/README.md).

## Documentation

- [Architecture](docs/architecture.md)
- [Technical specification](PROJECT_SPEC.md)
- [SQL catalog](docs/query-catalog.md)
- [Experiment catalog](docs/experiments.md)
- [Offline and Oracle demonstrations](docs/demo.md)
- [Development and CI](docs/development.md)
- [Public evidence summary / resumen técnico](docs/portfolio-summary.md)
- [Phase 4 closure summary](docs/phase4-final-audit.md)
- [Phase 5 closure summary](docs/phase5-final-audit.md)
- [Acceptance and limitations](docs/acceptance.md)
- [Public engineering log](docs/engineering-log.md)
- [Security principles](docs/security.md)
- [Contributor safety rules](AGENTS.md)

## Tests, security and licensing

Historical Phase 5 evidence records 180 offline unit tests and 55 subtests; four live integration tests belong to an earlier, separately authorized lab audit. Those are historical counts, not proof of a fresh live execution. The [initial public GitHub Actions run](https://github.com/Alexisvop/Oracle-Performance-Analyzer/actions/runs/39892553663) passed. Pre-publication outcomes remain in the historical release checklist; immutable export manifests and validation records are explained in [provenance](docs/provenance.md#initial-export-snapshot-and-later-maintenance). CI executes offline only; it downloads no Oracle database and holds no database credential.

Keep real credentials local in an owner-owned regular .env file with mode 0600, or supply environment variables. Only .env.example is public. Never run provisioning, reset, DDL, DML, index or DBMS_STATS operations without new, narrowly scoped authorization. Historical receipts cannot authorize repetition. Oracle integration tests are separately marked/gated.

Owner-confirmed original code and documentation are MIT licensed, Copyright (c) 2026 Alexis Abraham Perez Olvera. Third-party code, icons, Oracle software/materials and trademarks retain their own terms; the MIT grant does not relicense them. Oracle binaries, container layers, wallets and data files are not included. The factual synthetic observations are labeled original/derivative in [evidence provenance](docs/evidence/PROVENANCE.json).
