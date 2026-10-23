"""Public derivatives retain a complete, verifiable provenance mapping."""
import hashlib
import json
from pathlib import Path
from oracle_spa.data_generator import ROOT

def test_all_public_evidence_hashes_match_the_declared_derivatives():
    provenance = json.loads((ROOT / "docs/evidence/PROVENANCE.json").read_text())
    assert provenance["originals_retained_privately"] is True
    assert len(provenance["files"]) == 61
    paths = set()
    for record in provenance["files"]:
        path = record["path"]
        assert path.startswith("docs/evidence/") and ".." not in Path(path).parts
        target = ROOT / path
        assert target.is_file() and not target.is_symlink()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == record["public_sha256"]
        assert len(record["original_sha256"]) == 64
        if record["status"] == "original bytes":
            assert record["original_sha256"] == record["public_sha256"]
        else:
            assert record["status"] == "sanitized derivative"
            assert record["original_sha256"] != record["public_sha256"]
        assert path not in paths
        paths.add(path)

def test_public_reference_fixture_manifest_is_explicit_and_tamper_evident():
    base = ROOT / "docs/evidence/phase4/group-b-create-stat-table"
    manifest = json.loads((base / "manifest.json").read_text())
    assert manifest["public_derivative"] is True
    assert len(manifest["sha256"]) == 7
    for path, digest in manifest["sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest


def test_same_cohort_comparison_digest_binds_public_derivative_bytes():
    from oracle_spa.analysis import compare_statistics_runs
    from oracle_spa.statistics_backup import digest
    base = ROOT / "docs/evidence/phase4/group-b-histogram-final"
    first = json.loads((base / "runs/82b1df0bc6bb40738719801106790567/run.json").read_text())
    second = json.loads((base / "runs/232234a4a9ea4f56880afbb6749b585e/run.json").read_text())
    recorded = json.loads((base / "cohort-comparisons.json").read_text())
    for variant, cohort in [("baseline", "PAID_baseline"), ("rare", "CANCELLED_rare")]:
        actual = compare_statistics_runs(first, second, variant, approval="E04/ORDERS/" + digest([first, second]))
        assert actual == recorded["cohorts"][cohort]["comparison"]
