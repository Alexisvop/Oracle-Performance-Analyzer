# Future Cloudflare Pages deployment — not authorized

No repository, Cloudflare project, domain, credential or deployment was created. Independent technical/security review and explicit owner approval are required before any publication. The future repository URL is pending in PUBLIC_REPOSITORY.json; its name is a proposal only. The original private development repository must remain private.

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

The local workflow performs checks only and has no deployment job or cloud credential. The existing private repository's GitHub Pages workflow was not changed. No Cloudflare login, GitHub App connection, domain configuration or remote builder was exercised.

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

The production preview binds to loopback. Browser tests use npm run test:browser from portfolio/. A compatible local Chrome may be selected with PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH; otherwise install Playwright Chromium. All active project source/evidence links use reviewed same-origin assets while the external repository URL remains pending.

Before any future approved deployment, verify the exact reviewed hashes, data, notices, EN/ES, keyboard navigation, mobile charts, source references, console and static output. Recheck the actual HTTPS origin after deployment; no hosted URL is verified now.

Official configuration references: [Cloudflare build settings](https://developers.cloudflare.com/pages/configuration/build-configuration/), [Node and install controls](https://developers.cloudflare.com/pages/configuration/build-image/), [branch deployment controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/).
