# OSPA bilingual public portfolio

React, TypeScript, Vite, Tailwind CSS and Lucide. English is default; EN/ES changes one document. CSS/SVG charts include precise tables, unfavorable observations and methodology limits. No backend, Oracle connection, tracker or external font.

~~~sh
npm ci
npm run data:check
npm run typecheck
npm run lint
npm test
npm run build
npm run test:browser
npm run dev
~~~

Use Node 26.12.0 for the locally validated environment. Playwright uses its Chromium installation or PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome-stable when available. Unit and browser tests cover numbers/data hashes, EN/ES, local references, keyboard controls, charts, layouts and axe accessibility checks.

The root Vite base / is suitable for a future Cloudflare origin-root deployment. The production directory is portfolio/dist. A strict source asset list emits only reviewed code, documentation/evidence and third-party notices as local static references; no private URL is required. The [public source repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) is available. The owner reports the [Cloudflare Pages portfolio](https://oracle-performance-analyzer.pages.dev/) as published. Automated hosted requests returned HTTP 403, so the live revision and account settings remain NOT VERIFIED. Local preview remains available. Git integration may deploy automatically; no GitHub Actions deployment job exists. This task changes no Cloudflare settings.

The evidence exporter checks 44 input hashes, 23 measurements and eight equivalent-result comparisons. Forty public inputs also regenerate the independent Python report bundle. Inputs are committed public source, not ignored results. Historical 180/55 test counts remain labeled historical; the [initial public CI run](https://github.com/Alexisvop/Oracle-Performance-Analyzer/actions/runs/39892553663) records the release verification.

[Project README](../README.md), [architecture](../docs/architecture.md), [evidence](../docs/evidence/README.md), [notices](../THIRD_PARTY_NOTICES.md), [security](../docs/security.md).

## Prepared Cloudflare Pages settings

Root directory: portfolio; framework: Vite (React); production branch: main; build command: npm run build; output: dist; NODE_VERSION: 26.12.0. The .node-version file pins that runtime and .npmrc disables dependency lifecycle scripts. Keep Cloudflare's automatic dependency installation enabled and use the committed package-lock.json. Local verification uses npm ci.

The build ends with npm run audit:dist: it verifies the exact output inventory, approved public source bytes, notices and common secret/private-path patterns. It rejects symlinks, unapproved extra files and interview materials. A successful build is local preparation, not deployment authorization. The connection, branch controls, rollback and hosted acceptance procedure is documented at docs/cloudflare-pages-deployment.md in the repository root; that operations guide is not part of the website source allowlist.
