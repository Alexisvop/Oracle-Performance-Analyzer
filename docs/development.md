# Development and reproducibility

## Workflow A — Offline verification

~~~sh
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q src scripts tests
env -u ORACLE_DSN -u ORACLE_USER -u ORACLE_PASSWORD .venv/bin/python -m pytest -q tests/unit
env -u ORACLE_DSN -u ORACLE_USER -u ORACLE_PASSWORD .venv/bin/python -m oracle_spa.cli report-all --output results/phase5
~~~

Generated files are not available immediately after a clean clone. The command above creates results/phase5/report.md, summary.json, measurements.csv, comparisons.csv, manifest.json and eight charts (SVG/PNG). No generated assets need to be committed.

Run python scripts/check_documentation_links.py to audit committed documentation references. Only the exact report output names declared by that checker may be classified as optional generated files; other missing targets, traversal and symlinks fail.

Run the report a second time into a separate safe directory and compare summary.json, measurements.csv, comparisons.csv, report.md, chart bytes and manifest digests. Both bundles must verify all 40 public input hashes and 12 generated output hashes. Public input hashes identify derivatives where declared; they do not falsely claim equality with private source bytes.

## Workflow B — Oracle laboratory, separately authorized

Use a dedicated synthetic Oracle Free lab, python-oracledb Thin, PDB FREEPDB1 and least-privilege ORACLE_SPA. The documented DSN localhost:1521/FREEPDB1 is an example loopback service without a password. Keep TCP exposed only on loopback. Set credentials interactively outside Git; .env must be owner-owned, regular and mode 0600.

Inspect existing schema/data before any action. Creating users/tables/indexes, loading/resetting data, collecting/importing statistics and container operations require new specific authorization. Do not run scripts/provision.py or integration tests against an existing lab as a troubleshooting shortcut. No live Oracle verification is part of public-release checks.

## Frontend and CI

Use Node 26.12.0 for the locally validated environment. npm ci uses portfolio/package-lock.json. Run data:check, typecheck, lint, test, build and test:browser from portfolio/. Playwright can use PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome-stable on compatible Linux hosts. Otherwise install its Chromium locally. [Frontend details](../portfolio/README.md).

The workflow .github/workflows/ci.yml runs Python offline tests/report regeneration and frontend checks with contents: read. It has no Oracle service, privileged secret, deployment job or private-source access. Git initialization is not required for local verification.

[Security](security.md), [demonstration](demo.md), [architecture](architecture.md), [evidence](evidence/README.md).

[Independent Oracle laboratory prerequisites and gated setup](oracle-laboratory.md).
