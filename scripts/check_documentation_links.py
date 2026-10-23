"""Audit public Markdown links without requiring ignored report outputs."""
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit, unquote
import argparse
import json
import re

REPORT_COMMAND = ".venv/bin/python -m oracle_spa.cli report-all --output results/phase5"
GENERATED_OUTPUTS = frozenset({
    "report.md", "measurements.csv", "comparisons.csv", "summary.json", "manifest.json",
    *("charts/" + stem + "." + ext
      for stem in ("stage_a_baselines", "group_a_index_comparisons",
                   "group_a_storage_vs_latency", "group_b_e04_status_and_cohorts")
      for ext in ("svg", "png")),
})


def safe_path(root: Path, path: Path) -> Path:
    """Check lexical containment and every existing component before resolving."""
    root = root.resolve()
    if not path.is_relative_to(root):
        raise ValueError("Link escapes public root")
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError("Symlink in documentation path")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Link resolves outside public root")
    return path


def classify_link(root: Path, document: str, target: str, approved: set[str]) -> str:
    root = root.resolve()
    if "\\" in target or any(ord(c) < 32 for c in target):
        raise ValueError("Unsafe link characters")
    uri = urlsplit(target)
    if uri.scheme in ("https", "http"):
        if not uri.hostname or uri.username or uri.password:
            raise ValueError("Unsafe external URL")
        return "external"
    if uri.scheme or uri.netloc or uri.query:
        raise ValueError("Unsupported link URL")
    raw = uri.path
    if unquote(raw) != raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("Encoded or absolute link path")
    parts = list(PurePosixPath(document).parent.parts)
    seen_normal = False
    for component in raw.split("/") if raw else []:
        if component in ("", "."):
            continue
        if component == "..":
            if seen_normal or not parts:
                raise ValueError("Unsafe path traversal")
            parts.pop()
        else:
            seen_normal = True
            parts.append(component)
    relative = "/".join(parts) if raw else document
    path = safe_path(root, root / relative)
    if relative.startswith("results/phase5/"):
        output = relative.removeprefix("results/phase5/")
        if output not in GENERATED_OUTPUTS:
            raise ValueError("Unexpected generated output")
        if uri.fragment:
            raise ValueError("Unverified generated fragment")
        return "generated"
    if relative not in approved or not path.is_file():
        raise ValueError("Missing or unapproved repository file")
    if uri.fragment:
        if path.suffix != ".md":
            raise ValueError("Unverified non-Markdown fragment")
        headings = set()
        for line in path.read_text().splitlines():
            match = re.match(r"^#{1,6} (.+)$", line)
            if match:
                headings.add(re.sub(r"[^\w\s-]", "", match[1].lower()).replace(" ", "-"))
        if unquote(uri.fragment) not in headings:
            raise ValueError("Missing Markdown heading")
    return "repository"


def markdown_targets(text: str):
    fenced = False
    for line in text.splitlines():
        if re.match(r"^\s*(~~~|`{3})", line):
            fenced = not fenced
        elif not fenced:
            yield from re.findall(r"\[[^\]]+\]\(([^)]+)\)", line)


def audit(root: Path, approved: set[str]) -> dict:
    counts = {"repository": 0, "generated": 0, "external": 0}
    for name in sorted(approved):
        if not name.endswith(".md"):
            continue
        path = safe_path(root, root / name)
        for target in markdown_targets(path.read_text()):
            try:
                counts[classify_link(root, name, target, approved)] += 1
            except ValueError as error:
                raise ValueError(f"{name}: {error}") from error
    return {"status": "PASS", "counts": counts, "generated_command": REPORT_COMMAND}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "EXPORT_MANIFEST.json").read_text())
    approved = {row["destination_path"] for row in manifest["files"]}
    # Reviewed guide added after the immutable initial export.
    approved.update({"EXPORT_MANIFEST.json", "EXPORT_MANIFEST.sha256",
                     "docs/cloudflare-pages-deployment.md", "docs/final-production-readiness.md"})
    print(json.dumps(audit(root, approved), indent=2))


if __name__ == "__main__":
    main()
