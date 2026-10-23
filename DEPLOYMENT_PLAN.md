# Cloudflare Pages integration and maintenance plan

The independent [public source repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) has been published. The owner reports an existing [Cloudflare Pages portfolio](https://oracle-performance-analyzer.pages.dev/). Automated requests returned HTTP 403; the deployed revision and account settings are NOT VERIFIED. No Cloudflare settings, credentials or deployments are changed by this integration review. PUBLIC_REPOSITORY.json records the completed source publication. The original private development repository must remain private.

## Prepared static configuration

| Setting | Proposed value |
| --- | --- |
| Root directory | portfolio |
| Build command | npm run build |
| Output directory | dist (relative to portfolio) |
| NODE_VERSION | 26.12.0, matching local validation |
| Dependency installation | Automatic npm installation using portfolio/package-lock.json; scripts disabled by portfolio/.npmrc |
| Vite base | / |
| Routing | Existing hash anchors; one EN/ES document; no history-router rewrite |
| Credentials/backend | None; no Oracle connection, Functions, server or private repository input |

The whole public checkout is a build input because curated evidence and reviewed source/docs are outside portfolio/. Deploy only portfolio/dist, including its explicitly allowlisted public source/evidence references and third-party notices. Never upload the staging root, audit data, environments, caches, node_modules, results or release archives.

## Manual publication gate

The current preparation targets GitHub integration for the independent public repository. The earlier direct-upload preference is superseded by this reviewed proposal; the earlier preparation performed no integration or upload. The existing hosting state is owner-reported; it is not evidence that this candidate branch has been deployed. See the [GitHub deployment runbook](docs/cloudflare-pages-deployment.md) for exact settings, authorization boundaries, validation and rollback. Restrict app access to the approved public repository. Cloudflare defaults can trigger production and preview publication; connecting the account, creating a project and choosing Save and Deploy require separate owner authorization.

The public GitHub Actions workflow performs offline checks only and its [initial hosted run](https://github.com/Alexisvop/Oracle-Performance-Analyzer/actions/runs/39892553663) passed. It has no deployment job or cloud credential. The export did not include the original private Pages workflow. The prior local preparation performed no Cloudflare operation. This final review reads public URLs only and does not change hosting settings or deploy.

## Local verification and preview

~~~sh
npm --prefix portfolio ci
npm --prefix portfolio run data:check
npm --prefix portfolio run typecheck
npm --prefix portfolio run lint
npm --prefix portfolio test
npm --prefix portfolio run build
npm --prefix portfolio run preview
~~~

The production preview binds to loopback. Browser tests use npm run test:browser from portfolio/. A compatible local Chrome may be selected with PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH; otherwise install Playwright Chromium. Source/evidence navigation continues to use reviewed same-origin assets, and the [public repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) is available independently.

Before any future approved deployment, verify the exact reviewed hashes, data, notices, EN/ES, keyboard navigation, mobile charts, source references, console and static output. Recheck the actual HTTPS origin after deployment; the owner-supplied HTTPS URLs currently return HTTP 403 to automated requests, so hosted acceptance is NOT VERIFIED.

Official configuration references: [Cloudflare build settings](https://developers.cloudflare.com/pages/configuration/build-configuration/), [Node and install controls](https://developers.cloudflare.com/pages/configuration/build-image/), [branch deployment controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/).
