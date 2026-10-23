"""Phase 5 Stage B offline reproducible report, CSV, and scientific chart generator."""

import csv
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import sys

try:
    PACKAGE_VERSION = version("oracle-spa")
except PackageNotFoundError:
    PACKAGE_VERSION = "0.1.0"
from oracle_spa.analysis import (
    compare_runs,
    compare_statistics_runs,
    comparison,
    percentile,
    summarize,
)
from oracle_spa.data_generator import ROOT
from oracle_spa.db import DiagnosticError
from oracle_spa.queries import CATALOG
from oracle_spa.report import _load_run_payload, _reject_nonfinite_constant
from oracle_spa.statistics_backup import digest

EVIDENCE_PHASE4 = ROOT / "docs" / "evidence" / "phase4"
RESULTS_PHASE5 = ROOT / "results" / "phase5"

EXPECTED_STATUS_COUNTS = {
    "PAID": 5876,
    "SHIPPED": 2523,
    "NEW": 1060,
    "CANCELLED": 541,
}

EXPECTED_STAGE_A_RUNS = (
    ("E01", "Q01", "c4cd44eae137426cbdfec81f66cab75a"),
    ("E02", "Q02", "9dffbb99f3fe48e08ec80e18a9aa536d"),
    ("E03", "Q07", "b158e3a5c72249f9bf8a362f8a75eeea"),
    ("E04", "Q06", "a64fbcf36ff14a758698e301435ff310"),
    ("E05", "Q08", "7efe329021d4435688bf2ca9f755cca7"),
)

EXPECTED_GROUP_B_RUNS = {
    "scenario_a": "82b1df0bc6bb40738719801106790567",
    "scenario_b": "232234a4a9ea4f56880afbb6749b585e",
}

PHASE5_OUTPUT_ARTIFACT_NAMES = frozenset({
    "summary.json",
    "measurements.csv",
    "comparisons.csv",
    "report.md",
    "manifest.json",
    "charts",
    "charts/stage_a_baselines.svg",
    "charts/stage_a_baselines.png",
    "charts/group_a_index_comparisons.svg",
    "charts/group_a_index_comparisons.png",
    "charts/group_a_storage_vs_latency.svg",
    "charts/group_a_storage_vs_latency.png",
    "charts/group_b_e04_status_and_cohorts.svg",
    "charts/group_b_e04_status_and_cohorts.png",
})

METHODOLOGICAL_WARNINGS = [
    "All latency metrics represent client-side execute + full fetch elapsed time (time.perf_counter_ns in ms) over local loopback TCP, not server-only CPU time.",
    "Warmup repetitions (5 per variant) are retained in raw run.json evidence and excluded from descriptive summaries; all 10 measured repetitions per variant are retained with zero outlier removal.",
    "Percentiles (Q25, Q75, IQR = Q75 - Q25, and p95) use linear interpolation at rank (n - 1) * p.",
    "Sequential experiment blocks operate under warm-cache tendency without buffer-cache flushing or per-repetition DDL alternation; comparisons are labeled DESCRIPTIVE ONLY rather than causal proof.",
    "Stage A benchmarked the five Phase 4 baseline experiments E01-E05 (queries Q01, Q02, Q07, Q06, Q08). Phase 3 catalog queries Q03, Q04, and Q05 were verified functionally and via estimated plans in Phase 3 without timed Phase 4 benchmark runs; no latency values are fabricated for Q03-Q05.",
    "In E04 (Q06), PAID (5,876 rows) and CANCELLED (541 rows) return different result sets and row volumes; cross-cohort comparisons within a run are marked NOT COMPARABLE, whereas same-cohort comparisons across statistics states (PAID A vs B, CANCELLED A vs B) are valid descriptive comparisons.",
    "In E04 Scenario B, EXPLAIN PLAN reported estimated_rows = 2,500 for both PAID and CANCELLED despite an active 4-bucket FREQUENCY histogram on ORDERS.STATUS because EXPLAIN PLAN does not perform bind peeking on :status (falling back to 1 / NUM_DISTINCT = 0.25).",
    "Group C privileged fixed-view cursor metrics (V_$SQL, V_$SQL_PLAN, V_$SQL_PLAN_STATISTICS_ALL via DBMS_XPLAN.DISPLAY_CURSOR: A-Rows, Starts, Buffers) are formally DEFERRED / NOT VERIFIED under least-privilege account ORACLE_SPA (ORA-00942).",
]


def _check_no_symlinks_in_chain(path: Path, stop_at: Path | None = None) -> None:
    current = Path(path)
    visited = set()
    while current not in visited:
        visited.add(current)
        if current.is_symlink():
            raise DiagnosticError(f"Symbolic links are forbidden in report paths: {current}")
        if stop_at is not None and current == stop_at:
            break
        if current.parent == current:
            break
        current = current.parent


def validate_output_directory(output_dir: str | Path, evidence_root: str | Path = EVIDENCE_PHASE4) -> Path:
    """Validate that output_dir is safe, free of symlinks, and never overlaps historical evidence or source trees."""
    if not isinstance(output_dir, (str, Path)) or not str(output_dir).strip():
        raise DiagnosticError("Output directory must be a non-empty path.")
    raw_out = Path(output_dir)
    if not raw_out.is_absolute():
        raw_out = ROOT / raw_out
    _check_no_symlinks_in_chain(raw_out)
    resolved_out = raw_out.resolve()

    raw_ev = Path(evidence_root)
    if not raw_ev.is_absolute():
        raw_ev = ROOT / raw_ev
    _check_no_symlinks_in_chain(raw_ev)
    resolved_ev = raw_ev.resolve()

    protected_roots = [
        resolved_ev,
        (ROOT / "docs").resolve(),
        (ROOT / "src").resolve(),
        (ROOT / "sql").resolve(),
        (ROOT / "tests").resolve(),
        (ROOT / "scripts").resolve(),
        (ROOT / "recursos").resolve(),
        (ROOT / ".git").resolve(),
        (ROOT / ".venv").resolve(),
        (ROOT / "results" / "phase4").resolve(),
    ]
    if resolved_out == ROOT.resolve() or ROOT.resolve().is_relative_to(resolved_out):
        raise DiagnosticError("Output directory must not be the repository root or its parent.")
    for protected in protected_roots:
        if (
            resolved_out == protected
            or resolved_out.is_relative_to(protected)
            or protected.is_relative_to(resolved_out)
        ):
            raise DiagnosticError(
                "Output directory overlaps a protected evidence, source, or Phase 4 results path."
            )

    if raw_out.exists():
        if not raw_out.is_dir():
            raise DiagnosticError("Output path exists and is not a directory.")
        for child in raw_out.rglob("*"):
            if child.is_symlink():
                raise DiagnosticError("Symbolic links are forbidden inside the output directory.")
    return raw_out


def _read_verified_json(path: Path, input_hashes: dict[str, str], required_keys: set[str] | None = None):
    _check_no_symlinks_in_chain(path)
    if not path.is_file() or path.stat().st_size > 30_000_000:
        raise DiagnosticError(f"Missing, unsafe, or oversized evidence file: {path.name}")
    try:
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
        payload = json.loads(text, parse_constant=_reject_nonfinite_constant)
    except DiagnosticError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise DiagnosticError(f"Corrupted or invalid JSON in evidence file: {path.name}") from None
    if required_keys is not None:
        if not isinstance(payload, dict) or not required_keys <= payload.keys():
            raise DiagnosticError(f"Evidence file {path.name} is missing required schema fields.")
    try:
        rel_key = str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        rel_key = str(path)
    input_hashes[rel_key] = sha256(raw_bytes).hexdigest()
    return payload


def _load_and_verify_run(run_dir: Path, expected_run_id: str, input_hashes: dict[str, str]) -> tuple[dict, dict, dict]:
    _check_no_symlinks_in_chain(run_dir)
    run_file = run_dir / "run.json"
    summary_file = run_dir / "summary.json"
    _read_verified_json(run_file, input_hashes)
    run = _load_run_payload(run_file, expected_run_id)
    saved_summary = _read_verified_json(
        summary_file,
        input_hashes,
        required_keys={"run_id", "status", "summaries", "comparisons"},
    )
    if saved_summary["run_id"] != expected_run_id:
        raise DiagnosticError("Historical summary.json run_id does not match directory.")
    if run["status"] != "PASS" or not run.get("controls_unchanged", False):
        raise DiagnosticError(f"Run {expected_run_id} did not pass with unchanged controls.")
    context = run.get("context", {})
    if context.get("profile") != "small" or context.get("seed") != 20261016:
        raise DiagnosticError(f"Run {expected_run_id} does not match profile small / seed 20261016.")
    warmups_expected = run.get("warmups")
    repeats_expected = run.get("repeats")
    if not isinstance(warmups_expected, int) or not isinstance(repeats_expected, int) or repeats_expected < 5:
        raise DiagnosticError(f"Run {expected_run_id} has invalid warmups/repeats configuration.")
    if not run["cases"]:
        raise DiagnosticError(f"Run {expected_run_id} contains no variant cases.")

    expected_total_samples = len(run["cases"]) * (warmups_expected + repeats_expected)
    if len(run["samples"]) != expected_total_samples:
        raise DiagnosticError(
            f"Run {expected_run_id} has missing or unexpected sample count ({len(run['samples'])} != {expected_total_samples})."
        )

    recomputed_summaries = {}
    quartiles = {}
    for variant in run["cases"]:
        v_samples = [s for s in run["samples"] if s["variant"] == variant]
        if len(v_samples) != warmups_expected + repeats_expected:
            raise DiagnosticError(f"Run {expected_run_id} variant {variant} has incomplete samples.")
        rec = summarize(v_samples)
        if rec["warmups"] != warmups_expected or rec["n"] != repeats_expected or rec["failures"] != 0 or rec["warmup_failures"] != 0:
            raise DiagnosticError(f"Run {expected_run_id} variant {variant} contains sample failures or missing measurements.")
        if saved_summary["summaries"].get(variant) != rec:
            raise DiagnosticError(f"Recalculated summary for {expected_run_id}/{variant} diverges from historical summary.json.")
        measured_vals = [s["elapsed_ms"] for s in v_samples if not s["warmup"] and s["status"] == "PASS"]
        recomputed_summaries[variant] = rec
        quartiles[variant] = {
            "q25": percentile(measured_vals, 0.25),
            "q75": percentile(measured_vals, 0.75),
        }

    variants = list(recomputed_summaries)
    recomputed_comparisons = []
    for v in variants[1:]:
        recomputed_comparisons.append(
            {
                "baseline": variants[0],
                "alternative": v,
                **comparison(
                    recomputed_summaries[variants[0]],
                    recomputed_summaries[v],
                    comparable=run["equivalent"],
                    valid=run["status"] == "PASS" and run.get("controls_unchanged", False),
                ),
            }
        )
    if recomputed_comparisons != saved_summary["comparisons"]:
        raise DiagnosticError(f"Recalculated in-run comparisons for {expected_run_id} diverge from historical summary.json.")

    return run, recomputed_summaries, quartiles


def _extract_access_operator(operators: list[dict]) -> dict:
    if not isinstance(operators, list) or not operators:
        return {
            "access_operator": None,
            "object": None,
            "estimated_rows": None,
            "optimizer_cost": None,
        }
    root = operators[0]
    leaf_access = None
    for op in operators:
        operation = op.get("operation") or ""
        if "INDEX" in operation or "TABLE ACCESS" in operation:
            leaf_access = op
            if "INDEX" in operation:
                break
    target = leaf_access or root
    op_str = target.get("operation") or ""
    if target.get("options"):
        op_str = f"{op_str} {target['options']}"
    if target.get("object"):
        op_str = f"{op_str} ({target['object']})"
    return {
        "access_operator": op_str,
        "object": target.get("object"),
        "estimated_rows": root.get("estimated_rows"),
        "optimizer_cost": root.get("optimizer_cost"),
    }


def _build_measurement_row(stage_group: str, run: dict, variant: str, stats: dict, quartiles: dict) -> dict:
    case = run["cases"][variant]
    validation = case["validation"]
    plan = case["plan"]
    op_info = _extract_access_operator(plan.get("operators", []))
    return {
        "stage_group": stage_group,
        "experiment_id": run["experiment_id"],
        "experiment": run["experiment"],
        "query_id": run["query_id"],
        "scenario": run["scenario"],
        "variant": variant,
        "run_id": run["run_id"],
        "returned_rows": validation["result"]["rows"],
        "unit": stats["unit"],
        "n": stats["n"],
        "warmups": stats["warmups"],
        "failures": stats["failures"],
        "warmup_failures": stats["warmup_failures"],
        "median_ms": stats["median"],
        "mean_ms": stats["mean"],
        "q25_ms": quartiles["q25"],
        "q75_ms": quartiles["q75"],
        "iqr_ms": stats["iqr"],
        "p95_ms": stats["p95"],
        "min_ms": stats["min"],
        "max_ms": stats["max"],
        "stddev_ms": stats["stddev"],
        "plan_hash": plan.get("plan_hash"),
        "plan_capture_type": plan.get("type"),
        "access_operator": op_info["access_operator"],
        "estimated_rows": op_info["estimated_rows"],
        "optimizer_cost": op_info["optimizer_cost"],
        "result_sha256": validation["result"]["result_sha256"],
        "sql_sha256": validation["sql_sha256"],
    }


def collect_and_verify_phase4_evidence(evidence_root: str | Path = EVIDENCE_PHASE4) -> dict:
    """Load, validate, and recalculate all Stage A, Group A, and Group B Phase 4 evidence offline."""
    ev_root = Path(evidence_root)
    if not ev_root.is_absolute():
        ev_root = ROOT / ev_root
    _check_no_symlinks_in_chain(ev_root)
    if not ev_root.is_dir():
        raise DiagnosticError("Phase 4 evidence root directory does not exist.")

    input_hashes: dict[str, str] = {}
    measurements: list[dict] = []
    comparisons_table: list[dict] = []

    # 1. Stage A baseline runs (5 runs, 7 variant rows, 105 samples)
    stage_a_records = []
    stage_a_samples_total = 0
    stage_a_warmups_total = 0
    stage_a_measured_total = 0
    for exp_id, query_id, run_id in EXPECTED_STAGE_A_RUNS:
        run_dir = ev_root / "runs" / run_id
        run, summaries, quartiles = _load_and_verify_run(run_dir, run_id, input_hashes)
        if run["experiment_id"] != exp_id or run["query_id"] != query_id or run["scenario"] != "baseline":
            raise DiagnosticError(f"Stage A run {run_id} metadata mismatch.")
        stage_a_samples_total += len(run["samples"])
        for variant, stats in summaries.items():
            stage_a_warmups_total += stats["warmups"]
            stage_a_measured_total += stats["n"]
            row = _build_measurement_row("Stage A", run, variant, stats, quartiles[variant])
            measurements.append(row)
            stage_a_records.append(row)

        variants = list(summaries)
        for alt_v in variants[1:]:
            base_v = variants[0]
            comp = comparison(
                summaries[base_v],
                summaries[alt_v],
                comparable=run["equivalent"],
                valid=run["status"] == "PASS" and run.get("controls_unchanged", False),
            )
            base_op = _extract_access_operator(run["cases"][base_v]["plan"].get("operators", []))
            alt_op = _extract_access_operator(run["cases"][alt_v]["plan"].get("operators", []))
            comparisons_table.append(
                {
                    "stage_group": "Stage A",
                    "experiment_id": exp_id,
                    "query_id": query_id,
                    "comparison_label": f"{exp_id} ({query_id}): {base_v} vs {alt_v}",
                    "baseline_run_id": run_id,
                    "alternative_run_id": run_id,
                    "baseline_scenario": "baseline",
                    "alternative_scenario": "baseline",
                    "variant_or_cohort": f"{base_v}_vs_{alt_v}",
                    "returned_rows": (
                        run["cases"][base_v]["validation"]["result"]["rows"]
                        if run["equivalent"]
                        else None
                    ),
                    "status": comp["status"],
                    "baseline_median_ms": summaries[base_v]["median"],
                    "alternative_median_ms": summaries[alt_v]["median"],
                    "delta_ms": comp.get("alternative_minus_baseline_ms"),
                    "change_percent": comp.get("change_percent"),
                    "baseline_over_alternative": comp.get("baseline_over_alternative"),
                    "index_name": None,
                    "index_bytes": None,
                    "index_kib": None,
                    "index_object_id": None,
                    "before_plan_hash": run["cases"][base_v]["plan"].get("plan_hash"),
                    "after_plan_hash": run["cases"][alt_v]["plan"].get("plan_hash"),
                    "before_access": base_op["access_operator"],
                    "after_access": alt_op["access_operator"],
                    "limitation": comp.get("limitation") or comp.get("reason"),
                }
            )

    if (stage_a_samples_total, stage_a_warmups_total, stage_a_measured_total) != (105, 35, 70):
        raise DiagnosticError("Stage A sample totals do not match 105 (35 warmups + 70 measured).")

    # 2. Group A experimental index runs (5 isolated blocks, 10 runs, 6 comparisons, 180 samples)
    group_a_summary_path = ev_root / "group-a" / "summary.json"
    group_a_saved = _read_verified_json(
        group_a_summary_path,
        input_hashes,
        required_keys={"status", "samples", "warmups", "measured", "blocks", "comparisons"},
    )
    if (group_a_saved["samples"], group_a_saved["warmups"], group_a_saved["measured"]) != (180, 60, 120):
        raise DiagnosticError("Group A summary sample counts do not match 180 (60 warmups + 120 measured).")

    group_a_runs_cache: dict[str, tuple[dict, dict, dict]] = {}
    group_a_comparisons = []
    for entry in group_a_saved["comparisons"]:
        comp_saved = entry["comparison"]
        base_id = comp_saved["baseline_run_id"]
        alt_id = comp_saved["alternative_run_id"]
        variant = entry["variant"]
        for rid in (base_id, alt_id):
            if rid not in group_a_runs_cache:
                r_dir = ev_root / "group-a" / "runs" / rid
                r_obj, r_sums, r_qs = _load_and_verify_run(r_dir, rid, input_hashes)
                group_a_runs_cache[rid] = (r_obj, r_sums, r_qs)
                for v_key, v_stats in r_sums.items():
                    measurements.append(_build_measurement_row("Group A", r_obj, v_key, v_stats, r_qs[v_key]))

        base_run, base_sums, base_qs = group_a_runs_cache[base_id]
        alt_run, alt_sums, alt_qs = group_a_runs_cache[alt_id]
        if base_sums[variant] != entry["before"] or alt_sums[variant] != entry["after"]:
            raise DiagnosticError(f"Group A summary mismatch for index {entry['index']} ({variant}).")
        recomputed_comp = compare_runs(base_run, alt_run, variant=variant)
        if recomputed_comp != comp_saved:
            raise DiagnosticError(f"Group A comparison mismatch for index {entry['index']} ({variant}).")

        before_op = _extract_access_operator(entry.get("before_operators", []))
        after_op = _extract_access_operator(entry.get("after_operators", []))
        index_bytes = entry["bytes"]
        index_kib = index_bytes / 1024.0
        delta_ms = recomputed_comp["alternative_minus_baseline_ms"]
        pct = recomputed_comp["change_percent"]
        used_index = "INDEX" in (after_op["access_operator"] or "")
        if used_index and delta_ms < 0:
            outcome = "FAVORABLE (index selected, lower median latency)"
        elif used_index and delta_ms >= 0:
            outcome = "UNFAVORABLE (index selected, higher median latency on 50-block table)"
        else:
            outcome = "UNFAVORABLE / UNUSED (TABLE ACCESS FULL retained by CBO)"

        record = {
            "experiment_id": base_run["experiment_id"],
            "experiment": entry["experiment"],
            "query_id": base_run["query_id"],
            "scenario": entry["scenario"],
            "variant": variant,
            "index_name": entry["index"],
            "object_id": entry["object_id"],
            "index_bytes": index_bytes,
            "index_kib": index_kib,
            "returned_rows": entry["rows"],
            "result_sha256": entry["result_sha256"],
            "baseline_run_id": base_id,
            "alternative_run_id": alt_id,
            "before": base_sums[variant],
            "before_quartiles": base_qs[variant],
            "after": alt_sums[variant],
            "after_quartiles": alt_qs[variant],
            "comparison": recomputed_comp,
            "before_plan_hash": entry["before_plan_hash"],
            "after_plan_hash": entry["after_plan_hash"],
            "before_access": before_op["access_operator"],
            "after_access": after_op["access_operator"],
            "before_cost": before_op["optimizer_cost"],
            "after_cost": after_op["optimizer_cost"],
            "before_estimated_rows": before_op["estimated_rows"],
            "after_estimated_rows": after_op["estimated_rows"],
            "outcome": outcome,
        }
        group_a_comparisons.append(record)
        comparisons_table.append(
            {
                "stage_group": "Group A",
                "experiment_id": base_run["experiment_id"],
                "query_id": base_run["query_id"],
                "comparison_label": f"{base_run['experiment_id']} ({base_run['query_id']}) {entry['scenario']} [{variant}]",
                "baseline_run_id": base_id,
                "alternative_run_id": alt_id,
                "baseline_scenario": "baseline",
                "alternative_scenario": entry["scenario"],
                "variant_or_cohort": variant,
                "returned_rows": entry["rows"],
                "status": recomputed_comp["status"],
                "baseline_median_ms": base_sums[variant]["median"],
                "alternative_median_ms": alt_sums[variant]["median"],
                "delta_ms": delta_ms,
                "change_percent": pct,
                "baseline_over_alternative": recomputed_comp["baseline_over_alternative"],
                "index_name": entry["index"],
                "index_bytes": index_bytes,
                "index_kib": index_kib,
                "index_object_id": entry["object_id"],
                "before_plan_hash": entry["before_plan_hash"],
                "after_plan_hash": entry["after_plan_hash"],
                "before_access": before_op["access_operator"],
                "after_access": after_op["access_operator"],
                "limitation": recomputed_comp["block_limitation"],
            }
        )

    total_group_a_samples = sum(len(r[0]["samples"]) for r in group_a_runs_cache.values())
    if total_group_a_samples != 180:
        raise DiagnosticError("Group A raw run.json sample count does not equal 180.")

    # 3. Group B — E04 histogram experiment and exact statistics restoration
    gb_dir = ev_root / "group-b-histogram-final"
    run_a_id = EXPECTED_GROUP_B_RUNS["scenario_a"]
    run_b_id = EXPECTED_GROUP_B_RUNS["scenario_b"]
    run_a, sums_a, qs_a = _load_and_verify_run(gb_dir / "runs" / run_a_id, run_a_id, input_hashes)
    run_b, sums_b, qs_b = _load_and_verify_run(gb_dir / "runs" / run_b_id, run_b_id, input_hashes)

    for v_key, v_stats in sums_a.items():
        measurements.append(_build_measurement_row("Group B (Scenario A)", run_a, v_key, v_stats, qs_a[v_key]))
    for v_key, v_stats in sums_b.items():
        measurements.append(_build_measurement_row("Group B (Scenario B)", run_b, v_key, v_stats, qs_b[v_key]))

    obs_hist = _read_verified_json(
        gb_dir / "observed-histogram.json",
        input_hashes,
        required_keys={"evaluation", "post_gather_guard", "estimated_plans_with_histogram"},
    )
    saved_cohorts = _read_verified_json(
        gb_dir / "cohort-comparisons.json",
        input_hashes,
        required_keys={"cohorts"},
    )
    recovery_receipt = _read_verified_json(
        gb_dir / "recovery-receipt.json",
        input_hashes,
        required_keys={"operation", "status", "verification", "contents_sha256", "structure_sha256"},
    )
    field_comp = _read_verified_json(
        gb_dir / "field-comparison-after-recovery.json",
        input_hashes,
        required_keys={"before_statistics_sha256", "after_statistics_sha256", "overall_restoration"},
    )
    diff_after = _read_verified_json(
        gb_dir / "diff-after-recovery.json",
        input_hashes,
        required_keys={"columns", "rows"},
    )
    diff_maxdiffpct = str(diff_after["rows"][0][1]["oracle_number"])

    # Verify ORDERS.STATUS distribution across 3 independent sources in the evidence
    obs_status_counts = run_a["context"]["bind_observations"]["status_counts"]
    if obs_status_counts != EXPECTED_STATUS_COUNTS:
        raise DiagnosticError("ORDERS.STATUS counts in run.json do not match verified small/20261016 distribution.")
    endpoints = obs_hist["evaluation"]["endpoints_observed"]
    if [row[1] for row in endpoints] != [541, 1601, 7477, 10000]:
        raise DiagnosticError("Histogram cumulative endpoints in observed-histogram.json do not match [541, 1601, 7477, 10000].")
    endpoint_counts = {
        "CANCELLED": endpoints[0][1],
        "NEW": endpoints[1][1] - endpoints[0][1],
        "PAID": endpoints[2][1] - endpoints[1][1],
        "SHIPPED": endpoints[3][1] - endpoints[2][1],
    }
    if endpoint_counts != EXPECTED_STATUS_COUNTS:
        raise DiagnosticError("Histogram bucket deltas do not match ORDERS.STATUS distribution.")
    if (
        run_a["cases"]["baseline"]["validation"]["result"]["rows"] != 5876
        or run_a["cases"]["rare"]["validation"]["result"]["rows"] != 541
        or run_b["cases"]["baseline"]["validation"]["result"]["rows"] != 5876
        or run_b["cases"]["rare"]["validation"]["result"]["rows"] != 541
    ):
        raise DiagnosticError("E04 Q06 returned row counts do not match PAID=5876 and CANCELLED=541.")

    approval = "E04/ORDERS/" + digest([run_a, run_b])
    paid_comp = compare_statistics_runs(run_a, run_b, "baseline", approval=approval)
    cancelled_comp = compare_statistics_runs(run_a, run_b, "rare", approval=approval)
    if (
        paid_comp != saved_cohorts["cohorts"]["PAID_baseline"]["comparison"]
        or cancelled_comp != saved_cohorts["cohorts"]["CANCELLED_rare"]["comparison"]
    ):
        raise DiagnosticError("Recalculated E04 same-cohort comparisons diverge from cohort-comparisons.json.")

    group_b_cohorts = []
    for variant, cohort_name, comp_obj in (
        ("baseline", "PAID", paid_comp),
        ("rare", "CANCELLED", cancelled_comp),
    ):
        plan_a = run_a["cases"][variant]["plan"]
        plan_b = run_b["cases"][variant]["plan"]
        op_a = _extract_access_operator(plan_a.get("operators", []))
        op_b = _extract_access_operator(plan_b.get("operators", []))
        if op_a["estimated_rows"] != 2500 or op_b["estimated_rows"] != 2500:
            raise DiagnosticError("Unexpected E04 EXPLAIN PLAN cardinality; expected 2500 under unpeeked bind.")
        cohort_entry = {
            "cohort": cohort_name,
            "variant": variant,
            "actual_rows": EXPECTED_STATUS_COUNTS[cohort_name],
            "explain_plan_estimated_rows_before": op_a["estimated_rows"],
            "explain_plan_estimated_rows_after": op_b["estimated_rows"],
            "plan_hash_before": plan_a.get("plan_hash"),
            "plan_hash_after": plan_b.get("plan_hash"),
            "access_operator_before": op_a["access_operator"],
            "access_operator_after": op_b["access_operator"],
            "optimizer_cost_before": op_a["optimizer_cost"],
            "optimizer_cost_after": op_b["optimizer_cost"],
            "histogram_before": {"type": "NONE", "buckets": 1, "density": 0.25},
            "histogram_after": {
                "type": obs_hist["evaluation"]["histogram_type_observed"],
                "buckets": obs_hist["evaluation"]["num_buckets_observed"],
                "density": obs_hist["evaluation"]["density_observed"],
                "cumulative_endpoints": [541, 1601, 7477, 10000],
            },
            "latency_before": sums_a[variant],
            "quartiles_before": qs_a[variant],
            "latency_after": sums_b[variant],
            "quartiles_after": qs_b[variant],
            "comparison": comp_obj,
        }
        group_b_cohorts.append(cohort_entry)
        comparisons_table.append(
            {
                "stage_group": "Group B (E04)",
                "experiment_id": "E04",
                "query_id": "Q06",
                "comparison_label": f"E04 (Q06) {cohort_name}: Scenario A (NONE) vs Scenario B (FREQUENCY)",
                "baseline_run_id": run_a_id,
                "alternative_run_id": run_b_id,
                "baseline_scenario": "baseline",
                "alternative_scenario": "status-histogram",
                "variant_or_cohort": cohort_name,
                "returned_rows": EXPECTED_STATUS_COUNTS[cohort_name],
                "status": comp_obj["status"],
                "baseline_median_ms": sums_a[variant]["median"],
                "alternative_median_ms": sums_b[variant]["median"],
                "delta_ms": comp_obj["alternative_minus_baseline_ms"],
                "change_percent": comp_obj["change_percent"],
                "baseline_over_alternative": comp_obj["baseline_over_alternative"],
                "index_name": None,
                "index_bytes": None,
                "index_kib": None,
                "index_object_id": None,
                "before_plan_hash": plan_a.get("plan_hash"),
                "after_plan_hash": plan_b.get("plan_hash"),
                "before_access": op_a["access_operator"],
                "after_access": op_b["access_operator"],
                "limitation": comp_obj["block_limitation"],
            }
        )

    if (
        recovery_receipt["status"] != "PASS"
        or field_comp["overall_restoration"]["differences"] != []
        or field_comp["after_statistics_sha256"] != "6f27e295160307428e1deff18e1dfacdb9cd86c244a9c92f1b3a7e4551d1280d"
        or diff_maxdiffpct != "0"
    ):
        raise DiagnosticError("Group B post-experiment statistics restoration verification failed.")

    env_info = run_a.get("environment", {})
    catalog_summary = {
        qid: {
            "name": q.name,
            "benchmarked_in_phase4": qid in {"Q01", "Q02", "Q06", "Q07", "Q08"},
            "phase3_verified": True,
        }
        for qid, q in CATALOG.items()
    }

    return {
        "status": "PASS",
        "recalculated_matches_historical": True,
        "dataset": {
            "profile": "small",
            "seed": 20261016,
            "reference_date": "2026-10-16",
            "counts": run_a["context"]["manifest"]["counts"],
            "checksums": run_a["context"]["manifest"]["checksums"],
            "business_rows_total": 42500,
        },
        "environment_observed": {
            "oracle_version": run_a["context"]["oracle_version"],
            "identity": run_a["context"]["identity"],
            "python_version_phase4": env_info.get("python_version", "3.14.8"),
            "driver_version_phase4": env_info.get("driver_version", "26.0.1"),
            "oracle_image_digest": env_info.get("oracle_image_digest"),
        },
        "catalog_coverage": catalog_summary,
        "stage_a": {
            "runs_count": 5,
            "variant_cases_count": 7,
            "samples_total": stage_a_samples_total,
            "warmups_total": stage_a_warmups_total,
            "measured_total": stage_a_measured_total,
            "not_benchmarked_in_phase4": ["Q03", "Q04", "Q05"],
            "baselines": stage_a_records,
        },
        "group_a": {
            "blocks_count": 5,
            "runs_count": 10,
            "comparisons_count": 6,
            "samples_total": 180,
            "warmups_total": 60,
            "measured_total": 120,
            "comparisons": group_a_comparisons,
        },
        "group_b_e04": {
            "runs_count": 2,
            "samples_total": 60,
            "warmups_total": 20,
            "measured_total": 40,
            "status_distribution": EXPECTED_STATUS_COUNTS,
            "status_proportions": run_a["context"]["bind_observations"]["status_proportions"],
            "cumulative_endpoints": [
                {"status": "CANCELLED", "row_count": 541, "cumulative_endpoint": 541},
                {"status": "NEW", "row_count": 1060, "cumulative_endpoint": 1601},
                {"status": "PAID", "row_count": 5876, "cumulative_endpoint": 7477},
                {"status": "SHIPPED", "row_count": 2523, "cumulative_endpoint": 10000},
            ],
            "explain_plan_bind_limitation": (
                "EXPLAIN PLAN parses Q06 (WHERE status = :status) without bind peeking; Oracle CBO "
                "uses 1 / NUM_DISTINCT = 0.25 -> estimated_rows = 2,500 for both PAID and CANCELLED "
                "in both Scenario A (NONE) and Scenario B (FREQUENCY). Observing bucket-aware cursor "
                "cardinalities requires DBMS_XPLAN.DISPLAY_CURSOR (deferred in Group C)."
            ),
            "cohorts": group_b_cohorts,
            "restoration": {
                "status": "PASS",
                "operation": recovery_receipt["operation"],
                "active_orders_stats_sha256": field_comp["after_statistics_sha256"],
                "effective_state_sha256": field_comp["overall_restoration"]["after_sha256"],
                "backup_structure_sha256": recovery_receipt["structure_sha256"],
                "backup_contents_sha256": recovery_receipt["contents_sha256"],
                "field_differences": field_comp["overall_restoration"]["differences"],
                "diff_maxdiffpct": diff_maxdiffpct,
            },
        },
        "group_c": {
            "status": "DEFERRED",
            "reason": "Privileged fixed-view cursor metrics (V_$SQL, V_$SQL_PLAN, V_$SQL_PLAN_STATISTICS_ALL) formally deferred to future project versions by owner decision.",
        },
        "measurements": measurements,
        "comparisons": comparisons_table,
        "methodological_warnings": METHODOLOGICAL_WARNINGS,
        "input_hashes": dict(sorted(input_hashes.items())),
    }


def _save_dual_figure(fig, charts_dir: Path, stem: str) -> tuple[Path, Path]:
    svg_path = charts_dir / f"{stem}.svg"
    png_path = charts_dir / f"{stem}.png"
    _check_no_symlinks_in_chain(svg_path)
    _check_no_symlinks_in_chain(png_path)
    fig.savefig(
        svg_path,
        format="svg",
        metadata={"Date": None, "Creator": "OSPA Phase 5 / Matplotlib"},
    )
    fig.savefig(
        png_path,
        format="png",
        dpi=160,
        metadata={"Software": "OSPA Phase 5 / Matplotlib", "Creation Time": ""},
    )
    return svg_path, png_path


def _render_charts(bundle: dict, charts_dir: Path) -> list[str]:
    os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".local" / "matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    charts_dir.mkdir(parents=True, exist_ok=True)
    generated = []
    rc = {"svg.hashsalt": "ospa-phase5", "svg.fonttype": "none", "font.size": 9}

    # 1. Stage A Baselines Chart
    stage_a = bundle["stage_a"]["baselines"]
    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=(11, 5.5), layout="constrained")
        try:
            labels = [
                f"{r['experiment_id']} / {r['query_id']} [{r['variant']}]\n(rows={r['returned_rows']}, n={r['n']})"
                for r in stage_a
            ]
            y_pos = list(range(len(stage_a)))
            medians = [r["median_ms"] for r in stage_a]
            err_low = [max(0.0, r["median_ms"] - r["q25_ms"]) for r in stage_a]
            err_high = [max(0.0, r["q75_ms"] - r["median_ms"]) for r in stage_a]
            p95s = [r["p95_ms"] for r in stage_a]

            ax.barh(
                y_pos,
                medians,
                xerr=[err_low, err_high],
                capsize=4,
                color="#246aaf",
                alpha=0.88,
                label="Median (ms) with [Q25, Q75] IQR bar",
            )
            ax.scatter(p95s, y_pos, marker="|", s=180, color="#b22222", linewidths=2.2, label="p95 (ms)")
            for idx, r in enumerate(stage_a):
                ax.text(
                    max(r["p95_ms"], r["q75_ms"]) + 0.35,
                    idx,
                    f"med={r['median_ms']:.3f} ms | IQR={r['iqr_ms']:.3f} ms | p95={r['p95_ms']:.3f} ms",
                    va="center",
                    fontsize=8,
                )
            ax.set_yticks(y_pos, labels)
            ax.invert_yaxis()
            ax.set_xlim(0, max(p95s) * 1.38)
            ax.set_xlabel("Client execute + full fetch latency (ms)")
            ax.set_title(
                "Phase 4 Stage A — Five Baseline Experiment Runs (small, seed 20261016, n=10 measured, 5 warmups excluded)\n"
                "Query labels: E01->Q01, E02->Q02, E03->Q07, E04->Q06, E05->Q08 (Phase 3 catalog queries Q03, Q04, Q05 not timed in Phase 4).\n"
                "Note: Different returned row counts (1 to 5,876 rows) are not causal comparisons across queries."
            )
            ax.grid(axis="x", linestyle="--", alpha=0.4)
            ax.legend(loc="lower right")
            svg_p, png_p = _save_dual_figure(fig, charts_dir, "stage_a_baselines")
            generated.extend([svg_p.name, png_p.name])
        finally:
            plt.close(fig)

    # 2. Group A Experimental Index Comparisons Chart
    group_a = bundle["group_a"]["comparisons"]
    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=(12, 6.5), layout="constrained")
        try:
            n_cases = len(group_a)
            y_base = [i * 2.4 for i in range(n_cases)]
            y_alt = [i * 2.4 + 0.85 for i in range(n_cases)]
            y_ticks = [i * 2.4 + 0.425 for i in range(n_cases)]

            base_med = [c["before"]["median"] for c in group_a]
            base_low = [max(0.0, c["before"]["median"] - c["before_quartiles"]["q25"]) for c in group_a]
            base_high = [max(0.0, c["before_quartiles"]["q75"] - c["before"]["median"]) for c in group_a]
            base_p95 = [c["before"]["p95"] for c in group_a]

            alt_med = [c["after"]["median"] for c in group_a]
            alt_low = [max(0.0, c["after"]["median"] - c["after_quartiles"]["q25"]) for c in group_a]
            alt_high = [max(0.0, c["after_quartiles"]["q75"] - c["after"]["median"]) for c in group_a]
            alt_p95 = [c["after"]["p95"] for c in group_a]

            ax.barh(
                y_base,
                base_med,
                height=0.72,
                xerr=[base_low, base_high],
                capsize=3,
                color="#6c7a89",
                label="Contemporaneous Baseline (without experimental index) [Q25-Q75]",
            )
            ax.barh(
                y_alt,
                alt_med,
                height=0.72,
                xerr=[alt_low, alt_high],
                capsize=3,
                color="#1f7a4c",
                label="With Experimental Index [Q25-Q75]",
            )
            ax.scatter(base_p95, y_base, marker="|", s=140, color="black", linewidths=2.0, label="Baseline p95 (ms)")
            ax.scatter(alt_p95, y_alt, marker="|", s=140, color="#d9534f", linewidths=2.0, label="Indexed p95 (ms)")

            labels = []
            max_x = max(base_p95 + alt_p95)
            for idx, c in enumerate(group_a):
                pct = c["comparison"]["change_percent"]
                sign = "+" if pct >= 0 else ""
                labels.append(
                    f"{c['experiment_id']} ({c['query_id']}) {c['scenario']} [{c['variant']}]\n"
                    f"{c['index_name']} ({c['index_kib']:.0f} KiB, obj={c['object_id']})\n"
                    f"Plan: {c['before_plan_hash']} -> {c['after_plan_hash']}"
                )
                ax.text(
                    max(base_p95[idx], alt_p95[idx]) + 0.08,
                    y_ticks[idx],
                    f"{c['before']['median']:.3f} -> {c['after']['median']:.3f} ms ({sign}{pct:.2f}%)\n"
                    f"IQR: {c['before']['iqr']:.3f} -> {c['after']['iqr']:.3f} ms | {c['after_access']}",
                    va="center",
                    fontsize=7.8,
                )

            ax.set_yticks(y_ticks, labels)
            ax.invert_yaxis()
            ax.set_xlim(0, max_x * 1.58)
            ax.set_xlabel("Client execute + full fetch latency (ms) — n=10 measured, 5 warmups excluded, no outliers removed")
            ax.set_title(
                "Phase 4 Group A — Isolated Experimental Index Comparisons (DESCRIPTIVE ONLY)\n"
                "Unfavorable/unused index outcomes (E03 TRUNC +3.63%, E03 range +25.24%, E05 +10.77%) preserved without alteration."
            )
            ax.grid(axis="x", linestyle="--", alpha=0.4)
            ax.legend(loc="lower right", fontsize=8)
            svg_p, png_p = _save_dual_figure(fig, charts_dir, "group_a_index_comparisons")
            generated.extend([svg_p.name, png_p.name])
        finally:
            plt.close(fig)

    # 3. Group A Storage Cost vs Observed Latency Change Trade-off Chart
    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=(10, 5.2), layout="constrained")
        try:
            ax.axhline(0.0, color="black", linestyle="--", linewidth=1.0, alpha=0.7)
            for c in group_a:
                kib = c["index_kib"]
                pct = c["comparison"]["change_percent"]
                delta = c["comparison"]["alternative_minus_baseline_ms"]
                used = "INDEX" in (c["after_access"] or "")
                color = "#1f7a4c" if (used and pct < 0) else ("#d9534f" if (used and pct >= 0) else "#e67e22")
                marker = "o" if used else "s"
                ax.scatter([kib], [pct], s=130, color=color, marker=marker, edgecolors="black", zorder=3)
                cost_str = f"CBO Cost: {c['before_cost']}->{c['after_cost']}" if c["before_cost"] is not None else "CBO Cost: N/A"
                ax.annotate(
                    f"{c['experiment_id']}/{c['scenario']} [{c['variant']}]\n"
                    f"{kib:.0f} KiB | {pct:+.2f}% ({delta:+.3f} ms)\n{cost_str}",
                    (kib, pct),
                    textcoords="offset points",
                    xytext=(8, -6 if pct < 0 else 6),
                    fontsize=7.8,
                )
            ax.set_xlim(150, 440)
            ax.set_ylim(-65, 38)
            ax.set_xlabel("Verified Experimental Index Allocated Storage in USERS Tablespace (KiB)")
            ax.set_ylabel("Observed Median Latency Change (%) [Negative = Faster]")
            ax.set_title(
                "Phase 4 Group A — Storage Cost (KiB) vs. Observed Client Latency Change (%)\n"
                "Circles = CBO selected INDEX RANGE SCAN; Squares = CBO retained TABLE ACCESS FULL (DESCRIPTIVE ONLY)"
            )
            ax.grid(True, linestyle="--", alpha=0.4)
            svg_p, png_p = _save_dual_figure(fig, charts_dir, "group_a_storage_vs_latency")
            generated.extend([svg_p.name, png_p.name])
        finally:
            plt.close(fig)

    # 4. Group B E04 Status Distribution, EXPLAIN PLAN Cardinalities, and Same-Cohort Latency Chart
    gb = bundle["group_b_e04"]
    with plt.rc_context(rc):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.4), layout="constrained")
        try:
            # Panel 1: Actual ORDERS.STATUS distribution vs EXPLAIN PLAN Estimated Rows
            statuses = ["PAID", "SHIPPED", "NEW", "CANCELLED"]
            actuals = [gb["status_distribution"][s] for s in statuses]
            x_idx = list(range(len(statuses)))
            bars = ax1.bar(x_idx, actuals, color=["#246aaf", "#5c92c8", "#8ab4dc", "#c0d6ec"], edgecolor="black", width=0.55, label="Actual rows in ORDERS (total=10,000)")
            ax1.axhline(2500, color="#d9534f", linestyle="--", linewidth=2.0, label="EXPLAIN PLAN E-Rows = 2,500 (Scenario A & B)")
            endpoints_map = {e["status"]: e["cumulative_endpoint"] for e in gb["cumulative_endpoints"]}
            for idx, s_name in enumerate(statuses):
                cnt = actuals[idx]
                ep = endpoints_map[s_name]
                ax1.text(idx, cnt + 140, f"{cnt} rows\n(cum ep={ep})", ha="center", fontsize=8)
            ax1.set_xticks(x_idx, statuses)
            ax1.set_ylim(0, 6800)
            ax1.set_ylabel("Row count in ORDERS (small, seed 20261016)")
            ax1.set_title(
                "E04 Panel A — Actual ORDERS.STATUS Skew vs. EXPLAIN PLAN\n"
                "FREQUENCY Histogram (4 buckets: 541, 1601, 7477, 10000; density=0.00005)\n"
                "Unpeeked :status bind -> E-Rows stays 2,500 (Plan Hash 36248429)"
            )
            ax1.grid(axis="y", linestyle="--", alpha=0.4)
            ax1.legend(loc="upper right", fontsize=8)

            # Panel 2: Separate Same-Cohort Comparisons PAID(A vs B) and CANCELLED(A vs B)
            cohorts = gb["cohorts"]
            y_positions = [0.0, 0.85, 2.2, 3.05]
            labels_c = []
            meds_c = []
            low_c = []
            high_c = []
            p95_c = []
            colors_c = ["#246aaf", "#1f7a4c", "#7f8c8d", "#16a085"]
            for c_entry in cohorts:
                c_name = c_entry["cohort"]
                bef = c_entry["latency_before"]
                aft = c_entry["latency_after"]
                qb = c_entry["quartiles_before"]
                qa = c_entry["quartiles_after"]
                pct = c_entry["comparison"]["change_percent"]
                labels_c.extend(
                    [
                        f"{c_name} — Scenario A (HISTOGRAM=NONE)\nrows={c_entry['actual_rows']}, E-Rows=2500, n={bef['n']}",
                        f"{c_name} — Scenario B (FREQUENCY 4-bkt)\nrows={c_entry['actual_rows']}, E-Rows=2500, n={aft['n']} ({pct:+.2f}%)",
                    ]
                )
                meds_c.extend([bef["median"], aft["median"]])
                low_c.extend([max(0.0, bef["median"] - qb["q25"]), max(0.0, aft["median"] - qa["q25"])])
                high_c.extend([max(0.0, qb["q75"] - bef["median"]), max(0.0, qa["q75"] - aft["median"])])
                p95_c.extend([bef["p95"], aft["p95"]])

            ax2.barh(y_positions, meds_c, height=0.68, xerr=[low_c, high_c], capsize=3, color=colors_c, label="Median (ms) [Q25-Q75]")
            ax2.scatter(p95_c, y_positions, marker="|", s=150, color="#b22222", linewidths=2.0, label="p95 (ms)")
            for idx, y_val in enumerate(y_positions):
                iqr_val = low_c[idx] + high_c[idx]
                ax2.text(
                    p95_c[idx] + 0.4,
                    y_val,
                    f"med={meds_c[idx]:.3f} ms | IQR={iqr_val:.3f} ms | p95={p95_c[idx]:.3f} ms",
                    va="center",
                    fontsize=7.8,
                )
            ax2.set_yticks(y_positions, labels_c)
            ax2.invert_yaxis()
            ax2.set_xlim(0, max(p95_c) * 1.48)
            ax2.set_xlabel("Client execute + full fetch latency (ms)")
            ax2.set_title(
                "E04 Panel B — Separate Same-Cohort Comparisons (DESCRIPTIVE ONLY)\n"
                "PAID(A) vs PAID(B): +3.59%; CANCELLED(A) vs CANCELLED(B): +1.37%\n"
                "Cross-cohort PAID vs CANCELLED is NOT COMPARABLE (5,876 vs 541 rows)"
            )
            ax2.grid(axis="x", linestyle="--", alpha=0.4)
            ax2.legend(loc="lower right", fontsize=8)
            svg_p, png_p = _save_dual_figure(fig, charts_dir, "group_b_e04_status_and_cohorts")
            generated.extend([svg_p.name, png_p.name])
        finally:
            plt.close(fig)

    return generated


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    _check_no_symlinks_in_chain(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    _check_no_symlinks_in_chain(temp)
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fieldnames})
    temp.replace(path)


def _write_text_atomic(path: Path, text: str) -> None:
    _check_no_symlinks_in_chain(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    _check_no_symlinks_in_chain(temp)
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def _fmt_num(val, digits: int = 6) -> str:
    if val is None:
        return "N/A"
    return f"{val:.{digits}f}"


def _build_markdown_report(bundle: dict) -> str:
    ds = bundle["dataset"]
    env = bundle["environment_observed"]
    lines = [
        "# Oracle SQL Performance Analyzer (OSPA) — Phase 5 Reproducible Benchmark Report",
        "",
        "## 1. Provenance and Verification Summary",
        "",
        f"- **Verification Status:** `{bundle['status']}` (`recalculated_matches_historical = {bundle['recalculated_matches_historical']}`)",
        f"- **Dataset Profile & Seed:** `{ds['profile']}` / seed `{ds['seed']}` (`{ds['business_rows_total']}` business rows across `CUSTOMERS={ds['counts']['customers']}`, `PRODUCTS={ds['counts']['products']}`, `ORDERS={ds['counts']['orders']}`, `ORDER_ITEMS={ds['counts']['order_items']}`)",
        f"- **Observed Oracle Engine:** `{env['oracle_version']}` (`{env['identity'][0]}` in `{env['identity'][1]}`), Python `{env['python_version_phase4']}`, `python-oracledb` `{env['driver_version_phase4']}` Thin mode",
        "- **Timer Scope:** Client-side `time.perf_counter_ns()` around `cursor.execute()` + `cursor.fetchall()` in milliseconds (`ms`).",
        "- **Statistical Policy:** 5 warmups excluded from summaries (retained in raw JSON); all 10 measured repetitions included (`0` outliers removed); percentiles linearly interpolated at `(n - 1) * p`.",
        "",
        "## 2. Stage A — Baseline Queries (`E01`–`E05`)",
        "",
        "![Stage A Baselines](charts/stage_a_baselines.svg)",
        "",
        "| Experiment | Query | Variant | Rows | n | Warmups | Failures | Median (ms) | Mean (ms) | IQR (ms) | p95 (ms) | Min / Max (ms) | StdDev (ms) | Plan Hash | Access Operator | Run ID |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- | ---: | ---: | :--- | :--- |",
    ]
    for r in bundle["stage_a"]["baselines"]:
        lines.append(
            f"| `{r['experiment_id']}` | `{r['query_id']}` | `{r['variant']}` | {r['returned_rows']} | {r['n']} | {r['warmups']} | {r['failures']} | "
            f"{_fmt_num(r['median_ms'])} | {_fmt_num(r['mean_ms'])} | {_fmt_num(r['iqr_ms'])} | {_fmt_num(r['p95_ms'])} | "
            f"{_fmt_num(r['min_ms'], 3)} / {_fmt_num(r['max_ms'], 3)} | {_fmt_num(r['stddev_ms'])} | `{r['plan_hash']}` | `{r['access_operator']}` | `{r['run_id']}` |"
        )
    lines.extend(
        [
            "",
            "> **Catalog Coverage Note (`Q01`–`Q08`):** Stage A benchmarked `Q01` (`E01`), `Q02` (`E02`), `Q06` (`E04`), `Q07` (`E03`), and `Q08` (`E05`). Catalog queries `Q03`, `Q04`, and `Q05` were verified functionally and via estimated plans in Phase 3 without timed Phase 4 benchmark runs; no latency metrics are fabricated for `Q03`–`Q05`.",
            "",
            "## 3. Group A — Experimental Index Evaluations (`E01`, `E02`, `E03`, `E05`)",
            "",
            "![Group A Index Comparisons](charts/group_a_index_comparisons.svg)",
            "",
            "![Group A Storage vs Latency](charts/group_a_storage_vs_latency.svg)",
            "",
            "| Exp / Query | Scenario / Variant | Index (`OBJECT_ID`) | Size (KiB) | Baseline Median (ms) | Indexed Median (ms) | Delta (ms) | Change (%) | Baseline IQR / p95 (ms) | Indexed IQR / p95 (ms) | Plan Hash (Before -> After) | Cost (Before -> After) | Access Operator After | Status |",
            "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )
    for c in bundle["group_a"]["comparisons"]:
        comp = c["comparison"]
        bef = c["before"]
        aft = c["after"]
        lines.append(
            f"| `{c['experiment_id']}` (`{c['query_id']}`) | `{c['scenario']}` [`{c['variant']}`] | `{c['index_name']}` (`{c['object_id']}`) | {c['index_kib']:.0f} | "
            f"{_fmt_num(bef['median'])} | {_fmt_num(aft['median'])} | {comp['alternative_minus_baseline_ms']:+.6f} | {comp['change_percent']:+.2f}% | "
            f"{_fmt_num(bef['iqr'], 3)} / {_fmt_num(bef['p95'], 3)} | {_fmt_num(aft['iqr'], 3)} / {_fmt_num(aft['p95'], 3)} | "
            f"`{c['before_plan_hash']} -> {c['after_plan_hash']}` | `{c['before_cost']} -> {c['after_cost']}` | `{c['after_access']}` | `{comp['status']}` |"
        )

    gb = bundle["group_b_e04"]
    lines.extend(
        [
            "",
            "## 4. Group B — `E04` (`ORDERS.STATUS` Histogram, Bind Peeking & Exact Restoration)",
            "",
            "![Group B E04 Status and Cohorts](charts/group_b_e04_status_and_cohorts.svg)",
            "",
            "### 4.1 Verified `ORDERS.STATUS` Distribution (`small`, seed `20261016`)",
            "",
            "| Status Value | Actual Row Count | Proportion | Cumulative `FREQUENCY` Endpoint | Static `EXPLAIN PLAN` E-Rows (Scenario A & B) |",
            "| :--- | ---: | ---: | ---: | ---: |",
        ]
    )
    for ep in sorted(gb["cumulative_endpoints"], key=lambda x: -x["row_count"]):
        st = ep["status"]
        prop = gb["status_proportions"][st] * 100.0
        e_rows_str = "2500 (`Q06` bind `:status`)" if st in ("PAID", "CANCELLED") else "N/A (not queried as `Q06` cohort)"
        lines.append(f"| `{st}` | {ep['row_count']} | {prop:.2f}% | {ep['cumulative_endpoint']} | {e_rows_str} |")

    lines.extend(
        [
            "",
            "### 4.2 Separate Same-Cohort Comparisons (`PAID(A) vs PAID(B)` and `CANCELLED(A) vs CANCELLED(B)`)",
            "",
            "| Cohort (`:status`) | Actual Rows | Scenario A (`NONE`) Median / IQR / p95 (ms) | Scenario B (`FREQUENCY`) Median / IQR / p95 (ms) | Delta Median (ms) | Change (%) | E-Rows (A -> B) | Plan Hash (A -> B) | Status |",
            "| :--- | ---: | :--- | :--- | ---: | ---: | :--- | :--- | :--- |",
        ]
    )
    for c_entry in gb["cohorts"]:
        bef = c_entry["latency_before"]
        aft = c_entry["latency_after"]
        comp = c_entry["comparison"]
        lines.append(
            f"| `{c_entry['cohort']}` | {c_entry['actual_rows']} | "
            f"{_fmt_num(bef['median'])} / {_fmt_num(bef['iqr'], 3)} / {_fmt_num(bef['p95'], 3)} | "
            f"{_fmt_num(aft['median'])} / {_fmt_num(aft['iqr'], 3)} / {_fmt_num(aft['p95'], 3)} | "
            f"{comp['alternative_minus_baseline_ms']:+.6f} | {comp['change_percent']:+.2f}% | "
            f"`{c_entry['explain_plan_estimated_rows_before']} -> {c_entry['explain_plan_estimated_rows_after']}` | "
            f"`{c_entry['plan_hash_before']} -> {c_entry['plan_hash_after']}` | `{comp['status']}` |"
        )

    rest = gb["restoration"]
    lines.extend(
        [
            "",
            f"- **Why `EXPLAIN PLAN` Estimated 2,500 Rows in Scenario B:** {gb['explain_plan_bind_limitation']}",
            f"- **Post-Experiment Restoration (`{rest['operation']}`):** `{rest['status']}` — active `ORDERS` stats SHA-256 `{rest['active_orders_stats_sha256']}`, field differences `{rest['field_differences']}`, `DIFF_TABLE_STATS_IN_STATTAB` `MAXDIFFPCT = {rest['diff_maxdiffpct']}`.",
            "",
            "## 5. Methodological Warnings and Limitations",
            "",
        ]
    )
    for warning in bundle["methodological_warnings"]:
        lines.append(f"- {warning}")
    return "\n".join(lines) + "\n"


def _verify_no_secret_patterns(output_dir: Path) -> None:
    forbidden_tokens = ["ORACLE_PASSWORD="]
    env_file = ROOT / ".env"
    if env_file.is_file() and not env_file.is_symlink():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("ORACLE_PASSWORD="):
                    secret_val = line.partition("=")[2].strip()
                    if secret_val:
                        forbidden_tokens.append(secret_val)
        except OSError:
            pass
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.suffix in {".json", ".csv", ".md", ".svg"}:
            text = path.read_text(encoding="utf-8")
            for token in forbidden_tokens:
                if token in text:
                    raise DiagnosticError(f"Sensitive configuration token detected in generated artifact: {path.name}")


def render_phase5_bundle(
    output_dir: str | Path = RESULTS_PHASE5,
    evidence_root: str | Path = EVIDENCE_PHASE4,
) -> dict:
    """Validate Phase 4 evidence, recalculate statistics, and write the complete Phase 5 artifact bundle."""
    target_dir = validate_output_directory(output_dir, evidence_root)
    bundle = collect_and_verify_phase4_evidence(evidence_root)

    target_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = target_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    # Check output targets are not symlinks
    expected_files = [
        target_dir / "summary.json",
        target_dir / "measurements.csv",
        target_dir / "comparisons.csv",
        target_dir / "report.md",
        target_dir / "manifest.json",
    ]
    for fpath in expected_files:
        _check_no_symlinks_in_chain(fpath)

    # 1. Write summary.json
    summary_payload = {k: v for k, v in bundle.items() if k != "input_hashes"}
    _write_text_atomic(
        target_dir / "summary.json",
        json.dumps(summary_payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )

    # 2. Write measurements.csv
    measurement_fields = [
        "stage_group",
        "experiment_id",
        "experiment",
        "query_id",
        "scenario",
        "variant",
        "run_id",
        "returned_rows",
        "unit",
        "n",
        "warmups",
        "failures",
        "warmup_failures",
        "median_ms",
        "mean_ms",
        "q25_ms",
        "q75_ms",
        "iqr_ms",
        "p95_ms",
        "min_ms",
        "max_ms",
        "stddev_ms",
        "plan_hash",
        "plan_capture_type",
        "access_operator",
        "estimated_rows",
        "optimizer_cost",
        "result_sha256",
        "sql_sha256",
    ]
    _write_csv(target_dir / "measurements.csv", bundle["measurements"], measurement_fields)

    # 3. Write comparisons.csv
    comparison_fields = [
        "stage_group",
        "experiment_id",
        "query_id",
        "comparison_label",
        "baseline_run_id",
        "alternative_run_id",
        "baseline_scenario",
        "alternative_scenario",
        "variant_or_cohort",
        "returned_rows",
        "status",
        "baseline_median_ms",
        "alternative_median_ms",
        "delta_ms",
        "change_percent",
        "baseline_over_alternative",
        "index_name",
        "index_bytes",
        "index_kib",
        "index_object_id",
        "before_plan_hash",
        "after_plan_hash",
        "before_access",
        "after_access",
        "limitation",
    ]
    _write_csv(target_dir / "comparisons.csv", bundle["comparisons"], comparison_fields)

    # 4. Write report.md
    _write_text_atomic(target_dir / "report.md", _build_markdown_report(bundle))

    # 5. Render charts (*.svg and *.png)
    chart_names = _render_charts(bundle, charts_dir)

    # 6. Scan outputs for secrets
    _verify_no_secret_patterns(target_dir)

    # 7. Build and write manifest.json
    import matplotlib

    output_artifacts = {}
    for rel_path in [
        "summary.json",
        "measurements.csv",
        "comparisons.csv",
        "report.md",
        *[f"charts/{name}" for name in sorted(chart_names)],
    ]:
        full_p = target_dir / rel_path
        raw_b = full_p.read_bytes()
        output_artifacts[rel_path] = {
            "sha256": sha256(raw_b).hexdigest(),
            "bytes": len(raw_b),
        }

    manifest = {
        "schema_version": 1,
        "status": "PASS",
        "generator": "oracle_spa.phase5_report.render_phase5_bundle",
        "package_version": PACKAGE_VERSION,
        "dataset": {
            "profile": bundle["dataset"]["profile"],
            "seed": bundle["dataset"]["seed"],
            "business_rows_total": bundle["dataset"]["business_rows_total"],
            "checksums": bundle["dataset"]["checksums"],
        },
        "runs_verified": {
            "stage_a": [r_id for _, _, r_id in EXPECTED_STAGE_A_RUNS],
            "group_a": sorted({c["baseline_run_id"] for c in bundle["group_a"]["comparisons"]} | {c["alternative_run_id"] for c in bundle["group_a"]["comparisons"]}),
            "group_b_e04": [EXPECTED_GROUP_B_RUNS["scenario_a"], EXPECTED_GROUP_B_RUNS["scenario_b"]],
        },
        "tool_versions": {
            "python": sys.version.split()[0],
            "matplotlib": matplotlib.__version__,
            "oracle_server_observed_in_evidence": bundle["environment_observed"]["oracle_version"],
            "oracledb_driver_observed_in_evidence": bundle["environment_observed"]["driver_version_phase4"],
        },
        "generation_parameters": {
            "offline_mode": True,
            "oracle_connection_used": False,
            "percentile_method": "linear interpolation at (n-1)*p",
            "warmups_excluded": True,
            "outliers_removed": False,
            "svg_hashsalt": "ospa-phase5",
            "png_dpi": 160,
        },
        "reproducibility_note": (
            "JSON, CSV, and Markdown outputs are deterministic in numerical content, ordering, and UTF-8 bytes. "
            "SVG and PNG charts are deterministic in data and structure; cross-platform pixel/byte identity "
            "depends on the local FreeType/Matplotlib font stack."
        ),
        "input_evidence_files_count": len(bundle["input_hashes"]),
        "input_evidence_sha256": bundle["input_hashes"],
        "output_artifacts": output_artifacts,
    }
    _write_text_atomic(
        target_dir / "manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
    )

    try:
        display_out = str(target_dir.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        display_out = str(target_dir)

    return {
        "status": "PASS",
        "output_directory": display_out,
        "recalculated_matches_historical": True,
        "measurements_count": len(bundle["measurements"]),
        "comparisons_count": len(bundle["comparisons"]),
        "charts_generated": sorted(chart_names),
        "artifacts": list(output_artifacts.keys()) + ["manifest.json"],
    }


def audit_markdown_links(
    root: Path | str = ROOT,
    require_generated_exist: bool = False,
    results_dir: Path | str | None = None,
) -> dict[str, int]:
    """Audit all relative Markdown links in documentation.

    Distinguishes between versioned source/evidence files (which must always exist)
    and offline-generated Phase 5 artifacts (which must match allowlisted output paths
    and are checked for existence on disk when require_generated_exist is True or when
    results_dir already exists on disk).
    """
    import re

    base_root = Path(root).resolve()
    _check_no_symlinks_in_chain(base_root)

    canonical_results_dir = (base_root / "results" / "phase5").resolve()
    target_results_dir = (
        Path(results_dir).resolve()
        if results_dir is not None
        else canonical_results_dir
    )

    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    md_files = sorted(list(base_root.glob("*.md")) + list((base_root / "docs").glob("*.md")))

    total_links = 0
    versioned_links = 0
    generated_links = 0

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(content):
            target = raw_target.strip().split()[0]
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            rel_path = target.split("#", 1)[0]
            if not rel_path:
                continue

            # Anti-traversal check: resolved path must stay within repository
            resolved = (md_file.parent / rel_path).resolve()
            if not (resolved == base_root or resolved.is_relative_to(base_root)):
                raise DiagnosticError(
                    f"Path traversal outside repository forbidden in {md_file.name}: {raw_target} -> {resolved}"
                )

            total_links += 1

            # Check if this link targets the recognized generated output directory
            is_canonical_gen = (resolved == canonical_results_dir or resolved.is_relative_to(canonical_results_dir))
            is_target_gen = (resolved == target_results_dir or resolved.is_relative_to(target_results_dir))

            if is_canonical_gen or is_target_gen:
                if is_canonical_gen:
                    subpath = resolved.relative_to(canonical_results_dir).as_posix().rstrip("/")
                else:
                    subpath = resolved.relative_to(target_results_dir).as_posix().rstrip("/")

                if subpath and subpath not in PHASE5_OUTPUT_ARTIFACT_NAMES:
                    raise DiagnosticError(
                        f"Unrecognized generated artifact link in {md_file.name}: {raw_target} "
                        f"(subpath '{subpath}' is not in PHASE5_OUTPUT_ARTIFACT_NAMES)"
                    )
                generated_links += 1

                if require_generated_exist or target_results_dir.exists():
                    disk_target = target_results_dir / subpath if subpath else target_results_dir
                    _check_no_symlinks_in_chain(disk_target, stop_at=target_results_dir)
                    if not disk_target.exists():
                        raise DiagnosticError(
                            f"Generated artifact link broken (not found on disk) in {md_file.name}: "
                            f"{raw_target} -> {disk_target}"
                        )
            else:
                # Versioned repository file (source, docs, sql, tests, evidence)
                # Must not contain intermediate symlinks and must exist on disk
                _check_no_symlinks_in_chain(resolved, stop_at=base_root)
                if not resolved.exists():
                    raise DiagnosticError(
                        f"Broken versioned file link in {md_file.name}: {raw_target} -> {resolved}"
                    )
                versioned_links += 1

    return {
        "files_audited": len(md_files),
        "total_links": total_links,
        "versioned_links": versioned_links,
        "generated_links": generated_links,
    }
