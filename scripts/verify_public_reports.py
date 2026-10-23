"""Verify exact public inputs, output hashes and independent offline determinism."""
import hashlib
import json
from pathlib import Path
import sys

def verify(first: Path, second: Path):
    manifests = []
    for root in (first, second):
        m = json.loads((root / "manifest.json").read_text())
        assert m["status"] == "PASS" and m["input_evidence_files_count"] == 40
        assert len(m["output_artifacts"]) == 12
        for relative, meta in m["output_artifacts"].items():
            assert not Path(relative).is_absolute() and ".." not in Path(relative).parts
            target = root / relative
            assert target.is_file() and not target.is_symlink()
            raw = target.read_bytes()
            assert len(raw) == meta["bytes"]
            assert hashlib.sha256(raw).hexdigest() == meta["sha256"]
        project = Path(__file__).resolve().parents[1]
        for relative, digest in m["input_evidence_sha256"].items():
            assert relative.startswith("docs/evidence/") and ".." not in Path(relative).parts
            assert hashlib.sha256((project / relative).read_bytes()).hexdigest() == digest
        manifests.append(m)
    assert manifests[0] == manifests[1]
    for relative in manifests[0]["output_artifacts"]:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
    print("PASS: 40 public input hashes, 12 output digests, byte-identical deterministic bundles.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_public_reports.py FIRST SECOND")
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
