# Cloudflare Pages with GitHub — integration and operations runbook

This runbook targets only [Alexisvop/Oracle-Performance-Analyzer](https://github.com/Alexisvop/Oracle-Performance-Analyzer). The owner reports an existing deployment at https://oracle-performance-analyzer.pages.dev/ and the version URL https://8838874e.oracle-performance-analyzer.pages.dev/. Automated HTTPS requests to both returned HTTP 403; the live revision and account settings are NOT VERIFIED. The earlier local preparation performed no hosting operation, and this final task changes no Cloudflare setting or credential. Obtain independent technical review and explicit owner authorization before performing the remote steps below. Creating the Git integration and selecting Save and Deploy can publish immediately; do not treat setup as an offline operation.

## Exact configuration

| Setting | Value |
| --- | --- |
| Git provider / repository | GitHub / Alexisvop/Oracle-Performance-Analyzer |
| Production branch | main |
| Framework preset | Vite / React (Vite), according to dashboard label |
| Root directory | portfolio |
| Build command | npm run build |
| Build output directory | dist |
| Build image | v3 |
| NODE_VERSION | 26.12.0 |
| Dependency install | Enabled; npm with committed package-lock.json |
| SKIP_DEPENDENCY_INSTALL | Unset; do not carry over the old value 1 |
| Dependency lifecycle scripts | Disabled by portfolio/.npmrc |
| Preview branches | None unless separately authorized |
| Automatic production deployments | Disabled after initial setup unless explicitly authorized |
| Functions, secrets, bindings, analytics, custom domain | None |

The Node version file is portfolio/.node-version; set NODE_VERSION identically in the dashboard. The broad package.json engines range is not the runtime pin. Cloudflare starts install/build from portfolio, but the complete public checkout is required: evidence, SQL, source and documentation outside that folder are build inputs. Deploy only dist from inside portfolio. Do not upload the repository root or set output to `..`.

Cloudflare manages dependency installation before the build command. Verify in the first authorized hosted build that it uses the committed npm lock and does not mutate versions or execute install scripts. If the platform changes package-manager behavior, stop and review the log; do not silently switch to unpinned installation. Local validation uses npm ci; hosted installer equivalence is not yet verified. The native optional packages used by Vite work locally with lifecycle scripts disabled.

Official references: [build settings](https://developers.cloudflare.com/pages/configuration/build-configuration/) and [runtime overrides](https://developers.cloudflare.com/pages/configuration/build-image/).

## Local verification before authorization

From portfolio, using Node 26.12.0 and existing locked dependencies:

```sh
node --version
npm ci
npm run data:check
npm run typecheck
npm run lint
npm test
npm run build
npm run test:browser
```

A compatible installed Chromium may be supplied using PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH. No browser installation or Oracle service is needed in Cloudflare: browser tests belong to the local/CI verification gate, not the production build. npm run build validates the data, typechecks, builds with Vite, then audits dist. Run npm run audit:dist again to print the sorted SHA-256 inventory. Build twice and compare all paths and digests; preserve the inventories outside dist.

The output audit compares approved source assets, evidence and notices with their current public inputs. It rejects unexpected files, symlinks, altered reference assets and common secret/private-path/tracker patterns. Its pattern scan cannot establish absolute absence of all confidential strings; manually review the source allowlist as well. Do not expand portfolio/public-source-files.json to include interview preparation, prompts, internal audits or private operational records. A directory's presence in a public checkout does not authorize adding it to the website.

Historical EXPORT_MANIFEST.json and its checksum remain an immutable initial-export snapshot; do not regenerate them for frontend changes. Verify their own checksum and all evidence provenance hashes. Current deployment artifacts have a separate local sorted hash inventory from audit:dist.

## Initial connection procedure — only if not already connected

Do not repeat initial project creation on an existing integration. First inspect the existing project read-only in the dashboard; account-specific access and settings are not available to this audit. The following initial-setup steps are retained for an owner-authorized setup only.

1. Review the exact public commit to deploy and its passing GitHub Actions checks. Confirm main contains the approved frontend changes; uncommitted local work cannot be deployed from GitHub.
2. In Cloudflare Workers & Pages select Create application, then Pages, then Connect to Git. Use the Pages static-site flow, not a Workers deployment. Choose GitHub and the Alexisvop account.
3. Review the Cloudflare Workers & Pages GitHub App permissions. Choose Only select repositories and grant access solely to Oracle-Performance-Analyzer. Never choose all repositories or the original private project. If narrower access is unavailable, stop for review.
4. Select the exact repository and enter the configuration table above. Keep the project name/hostname as an owner decision; no pages.dev URL or domain is reserved by this document. Inspect all variables: only the non-secret runtime pin is needed. Do not add Oracle credentials, API tokens or VITE_* secrets.
5. Stop before Save and Deploy unless authorization specifically covers the first public deployment. There is no verified promise that project creation is a non-publishing draft mode.
6. After an authorized first deployment, open Settings > Builds & deployments / Branch control. Set production branch main, disable automatic production deployments and set preview branches to None unless the owner expressly approved those automation scopes. Save and verify the controls before further pushes or pull requests. If setup exposes these controls before the first deployment, set them there too. Avoid pushes during initial setup.

The GitHub App connection itself is not performed during this task. Cloudflare defaults can deploy both production and preview changes. Source: [Git setup](https://developers.cloudflare.com/pages/get-started/git-integration/), [GitHub access scope](https://developers.cloudflare.com/pages/configuration/git-integration/github-integration/), [branch controls](https://developers.cloudflare.com/pages/configuration/branch-build-controls/).

## Routing and hosted acceptance

Vite base is `/`. This application uses section hashes on one document; it has no history router or separate EN/ES paths. Do not invent /en, /es, /results or a catch-all rewrite. Direct root bookmarks such as /#results must work after refresh. EN/ES changes the current document and html lang; a fresh page defaults to English. Source pages use explicit /source/... paths, and evidence uses /data/evidence.json.

After a separately authorized deployment:

- Record the deployment ID, commit, build log, Node version and actual HTTPS URL. Confirm the selected project is Pages and the output was dist only.
- Open `/`, `/#results`, `/#docs`, `/source/index.html`, `/source/README.md.html` and `/data/evidence.json` directly and after refresh. Cloudflare can canonicalize .html URLs; verify redirects preserve the correct page and fragment. Do not count an HTML fallback response as valid JSON or a JavaScript asset.
- Check English default, EN/ES switching, keyboard menu/skip link, charts/tables and desktop/tablet/mobile layouts. Inspect console/network for errors and unapproved third-party requests.
- Verify the public GitHub link, approved source/evidence links and all six license notices. Confirm deferred Group C and Engineering Challenges remain labeled future work.
- Compare published asset bytes with the approved local inventory, including decoded response bodies if HTTP compression is used. Confirm no additional tracker/analytics script was injected by platform settings.
- Keep preview publication and automatic production triggers disabled until separately authorized. A successful local test is not a hosted acceptance result.

No _redirects, Functions, Wrangler deployment config, GitHub deployment workflow or hosting token is required for this static hash-navigation site.

## Disable automation, rollback and exposure response

These are owner-operated incident procedures after deployment authorization, not actions performed now.

1. Freeze automation: in the project's branch controls uncheck Enable automatic production branch deployments and set preview branches to None; save. Cancel any queued/running deployment where available. Disabling builds does not remove an already published site or existing preview URLs.
2. For a regression with a known safe production version, go to Deployments > All deployments, select the safe successful production deployment's three-dot menu, then Rollback to this deployment and confirm. Preview deployments are not eligible rollback targets. Record the target ID/commit and retest the live URL. Leave automatic deployments disabled to prevent the next push from replacing the rollback. [Official rollback procedure](https://developers.cloudflare.com/pages/configuration/rollbacks/).
3. Rollback does not erase retained deployment-specific URLs. If confidential material was exposed, keep logs/IDs without reproducing the secret, notify the owner and rotate any affected credentials through their authorized issuer. Obtain explicit approval to remove affected deployment artifacts/URLs. Do not assume rollback or removing a custom domain eliminates pages.dev access.
4. If there is no safe prior deployment or full takedown is required, obtain explicit owner authorization for project/deployment removal. Follow the [official project-removal procedure](https://developers.cloudflare.com/pages/get-started/git-integration/); review custom-domain DNS cleanup first if any domain was later attached. Deletion is destructive and is not authorized by this runbook.
5. Correct the source through an independently reviewed public PR, rerun local/CI checks and obtain approval for redeployment. Re-enable automation only under its own approved scope. Do not rewrite Git history to respond to a hosting regression.

## Current readiness

The candidate is being prepared for PR review; the owner reports an existing public site. Cloudflare's hosted installer, account permissions, selected hostname, redirects and live rollback remain NOT VERIFIED until a separately authorized remote operation. No interview material, original private repository input, Oracle connection or tracking service is required by this design.

## Historical local preparation validation record

Base: public main commit 2d920f16184a24965911a4a0cb9b281c4b58baee; working branch feature/cloudflare-pages. Main includes the approved post-publication documentation maintenance. The source allowlist, measurements, historical evidence, MIT license and third-party notices are unchanged.

Validation used Node 26.12.0 and npm 12.2.1. These results describe the earlier preparation, not a fresh final run. Final-run results are recorded in docs/final-production-readiness.md. The exact Node runtime was obtained from nodejs.org, checked against its official SHASUMS256.txt, and isolated locally without changing the system runtime. The linux-x64 archive SHA-256 was fd47865ecd6391ebb431fc815e01b9135bf83ded5cf373247e9331e196b7aded. This is an official-source integrity check, not an independent attestation of the toolchain.

| Check | Result | Exit code |
| --- | --- | ---: |
| npm ci | Lockfile installation; lifecycle scripts disabled; zero vulnerabilities reported by npm | 0 |
| npm run data:check | 44 input hashes, 23 measurements, eight same-result comparisons | 0 |
| npm run typecheck | PASS | 0 |
| npm run lint | PASS | 0 |
| npm test | 14 tests passed | 0 |
| npm run build, twice | Both builds and output audits passed; 139 byte-identical assets | 0 |
| npm run test:browser | 18 scenarios passed across desktop, tablet and mobile; EN/ES, keyboard, links and axe assertions passed | 0 |
| Independent output negative checks | Private extra file, altered evidence, synthetic token, tracker and symlink all rejected | 0 |
| Generated HTML references | 359 local links/assets/fragments resolved | 0 |
| Historical integrity | Manifest checksum and 61 public provenance hashes matched | 0 |
| Markdown audit | 187 repository links checked; 30 external URLs classified | 0 |
| Offline Python unit tests | 198 tests and 55 subtests passed | 0 |
| git diff --check | No whitespace errors | 0 |

Sorted path-to-SHA256 inventory digest: 88e93d0928afd8ba8b3ba45264b3943f907e90b8e4873fffd93f1bdf413d7194, calculated over Python json.dumps(inventory, sort_keys=True). The inventory and command/exit-code logs are local-only under .cache/docs-cleanup. They are outside dist and excluded from Git.

The Markdown auditor explicitly adds this new guide to its reviewed paths; it does not rewrite EXPORT_MANIFEST.json or relax missing-file, traversal, symlink or generated-output checks. Final link audit, offline Python tests and whitespace checks are recorded in the local review results. No hosting credential or Oracle connection was used. Hosted verification and account-specific rollback remain pending owner authorization.
