# Public engineering log

This is a sanitized public summary, not the private operational journal. Phases 1–3 established guarded connectivity, deterministic synthetic schema/data, approved queries, independent correctness and estimated plans. Phase 4 retained baseline/index/histogram observations, unfavorable outcomes and exact recovery. Phase 5 established offline reports, integrity checks, tests and CI.

The public edition excludes internal prompts, personal context, host diagnostics and Git history. Metadata derivatives are explicitly mapped; measurements and original private records are unchanged. No consumed authorization grants a future operation. [Evidence provenance](evidence/PROVENANCE.json), [methodology](benchmark-methodology.md), [acceptance](acceptance.md).

## 2026-10-23 — Public repository maintenance and recruiter presentation

Public source is available on [GitHub](https://github.com/Alexisvop/Oracle-Performance-Analyzer).
PR #2, the guarded Cloudflare build integration, merged to `main` at
`8b78d2d2910ec49f0a4a3135584714e87cbcacd2`; corresponding offline CI
passed. The owner reports publication at
[oracle-performance-analyzer.pages.dev](https://oracle-performance-analyzer.pages.dev/),
but automated requests return HTTP 403. Public site revision and headers have
not been independently verified, and this record creates no new deployment
or Oracle-operation authorization.

The portfolio now highlights three historical, provenance-backed cases: E01
lower observed median latency, E03 higher observed median despite an index scan,
and E04 unchanged estimated cardinality after histogram collection. English and
Spanish copy is derived exclusively from the existing curated evidence; no
runtime cursor metrics, new database operations or measurements are claimed.
Historical Phase 4 JSON and immutable release manifests remain untouched.
