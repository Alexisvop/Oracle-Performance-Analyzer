# Security principles

Use synthetic data only, explicit query/object allowlists, loopback-only Oracle access and a least-privilege dedicated lab identity. Do not benchmark arbitrary SQL. Never embed a credential in a command, log, screenshot, source file, static asset or report. The public .env.example has an empty password.

Offline report/site/test flows need no Oracle credential or connection. Historical receipts and object IDs are observations for guard regressions, not current secrets or reusable authorizations. Oracle object IDs in closed fixtures are retained where tests verify the precise object graph; host/container identities are excluded.

Any new provisioning, load/reset, DDL, DML, DBMS_STATS, privilege or container mutation requires separate narrowly scoped owner approval. Oracle DDL may commit implicitly; stop on uncertain outcomes and do not retry/clean up automatically.

EXPORT_MANIFEST.json records the initial approved export; subsequent changes require ordinary Git review without rewriting that historical snapshot. _private_audit, local environments, caches, node_modules, results, release archives and browser logs/screenshots remain excluded from distribution. The [public repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) was initialized with independent history; no original .git directory or private history was copied. Local evidence navigation remains available. Source publication is complete; website deployment is separately gated.

[Contributor rules](../AGENTS.md), [development](development.md), [provenance](provenance.md).
