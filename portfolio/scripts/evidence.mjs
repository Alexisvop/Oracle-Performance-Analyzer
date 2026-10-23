// Curated public fields only. Never copy whole database receipts into the website.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath, URL } from 'node:url';
import assert from 'node:assert/strict';

const root = new URL('../../', import.meta.url);
const hashes = {};
function read(path) {
  const bytes = readFileSync(new URL(path, root));
  hashes[path] = createHash('sha256').update(bytes).digest('hex');
  return JSON.parse(bytes);
}
const phase4 = 'docs/evidence/phase4/';
const caveats = [
  'client_execute_full_fetch',
  'sequential_blocks',
  'single_host_small_seed',
  'estimated_plans_only',
];
export function percentile(values, p) {
  const sorted = [...values].sort((a, b) => a - b);
  assert(sorted.length > 0 && p >= 0 && p <= 1);
  assert(sorted.every((x) => typeof x === 'number' && Number.isFinite(x) && x >= 0));
  const rank = (sorted.length - 1) * p;
  const low = Math.floor(rank);
  return sorted[low] + (sorted[Math.ceil(rank)] - sorted[low]) * (rank - low);
}
function measurement(path, variant) {
  const run = read(path);
  const historical = read(path.replace('run.json', 'summary.json')).summaries[variant];
  assert.equal(run.status, 'PASS');
  const samples = run.samples.filter((s) => s.variant === variant && !s.warmup);
  assert.equal(samples.length, 10);
  assert(samples.every((s) => s.status === 'PASS' && s.sql_error === null));
  const values = samples.map((s) => s.elapsed_ms);
  const q25 = percentile(values, 0.25),
    q75 = percentile(values, 0.75);
  const stats = { median: percentile(values, 0.5), iqr: q75 - q25, p95: percentile(values, 0.95) };
  for (const [key, value] of Object.entries(stats))
    assert(Math.abs(value - historical[key]) < 1e-10, `${path}: ${key}`);
  const { validation, plan } = run.cases[variant];
  assert.equal(validation.status, 'PASS');
  assert.equal(plan.type, 'ESTIMATED_PLAN');
  return {
    experimentId: run.experiment_id,
    queryId: run.query_id,
    variant,
    scenario: run.scenario,
    sql: validation.sql,
    rows: validation.result.rows,
    resultSha256: validation.result.result_sha256,
    ...stats,
    q25,
    q75,
    n: samples.length,
    warmups: run.warmups,
    unit: 'ms',
    indexConfiguration: run.context.authorized_indexes,
    estimatedPlan: {
      hash: plan.plan_hash,
      operators: plan.operators,
    },
    actualCursorMetrics: null,
    evidence: path,
    caveats,
  };
}
const baselineIds = [
  'c4cd44eae137426cbdfec81f66cab75a',
  '9dffbb99f3fe48e08ec80e18a9aa536d',
  'b158e3a5c72249f9bf8a362f8a75eeea',
  'a64fbcf36ff14a758698e301435ff310',
  '7efe329021d4435688bf2ca9f755cca7',
];
const baselines = baselineIds.flatMap((id) => {
  const path = `${phase4}runs/${id}/run.json`;
  return Object.keys(read(path).cases).map((v) => measurement(path, v));
});
const groupA = read(`${phase4}group-a/summary.json`);
const indexes = groupA.comparisons.map((c) => {
  const before = measurement(
    `${phase4}group-a/runs/${c.comparison.baseline_run_id}/run.json`,
    c.variant,
  );
  const after = measurement(
    `${phase4}group-a/runs/${c.comparison.alternative_run_id}/run.json`,
    c.variant,
  );
  assert.equal(before.resultSha256, after.resultSha256);
  const receiptPath = `${phase4}group-a/${c.index}.json`;
  const receipt = read(receiptPath);
  assert.equal(receipt.status, 'CLOSED');
  const changePercent = (after.median / before.median - 1) * 100;
  assert(Math.abs(changePercent - c.comparison.change_percent) < 1e-10);
  return {
    id: `${before.experimentId}-${c.scenario}-${c.variant}`,
    index: c.index,
    configuration: receipt.ddl_attempts.find((x) => x.action === 'create').sql,
    storageKiB: c.bytes / 1024,
    before,
    after,
    changePercent,
    evidence: receiptPath,
  };
});
const bpath = `${phase4}group-b-histogram-final/`;
const cohortComparisons = read(`${bpath}cohort-comparisons.json`);
assert(cohortComparisons);
const cohorts = ['baseline', 'rare'].map((v, i) => {
  const before = measurement(`${bpath}runs/82b1df0bc6bb40738719801106790567/run.json`, v);
  const after = measurement(`${bpath}runs/232234a4a9ea4f56880afbb6749b585e/run.json`, v);
  assert.equal(before.resultSha256, after.resultSha256);
  return {
    status: ['PAID', 'CANCELLED'][i],
    before,
    after,
    changePercent: (after.median / before.median - 1) * 100,
  };
});
const observed = read(`${bpath}observed-histogram.json`);
const histogramPlans = Object.values(observed.estimated_plans_with_histogram);
assert(histogramPlans.every((p) => p.operators[0].estimated_rows === 2500));
const original = read(`${bpath}runs/82b1df0bc6bb40738719801106790567/run.json`);
const stageDPath = 'docs/evidence/phase5/stage-d/summary.json';
const stageD = read(stageDPath);
const stageAPath = 'docs/evidence/phase5/stage-a/summary.json';
read(stageAPath);
const data = {
  schemaVersion: 1,
  evidenceEdition: 'sanitized-public-edition',
  dataset: {
    profile: 'small',
    seed: original.context.seed,
    counts: original.context.manifest.counts,
    businessRows: Object.values(original.context.manifest.counts).reduce((a, b) => a + b, 0),
  },
  quality: {
    unitTests: stageD.offline_demonstration_flow_a.unit_tests_passed,
    subtests: stageD.offline_demonstration_flow_a.unit_subtests_passed,
    unitEvidence: stageDPath,
    integrationEvidence: stageAPath,
  },
  statusCounts: original.context.bind_observations.status_counts,
  histogram: { evidence: `${bpath}observed-histogram.json`, estimatedRows: 2500, cohorts },
  baselines,
  indexes,
  sources: Object.fromEntries(Object.entries(hashes).sort(([a], [b]) => a.localeCompare(b))),
};
const target = fileURLToPath(new URL('../src/data/evidence.json', import.meta.url));
const serialized = JSON.stringify(data, null, 2) + '\n';
if (process.argv.includes('--write')) writeFileSync(target, serialized);
else
  assert.equal(
    readFileSync(target, 'utf8'),
    serialized,
    'Curated data differs from evidence. Review, then npm run data:generate.',
  );
console.log(
  `PASS: ${Object.keys(hashes).length} input SHA-256 hashes; 23 measurements recalculated; 8 same-result comparisons; zero Oracle access.`,
);
