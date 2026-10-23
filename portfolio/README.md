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

The root Vite base / is suitable for a future Cloudflare origin-root deployment. The production directory is portfolio/dist. A strict source asset list emits only reviewed code, documentation/evidence and third-party notices as local static references; no private URL is required. The [public source repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) is available. The portfolio currently runs locally; Cloudflare Pages has not been deployed; deployment still requires separate owner authorization. No automatic deployment workflow exists.

The evidence exporter checks 44 input hashes, 23 measurements and eight equivalent-result comparisons. Forty public inputs also regenerate the independent Python report bundle. Inputs are committed public source, not ignored results. Historical 180/55 test counts remain labeled historical; the [initial public CI run](https://github.com/Alexisvop/Oracle-Performance-Analyzer/actions/runs/39892553663) records the release verification.

[Project README](../README.md), [architecture](../docs/architecture.md), [evidence](../docs/evidence/README.md), [notices](../THIRD_PARTY_NOTICES.md), [security](../docs/security.md).
