# Contributor and automation safety

Read README.md and PROJECT_SPEC.md before changes. This public edition contains no private operational handoff or historical authorization grants.

- Treat historical evidence as read-only. Preserve samples, results, timestamps and unfavorable observations.
- Run offline unit tests and report regeneration first. Do not connect to Oracle during offline checks.
- Require explicit owner approval for every database mutation, provisioning, container operation, Git publication and deployment. Historical approvals are consumed and non-reusable.
- Never expose credentials, private keys, environment files or workstation identities.
- Distinguish client latency, estimated plans and actual cursor metrics. Group C and Engineering Challenges remain deferred.
- Keep reviewed source/evidence navigation available locally. PUBLIC_REPOSITORY.json records the published source URL; website deployment remains separately gated.
- The _private_audit, .venv, node_modules, caches, results and release directories are local-only and must never be published.
