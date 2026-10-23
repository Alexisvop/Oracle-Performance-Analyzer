# Future Cloudflare Pages deployment — not authorized

The independent [public source repository](https://github.com/Alexisvop/Oracle-Performance-Analyzer) has been published. No Cloudflare project, domain, deployment credential or website deployment has been created. Website deployment requires separate review and explicit owner approval; this plan does not authorize it. PUBLIC_REPOSITORY.json records the completed source publication. The original private development repository must remain private.

## Prepared static configuration

| Setting | Proposed value |
| --- | --- |
| Root directory | Repository root / blank |
| Build command | npm --prefix portfolio ci && npm --prefix portfolio run build |
| Output directory | portfolio/dist |
| NODE_VERSION | 26.12.0, matching local validation |
| SKIP_DEPENDENCY_INSTALL | 1, for the explicit locked frontend installation |
| Vite base | / |
| Routing | Existing hash anchors; one EN/ES document; no history-router rewrite |
| Credentials/backend | None; no Oracle connection, Functions, server or private repository input |

The whole public checkout is a build input because curated evidence and reviewed source/docs are outside portfolio/. Deploy only portfolio/dist, including its explicitly allowlisted public source/evidence references and third-party notices. Never upload the staging root, audit data, environments, caches, node_modules, results or release archives.

## Manual publication gate

Prefer an independently approved static-artifact upload for a future first release; it does not require automatic Git integration. No upload command is authorized by this document. If Git integration is later chosen, restrict app access to the approved public repository and explicitly review production/preview branch controls before connecting or saving a configuration. Cloudflare defaults can trigger builds/deployments on commits; automatic production and preview publication must remain disabled unless separately approved.

The public GitHub Actions workflow performs offline checks only and its [initial hosted run](https://github.com/Alexisvop/Oracle-Performance-Analyzer/actions/runs/39892553663) passed. It has no deployment job or cloud credential. The export did not include the original private Pages workflow. No Cloudflare login, hosting integration, domain configuration, Cloudflare build or website deployment has been performed.

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

Before any future approved deployment, verify the exact reviewed hashes, data, notices, EN/ES, keyboard navigation, mobile charts, source references, console and static output. Recheck the actual HTTPS origin after deployment; no hosted URL is verified now.

Official configuration references: [Cloudflare build settings](https://developers.cloudflare.com/pages/configuration/build-configuration/), [Node and install controls](https://developers.cloudflare.com/pages/configuration/build-image/), [branch deployment controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/).
