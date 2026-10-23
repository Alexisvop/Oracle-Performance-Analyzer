# Proposed independent public repository — NO PUBLICATION AUTHORIZATION

Proposed name: Oracle-Performance-Analyzer. A read-only lookup of Alexisvop/Oracle-Performance-Analyzer returned 404 during local hardening; no name was reserved, and a 404 is not guaranteed availability. PUBLIC_REPOSITORY.json intentionally keeps url null until approved.

This is a future procedure only. Independent security/technical review and explicit owner authorization are required before Git initialization, an initial commit, repository creation or push. The original private repository must stay private and must never be used as the new checkout, Git object source, alternate object directory or remote.

## Approved layout

Use only the newly sealed release/ospa-public-review.tar.gz and its verified checksum. The source archive contains the explicit public allowlist, including LICENSE, THIRD_PARTY_NOTICES.md, Python/SQL/evidence/docs/frontend, public manifest and offline CI. It excludes .git, _private_audit, old review packages, environments, node_modules, caches, generated results and private operational material. Static deployment is a separate decision.

## Future owner-authorized commands — do not execute during preparation

The destination must not already exist and must not resolve into the original private checkout. Run these commands only after independent review and explicit authorization. Confirm the archive digest against the reviewer-approved digest before extraction.

~~~bash
set -euo pipefail
export OSPA_STAGING="$HOME/Documents/Workspace/Oracle-Performance-Analyzer-Public"
export OSPA_NEW_CHECKOUT="$HOME/Documents/Workspace/Oracle-Performance-Analyzer"
test ! -e "$OSPA_NEW_CHECKOUT"
test ! -L "$OSPA_NEW_CHECKOUT"
test "$(realpath -m "$OSPA_NEW_CHECKOUT")" = "$OSPA_NEW_CHECKOUT"
cd "$OSPA_STAGING/release"
sha256sum -c ospa-public-review.tar.gz.sha256
tar -tzf ospa-public-review.tar.gz
mkdir "$OSPA_NEW_CHECKOUT"
tar -xzf ospa-public-review.tar.gz --strip-components=1 -C "$OSPA_NEW_CHECKOUT"
cd "$OSPA_NEW_CHECKOUT"
sha256sum -c EXPORT_MANIFEST.sha256
python - <<'PY'
import hashlib, json
from pathlib import Path
root = Path.cwd()
manifest = json.loads((root / "EXPORT_MANIFEST.json").read_text())
approved = {r["destination_path"] for r in manifest["files"]}
approved.update({"EXPORT_MANIFEST.json", "EXPORT_MANIFEST.sha256"})
assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == approved
assert not any(p.is_symlink() for p in root.rglob("*"))
assert not (root / ".git").exists()
for row in manifest["files"]:
    p = root / row["destination_path"]
    assert not p.is_absolute() or p.is_relative_to(root)
    assert ".." not in Path(row["destination_path"]).parts
    assert hashlib.sha256(p.read_bytes()).hexdigest() == row["final_sha256"]
PY
git init --initial-branch=main
git add -- .
git diff --cached --stat
git commit -m "Initial sanitized OSPA public edition"
gh repo create Alexisvop/Oracle-Performance-Analyzer --public --source=. --remote=origin
git push -u origin main
~~~

The final three Git/GitHub commands create history and publish. They have NOT been executed. Recheck the remote name/availability and owner authorization immediately before running them. Review the prepared offline CI before enabling/running it; hosted workflow execution remains unverified. After owner selection of an actual URL, update PUBLIC_REPOSITORY.json through a reviewed change. Never add a private-origin remote or copy Git history. Cloudflare login, Git integration, domains, previews and deployment need a separate approval and are outside this procedure.
