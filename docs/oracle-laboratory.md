# Optional independent Oracle laboratory

This guide describes a new, separately owner-authorized synthetic lab. No setup, container, provisioning or database command below was executed for this export. Never reuse the original private environment, overwrite an existing object or treat historical receipts as current authorization.

## Environment and Oracle terms

Use a supported rootless Podman Linux host, adequate memory and at least 20 GiB free storage for the recorded environment. Review [Oracle Free Use Terms](https://www.oracle.com/downloads/licenses/oracle-free-license.html) before obtaining Oracle software. The historical linux/amd64 image is container-registry.oracle.com/database/free at digest sha256:c4d9b15a1b2240ce90730c23ce298fcdd34f6793792c1b3849181a080009c322. Its observed server version was 23.26.3.0.0; fresh image availability, provisioning and live behavior are not verified here.

Choose new container, volume and secret names, inspect whether they already exist, and stop if they do. Expose TCP only on 127.0.0.1:1521. Store the administrator password interactively in Podman secrets, without echo, command-line values or logging. The recorded image expects the secret file oracle_pwd. Preserve new persistent storage; never delete a volume as troubleshooting.

## Account and deterministic schema — gated mutations

Review scripts/provision.py before a separately approved first invocation. It reads passwords without echo, refuses an existing ORACLE_SPA user, verifies SYSTEM in FREEPDB1, and creates the dedicated identity with CREATE SESSION and a 1 GiB USERS quota. A separate, narrowly approved CREATE TABLE grant in FREEPDB1 is needed for the lab schema. Do not grant DBA roles or Group C fixed-view access.

Use .env.example as a layout only. Real credentials belong in an owner-owned regular .env file, exact mode 0600 and <=16 KiB, or process environment. The allowed example DSN is localhost:1521/FREEPDB1 and application user ORACLE_SPA. No password is supplied by this distribution.

Review the [schema](../sql/01_schema.sql), [profiles](../config/datasets.json), CLI help and fresh empty-lab identity. Only after independent authorization for each mutation:

~~~sh
.venv/bin/python -m oracle_spa.cli init-schema
.venv/bin/python -m oracle_spa.cli load-data --profile small --seed 20261016
.venv/bin/python -m oracle_spa.cli gather-stats
~~~

Those commands are not safe to repeat automatically. DDL may commit implicitly; on uncertain outcomes, stop and inspect read-only. Do not reset an existing dataset.

Expected business counts: 2,000 CUSTOMERS, 500 PRODUCTS, 10,000 ORDERS and 30,000 ORDER_ITEMS plus one OSPA_DATASET metadata row. The generator reference date is fixed at 2026-10-16. On the newly owned/configured lab, doctor and validate-data verify identity, schema and deterministic checksums. Approved queries and independent correctness checks are in the [catalog](query-catalog.md).

## Experiments and verification limits

Read [experiments](experiments.md) and [methodology](benchmark-methodology.md) before execution. B-tree/statistics changes, export/import/gather/recovery, privileges and container operations require new specific authorization and baseline preservation. Recorded receipts and object IDs are historical observations, not permission tokens.

EXPLAIN PLAN captures estimates, not privileged runtime counters. Offline historical reports work without any lab operation. Fresh Oracle integration, timing equivalence on another host and new histogram/index experiments remain NOT VERIFIED. [Offline workflow](development.md), [security](security.md), [evidence](evidence/README.md).
