"""Phase 5 Stage A quality, numerical hardening, report schema, and offline evidence reproducibility tests."""

import json
import math
from pathlib import Path
import pytest

from oracle_spa.analysis import (
    compare_runs,
    compare_statistics_runs,
    comparison,
    percentile,
    summarize,
)
from oracle_spa.data_generator import ROOT
from oracle_spa.db import DiagnosticError
from oracle_spa.report import render_report
from oracle_spa.statistics_backup import digest


def test_percentile_rejects_boolean_and_nonfinite_inputs():
    with pytest.raises(ValueError, match="finite numeric"):
        percentile([1.0, 2.0, 3.0], True)
    with pytest.raises(ValueError, match="finite numeric"):
        percentile([1.0, 2.0, 3.0], False)
    with pytest.raises(ValueError, match="finite numeric"):
        percentile([1.0, 2.0, 3.0], math.nan)
    with pytest.raises(ValueError, match="finite numeric"):
        percentile([1.0, True, 3.0], 0.5)
    with pytest.raises(ValueError, match="finite numeric"):
        percentile([1.0, math.nan, 3.0], 0.5)
    with pytest.raises(ValueError, match="finite numeric"):
        percentile([1.0, math.inf, 3.0], 0.5)


def test_summarize_treats_boolean_elapsed_ms_as_invalid_sample():
    samples = [
        {"warmup": True, "status": "PASS", "elapsed_ms": True},
        {"warmup": False, "status": "PASS", "elapsed_ms": True},
        {"warmup": False, "status": "PASS", "elapsed_ms": False},
        {"warmup": False, "status": "PASS", "elapsed_ms": 2.5},
        {"warmup": False, "status": "PASS", "elapsed_ms": 3.5},
    ]
    summary = summarize(samples)
    assert summary["n"] == 2
    assert summary["failures"] == 2
    assert summary["median"] == 3.0


def test_render_report_rejects_corrupted_nan_and_incomplete_json(tmp_path):
    run_id = "f" * 32
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    source = run_dir / "run.json"

    # 1. Malformed JSON syntax
    source.write_text("{corrupted json", encoding="utf-8")
    with pytest.raises(DiagnosticError, match="Corrupted or invalid JSON"):
        render_report(run_id, tmp_path)

    # 2. Non-standard NaN constant in JSON
    source.write_text('{"run_id": "' + run_id + '", "value": NaN}', encoding="utf-8")
    with pytest.raises(DiagnosticError, match="NaN or Infinity"):
        render_report(run_id, tmp_path)

    # 3. Missing required top-level schema fields
    source.write_text(json.dumps({"run_id": run_id, "status": "PASS"}), encoding="utf-8")
    with pytest.raises(DiagnosticError, match="missing required schema fields"):
        render_report(run_id, tmp_path)

    # 4. Invalid sample structure
    bad_payload = {
        "run_id": run_id,
        "status": "PASS",
        "samples": [{"variant": "baseline"}],
        "cases": {"baseline": {}},
        "equivalent": True,
        "experiment_id": "E01",
        "scenario": "baseline",
        "metric": "client_execute_plus_full_fetch_ms",
        "environment_notes": [],
    }
    source.write_text(json.dumps(bad_payload), encoding="utf-8")
    with pytest.raises(DiagnosticError, match="invalid collection or sample structure"):
        render_report(run_id, tmp_path)


def test_offline_reproducibility_of_committed_phase4_evidence():
    # 1. Stage A baseline runs (5 runs, 105 samples: 35 warmups + 70 measured)
    stage_a_dir = ROOT / "docs" / "evidence" / "phase4" / "runs"
    stage_a_runs = sorted(stage_a_dir.glob("*/run.json"))
    assert len(stage_a_runs) == 5
    total_samples = 0
    total_warmups = 0
    total_measured = 0
    for run_file in stage_a_runs:
        run = json.loads(run_file.read_text(encoding="utf-8"))
        saved_summary = json.loads((run_file.parent / "summary.json").read_text(encoding="utf-8"))
        total_samples += len(run["samples"])
        for variant in run["cases"]:
            recomputed = summarize([s for s in run["samples"] if s["variant"] == variant])
            assert recomputed == saved_summary["summaries"][variant]
            total_warmups += recomputed["warmups"]
            total_measured += recomputed["n"]
    assert (total_samples, total_warmups, total_measured) == (105, 35, 70)

    # 2. Group A experimental index blocks (10 runs, 180 samples: 60 warmups + 120 measured)
    group_a_summary = json.loads(
        (ROOT / "docs" / "evidence" / "phase4" / "group-a" / "summary.json").read_text(encoding="utf-8")
    )
    assert (
        group_a_summary["samples"],
        group_a_summary["warmups"],
        group_a_summary["measured"],
    ) == (180, 60, 120)
    for entry in group_a_summary["comparisons"]:
        expected_comp = entry["comparison"]
        base_run = json.loads(
            (ROOT / "docs" / "evidence" / "phase4" / "group-a" / "runs" / expected_comp["baseline_run_id"] / "run.json").read_text(encoding="utf-8")
        )
        alt_run = json.loads(
            (ROOT / "docs" / "evidence" / "phase4" / "group-a" / "runs" / expected_comp["alternative_run_id"] / "run.json").read_text(encoding="utf-8")
        )
        recomputed_comp = compare_runs(base_run, alt_run, variant=entry["variant"])
        assert recomputed_comp == expected_comp

    # 3. Group B final E04 histogram runs and same-cohort comparisons
    group_b_dir = ROOT / "docs" / "evidence" / "phase4" / "group-b-histogram-final"
    run_a = json.loads((group_b_dir / "runs" / "82b1df0bc6bb40738719801106790567" / "run.json").read_text(encoding="utf-8"))
    run_b = json.loads((group_b_dir / "runs" / "232234a4a9ea4f56880afbb6749b585e" / "run.json").read_text(encoding="utf-8"))
    saved_cohorts = json.loads((group_b_dir / "cohort-comparisons.json").read_text(encoding="utf-8"))
    approval = "E04/ORDERS/" + digest([run_a, run_b])
    paid_comp = compare_statistics_runs(run_a, run_b, "baseline", approval=approval)
    cancelled_comp = compare_statistics_runs(run_a, run_b, "rare", approval=approval)
    assert paid_comp == saved_cohorts["cohorts"]["PAID_baseline"]["comparison"]
    assert cancelled_comp == saved_cohorts["cohorts"]["CANCELLED_rare"]["comparison"]
    assert paid_comp["status"] == "DESCRIPTIVE ONLY"
    assert cancelled_comp["status"] == "DESCRIPTIVE ONLY"


def test_phase5_bundle_generation_csv_charts_manifest_and_oracle_independence(tmp_path, monkeypatch):
    import csv
    import oracledb
    from oracle_spa.cli import main as cli_main
    from oracle_spa.phase5_report import _verify_no_secret_patterns

    # Block any Oracle connection attempt to prove strict offline independence
    def _forbid_connect(*_args, **_kwargs):
        raise AssertionError("Offline report-all must never connect to Oracle.")

    monkeypatch.setattr(oracledb, "connect", _forbid_connect)

    out_dir = tmp_path / "phase5_out"
    exit_code = cli_main(["report-all", "--output", str(out_dir)])
    assert exit_code == 0

    # Verify all required artifacts exist and are UTF-8 / non-empty
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    report_md = (out_dir / "report.md").read_text(encoding="utf-8")
    assert summary["status"] == "PASS"
    assert summary["recalculated_matches_historical"] is True
    assert summary["stage_a"]["not_benchmarked_in_phase4"] == ["Q03", "Q04", "Q05"]
    assert summary["group_b_e04"]["status_distribution"] == {
        "PAID": 5876,
        "SHIPPED": 2523,
        "NEW": 1060,
        "CANCELLED": 541,
    }
    assert manifest["status"] == "PASS"
    assert manifest["generation_parameters"]["oracle_connection_used"] is False
    assert manifest["input_evidence_files_count"] == 40
    assert "DESCRIPTIVE ONLY" in report_md
    assert "2,500" in report_md or "2500" in report_md

    # Verify measurements.csv and comparisons.csv structure and preservation of warmups/outliers
    with (out_dir / "measurements.csv").open("r", encoding="utf-8", newline="") as f:
        meas_rows = list(csv.DictReader(f))
    assert len(meas_rows) == 23
    assert all(r["n"] == "10" and r["warmups"] == "5" and r["failures"] == "0" for r in meas_rows)

    with (out_dir / "comparisons.csv").open("r", encoding="utf-8", newline="") as f:
        comp_rows = list(csv.DictReader(f))
    assert len(comp_rows) == 10
    statuses = {r["comparison_label"]: r["status"] for r in comp_rows}
    assert statuses["E04 (Q06): baseline vs rare"] == "NOT COMPARABLE"
    assert statuses["E03 (Q07) date-index [range]"] == "DESCRIPTIVE ONLY"

    # Verify SVG and PNG charts
    expected_stems = [
        "stage_a_baselines",
        "group_a_index_comparisons",
        "group_a_storage_vs_latency",
        "group_b_e04_status_and_cohorts",
    ]
    for stem in expected_stems:
        svg_file = out_dir / "charts" / f"{stem}.svg"
        png_file = out_dir / "charts" / f"{stem}.png"
        svg_text = svg_file.read_text(encoding="utf-8")
        png_bytes = png_file.read_bytes()
        assert "<svg" in svg_text
        assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(png_bytes) > 10_000

    stage_a_svg = (out_dir / "charts" / "stage_a_baselines.svg").read_text(encoding="utf-8")
    for q_label in ("Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08"):
        assert q_label in stage_a_svg

    # Verify secret scanner rejects leaked password marker
    (out_dir / "leaked.md").write_text("ORACLE_PASSWORD=leaked_value\n", encoding="utf-8")
    with pytest.raises(DiagnosticError, match="Sensitive configuration token"):
        _verify_no_secret_patterns(out_dir)


def test_phase5_output_directory_guards_against_unsafe_paths_and_symlinks(tmp_path):
    from oracle_spa.phase5_report import validate_output_directory

    for forbidden in (
        ROOT,
        ROOT / "docs",
        ROOT / "docs" / "evidence" / "phase4",
        ROOT / "src" / "oracle_spa",
        ROOT / "results" / "phase4",
        ROOT / "sql",
        ROOT / "tests",
    ):
        with pytest.raises(DiagnosticError):
            validate_output_directory(forbidden)

    real_dir = tmp_path / "real"
    real_dir.mkdir()
    symlink_dir = tmp_path / "symlink_out"
    symlink_dir.symlink_to(real_dir)
    with pytest.raises(DiagnosticError, match="Symbolic links are forbidden"):
        validate_output_directory(symlink_dir)


def test_phase5_loader_rejects_missing_samples_and_summary_divergence(tmp_path):
    from oracle_spa.phase5_report import _load_and_verify_run

    src_run_dir = ROOT / "docs" / "evidence" / "phase4" / "runs" / "c4cd44eae137426cbdfec81f66cab75a"
    run_id = "c4cd44eae137426cbdfec81f66cab75a"
    work_dir = tmp_path / run_id
    work_dir.mkdir()
    run_data = json.loads((src_run_dir / "run.json").read_text(encoding="utf-8"))
    sum_data = json.loads((src_run_dir / "summary.json").read_text(encoding="utf-8"))

    # 1. Missing sample in run.json
    truncated = dict(run_data, samples=run_data["samples"][:-1])
    (work_dir / "run.json").write_text(json.dumps(truncated), encoding="utf-8")
    (work_dir / "summary.json").write_text(json.dumps(sum_data), encoding="utf-8")
    with pytest.raises(DiagnosticError, match="missing or unexpected sample count"):
        _load_and_verify_run(work_dir, run_id, {})

    # 2. Tampered historical summary.json diverges from recalculated raw samples
    (work_dir / "run.json").write_text(json.dumps(run_data), encoding="utf-8")
    tampered_sum = json.loads(json.dumps(sum_data))
    tampered_sum["summaries"]["baseline"]["median"] = 999.0
    (work_dir / "summary.json").write_text(json.dumps(tampered_sum), encoding="utf-8")
    with pytest.raises(DiagnosticError, match="diverges from historical summary.json"):
        _load_and_verify_run(work_dir, run_id, {})


def test_phase5_stage_c_lockfile_workflow_and_dev_guide_hygiene():
    import re

    lock_lines = [
        line.strip()
        for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(lock_lines) == 22
    for line in lock_lines:
        assert not line.startswith("-e ")
        assert "git+" not in line and "file:" not in line and "/" not in line
        assert re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.-]+", line), f"Unpinned line: {line}"

    ci_path = ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.is_file()
    ci_text = ci_path.read_text(encoding="utf-8")
    assert "contents: read" in ci_text
    assert "workflow_dispatch:" in ci_text
    assert "ubuntu-latest" in ci_text
    assert "python -m oracle_spa.cli report-all --output results/phase5" in ci_text
    actions = re.findall(r"uses:\s*([^@\s]+)@([^\s]+)", ci_text)
    assert len(actions) == 5
    assert {name for name, _ in actions} == {
        "actions/checkout", "actions/setup-python", "actions/setup-node", "actions/upload-artifact"
    }
    assert all(re.fullmatch(r"[0-9a-f]{40}", revision) for _, revision in actions)
    assert "scripts/check_documentation_links.py" in ci_text
    assert "secrets." not in ci_text
    assert "container-registry.oracle.com" not in ci_text

    dev_guide = (ROOT / "docs" / "development.md").read_text(encoding="utf-8")
    assert "Workflow A" in dev_guide and "Workflow B" in dev_guide
    assert "python -m oracle_spa.cli report-all --output results/phase5" in dev_guide


def test_phase5_stage_d_portfolio_docs_links_and_consistency():
    import re

    required_docs = (
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "docs" / "demo.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "portfolio-summary.md",
        ROOT / "docs" / "phase5-final-audit.md",
        ROOT / "docs" / "acceptance.md",
        ROOT / "docs" / "engineering-log.md",
        ROOT / "docs" / "findings.md",
        ROOT / "docs" / "development.md",
        ROOT / "docs" / "evidence" / "phase5" / "stage-d" / "summary.json",
    )
    for doc in required_docs:
        assert doc.is_file(), f"Missing Stage D file: {doc}"

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Phase 5 remains locked" not in readme_text
    assert "Phase 5 is not yet authorized" not in readme_text
    assert "docs/demo.md" in readme_text
    assert "docs/architecture.md" in readme_text
    assert "docs/portfolio-summary.md" in readme_text
    assert "docs/phase5-final-audit.md" in readme_text

    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Phase 5 remains locked" not in agents_text
    assert "read-only" in agents_text and "approval" in agents_text
    assert not (ROOT / "recursos").exists()

    portfolio_text = (ROOT / "docs" / "portfolio-summary.md").read_text(encoding="utf-8")
    assert "Public evidence summary" in portfolio_text
    assert "English Version" in portfolio_text and "Versión en Español" in portfolio_text

    stage_d_summary = json.loads(
        (ROOT / "docs" / "evidence" / "phase5" / "stage-d" / "summary.json").read_text(encoding="utf-8")
    )
    assert stage_d_summary["status"] == "PASS"
    assert stage_d_summary["offline_demonstration_flow_a"]["unit_tests_passed"] == 180
    assert stage_d_summary["constraints_respected"]["no_ddl_dml_grant_or_dbms_stats_executed"] is True

    # Audit relative Markdown links across all root and docs/ Markdown files
    # Distinguishes versioned source files (which must exist) from offline-generated
    # Phase 5 artifacts under results/phase5/ (which are validated against allowlisted
    # artifact names prior to generation, and checked on disk once generated).
    from oracle_spa.phase5_report import audit_markdown_links

    stats = audit_markdown_links(ROOT, require_generated_exist=False)
    assert stats["files_audited"] >= 10
    assert stats["total_links"] > 50
    assert stats["versioned_links"] > 40
    # Public docs must work before ignored outputs have been generated.
    assert stats["generated_links"] == 0


def test_phase5_stage_d_generated_links_exist_after_generation(tmp_path):
    """Verify the exact documented output contract and digests after generation."""
    from oracle_spa.phase5_report import audit_markdown_links, render_phase5_bundle

    out_dir = tmp_path / "phase5_generated"
    res = render_phase5_bundle(output_dir=out_dir)
    assert res["status"] == "PASS"

    # Documentation stays valid; validate every approved output independently of live links.
    stats = audit_markdown_links(ROOT, require_generated_exist=True, results_dir=out_dir)
    assert stats["generated_links"] == 0
    import hashlib
    from scripts.check_documentation_links import GENERATED_OUTPUTS
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert set(manifest["output_artifacts"]) | {"manifest.json"} == GENERATED_OUTPUTS
    for name in GENERATED_OUTPUTS:
        assert (out_dir / name).is_file() and not (out_dir / name).is_symlink()
    for name, metadata in manifest["output_artifacts"].items():
        assert hashlib.sha256((out_dir / name).read_bytes()).hexdigest() == metadata["sha256"]


def test_phase5_stage_d_ci_failure_clean_env_regression(tmp_path):
    """Regression test for the GitHub Actions failure in a clean checkout.

    Reproduces the exact failure mode where tests run in a clean environment
    before results/phase5 has been generated. Confirms that:
    1. A naive existence check fails on ungenerated results/phase5/manifest.json.
    2. The corrected audit_markdown_links passes for valid documentation links.
    3. Invalid or unauthorized links (outside allowlist, traversal, or nonexistent versioned) are rejected.
    """
    from oracle_spa.db import DiagnosticError
    from oracle_spa.phase5_report import audit_markdown_links

    # 1. Simulate a clean environment where results/phase5 does not exist
    clean_root = tmp_path / "clean_repo"
    clean_root.mkdir()
    docs_dir = clean_root / "docs"
    docs_dir.mkdir()

    # Replicate documentation linking to generated artifacts and versioned files
    (clean_root / "README.md").write_text("# Test\nLink: [Doc](docs/sample.md)\n", encoding="utf-8")
    (docs_dir / "sample.md").write_text("# Sample\nVersioned link: [README](../README.md)\n", encoding="utf-8")
    (docs_dir / "findings.md").write_text(
        "# Findings\nLink to manifest: [manifest.json](../results/phase5/manifest.json)\n",
        encoding="utf-8",
    )

    # 1a. Naive check reproducing the exact CI failure:
    # 'AssertionError: Broken link in findings.md: ../results/phase5/manifest.json'
    manifest_target = (clean_root / "results" / "phase5" / "manifest.json")
    assert not manifest_target.exists(), "Clean environment must not have pre-existing results/phase5"

    naive_failed = False
    try:
        # The naive logic that failed in a clean checkout:
        rel = "../results/phase5/manifest.json"
        resolved = (docs_dir / rel).resolve()
        assert resolved.exists(), f"Broken link in findings.md: {rel} -> {resolved}"
    except AssertionError as exc:
        assert "Broken link in findings.md: ../results/phase5/manifest.json" in str(exc)
        naive_failed = True
    assert naive_failed, "Naive check must reproduce the exact CI failure in a clean checkout"

    # 2. Corrected audit_markdown_links handles the clean environment correctly
    stats = audit_markdown_links(root=clean_root, require_generated_exist=False)
    assert stats["generated_links"] == 1
    assert stats["versioned_links"] == 2

    # 3. But rejects invalid or un-allowlisted paths even in clean environment
    (docs_dir / "bad_artifact.md").write_text(
        "[Bad](../results/phase5/unauthorized_output.json)\n", encoding="utf-8"
    )
    with pytest.raises(DiagnosticError, match="Unrecognized generated artifact link"):
        audit_markdown_links(root=clean_root, require_generated_exist=False)
    (docs_dir / "bad_artifact.md").unlink()

    # 4. Rejects links to other subdirectories under results/
    (docs_dir / "bad_results.md").write_text(
        "[Bad](../results/other/file.txt)\n", encoding="utf-8"
    )
    with pytest.raises(DiagnosticError, match="Broken versioned file link"):
        audit_markdown_links(root=clean_root, require_generated_exist=False)
    (docs_dir / "bad_results.md").unlink()

    # 5. Rejects broken versioned links
    (docs_dir / "bad_versioned.md").write_text(
        "[Bad](missing_file.md)\n", encoding="utf-8"
    )
    with pytest.raises(DiagnosticError, match="Broken versioned file link"):
        audit_markdown_links(root=clean_root, require_generated_exist=False)
    (docs_dir / "bad_versioned.md").unlink()

    # 6. Rejects path traversal outside repository
    (docs_dir / "traversal.md").write_text(
        "[Traversal](../../../etc/passwd)\n", encoding="utf-8"
    )
    with pytest.raises(DiagnosticError, match="Path traversal outside repository forbidden"):
        audit_markdown_links(root=clean_root, require_generated_exist=False)
