import { useEffect, useState, type ReactNode } from 'react';
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Braces,
  ChartNoAxesCombined,
  Check,
  ChevronDown,
  CodeXml as Github,
  Database,
  FileCheck2,
  Fingerprint,
  GitBranch,
  Layers3,
  Menu,
  ShieldCheck,
  Terminal,
  X,
} from 'lucide-react';
import { translations, type Copy, type Language } from './i18n';
import {
  evidence,
  number,
  percent,
  repository,
  sourceUrl,
  usesIndex,
  type IndexExperiment,
  type Measurement,
} from './data/metrics';

const sectionIds = [
  'overview',
  'architecture',
  'features',
  'results',
  'quality',
  'docs',
  'future',
] as const;
function Source({ path, children }: { path: string; children: ReactNode }) {
  return (
    <a className="source-link" href={sourceUrl(path)}>
      {children}
      <ArrowUpRight size={14} aria-hidden="true" />
    </a>
  );
}
function SectionHeading({ index, title, text }: { index: string; title: string; text?: string }) {
  return (
    <div className="section-heading">
      <span className="eyebrow">{index}</span>
      <h2>{title}</h2>
      {text && <p>{text}</p>}
    </div>
  );
}
function PairBars({ before, after, t }: { before: number; after: number; t: Copy }) {
  const max = Math.max(before, after);
  return (
    <div className="pair-bars" aria-hidden="true">
      {[
        [t.baseline, before],
        [t.indexed, after],
      ].map(([label, value], i) => (
        <div className="bar-line" key={i}>
          <span>{label}</span>
          <div className="bar-track">
            <div
              className={`bar-fill ${i === 1 ? 'alternative' : ''}`}
              style={{ width: `${(Number(value) / max) * 100}%` }}
            />
          </div>
          <strong>
            {number(Number(value))} <small>ms</small>
          </strong>
        </div>
      ))}
    </div>
  );
}
function Plan({ measurement, t }: { measurement: Measurement; t: Copy }) {
  return (
    <div className="plan">
      <p className="mono">
        {t.estimated} · hash {measurement.estimatedPlan.hash}
      </p>
      <ol>
        {measurement.estimatedPlan.operators.map((op) => (
          <li key={op.id}>
            <code>
              {op.id} · {[op.operation, op.options, op.object].filter(Boolean).join(' ')}
            </code>
            <span>
              E-Rows {op.estimated_rows ?? '—'} · Cost {op.optimizer_cost ?? '—'}
            </span>
          </li>
        ))}
      </ol>
      <Source path={measurement.evidence}>
        {t.evidence} · {measurement.queryId} / {measurement.variant}
      </Source>
    </div>
  );
}
function ExperimentCard({ item, t }: { item: IndexExperiment; t: Copy }) {
  return (
    <article className="experiment-card">
      <div className="experiment-top">
        <div>
          <span className="mono muted">
            {item.before.experimentId} / {item.before.queryId}
          </span>
          <h4>
            {item.before.experimentId === 'E03'
              ? `ORDER_DATE · ${item.before.variant === 'baseline' ? 'TRUNC' : 'range'}`
              : item.before.experimentId === 'E01'
                ? 'EMAIL'
                : item.before.experimentId === 'E02'
                  ? `CUSTOMER_ID · ${item.after.scenario}`
                  : 'Top-N'}
          </h4>
        </div>
        <span className={`delta ${item.changePercent < 0 ? 'favorable' : 'unfavorable'}`}>
          {percent(item.changePercent)}
        </span>
      </div>
      <PairBars before={item.before.median} after={item.after.median} t={t} />
      <p className="plan-status">
        <span className={`status-dot ${usesIndex(item) ? 'cyan' : 'amber'}`} />
        {usesIndex(item) ? t.selected : t.ignored}
      </p>
      <details>
        <summary>
          {t.details}
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <code className="sql">{item.configuration}</code>
        <p>
          {item.storageKiB} KiB · {item.before.rows.toLocaleString('en-US')} {t.rows} · n = 10 /{' '}
          {t.baseline}, n = 10 / {t.indexed}
        </p>
        <table>
          <caption>{t.client} (ms)</caption>
          <thead>
            <tr>
              <th scope="col">{t.experiment}</th>
              <th scope="col">{t.median}</th>
              <th scope="col">IQR</th>
              <th scope="col">p95</th>
            </tr>
          </thead>
          <tbody>
            {[item.before, item.after].map((m, i) => (
              <tr key={i}>
                <th scope="row">{i ? t.indexed : t.baseline}</th>
                <td>{number(m.median, 6)}</td>
                <td>{number(m.iqr, 6)}</td>
                <td>{number(m.p95, 6)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <code className="sql">{item.before.sql}</code>
        <Plan measurement={item.before} t={t} />
        <Plan measurement={item.after} t={t} />
        <p className="small muted">{t.cursorUnavailable}</p>
        <Source path={item.evidence}>
          {t.evidence} · {item.index}
        </Source>
      </details>
    </article>
  );
}
function StorageChart({ t }: { t: Copy }) {
  return (
    <>
      <figure className="scatter">
        <svg
          viewBox="0 0 760 365"
          role="img"
          aria-labelledby="storage-title"
          aria-describedby="storage-desc"
        >
          <title id="storage-title">{t.storageCaption}</title>
          <desc id="storage-desc">
            {evidence.indexes
              .map((item) => `${item.id}: ${item.storageKiB} KiB, ${percent(item.changePercent)}`)
              .join('; ')}
          </desc>
          {[-60, -40, -20, 0, 20, 40].map((tick) => (
            <g key={tick}>
              <line
                x1="82"
                x2="705"
                y1={278 - (tick + 60) * 2.1}
                y2={278 - (tick + 60) * 2.1}
                className={tick === 0 ? 'zero-line' : 'grid-line'}
              />
              <text x="66" y={282 - (tick + 60) * 2.1} textAnchor="end">
                {tick}%
              </text>
            </g>
          ))}
          {[192, 256, 320, 384].map((tick) => (
            <text key={tick} x={100 + (tick - 160) * 2.5} y="307" textAnchor="middle">
              {tick}
            </text>
          ))}
          {evidence.indexes.map((item, i) => {
            const x = 100 + (item.storageKiB - 160) * 2.5,
              y = 278 - (item.changePercent + 60) * 2.1;
            return (
              <g key={item.id}>
                <circle
                  cx={x}
                  cy={y}
                  r="6"
                  className={item.changePercent < 0 ? 'point-good' : 'point-bad'}
                />
                <text x={x + 11} y={y + (i === 3 ? 18 : -11)}>
                  {item.before.experimentId}
                  {item.before.experimentId === 'E03'
                    ? ` ${item.before.variant === 'baseline' ? 'TRUNC' : 'range'}`
                    : item.before.experimentId === 'E02'
                      ? ` ${item.after.scenario}`
                      : ''}
                </text>
              </g>
            );
          })}
          <text x="395" y="345" textAnchor="middle">
            {t.storageAxis}
          </text>
        </svg>
        <figcaption>{t.changeAxis}</figcaption>
      </figure>
      <p className="small muted">{t.storageNote}</p>
      <div className="table-scroll" role="region" tabIndex={0} aria-label={t.storageCaption}>
        <table>
          <caption>{t.storageCaption}</caption>
          <thead>
            <tr>
              <th scope="col">{t.experiment}</th>
              <th scope="col">KiB</th>
              <th scope="col">{t.baseline} (ms)</th>
              <th scope="col">{t.indexed} (ms)</th>
              <th scope="col">{t.delta}</th>
            </tr>
          </thead>
          <tbody>
            {evidence.indexes.map((item) => (
              <tr key={item.id}>
                <th scope="row">{item.id}</th>
                <td>{item.storageKiB}</td>
                <td>{number(item.before.median, 6)}</td>
                <td>{number(item.after.median, 6)}</td>
                <td>{percent(item.changePercent)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
function Baselines({ t }: { t: Copy }) {
  const [selected, setSelected] = useState(0);
  const m = evidence.baselines[selected];
  return (
    <>
      <label className="select-label" htmlFor="baseline-selector">
        {t.experiment}
      </label>
      <select
        id="baseline-selector"
        value={selected}
        onChange={(event) => setSelected(Number(event.target.value))}
      >
        {evidence.baselines.map((item, i) => (
          <option value={i} key={`${item.queryId}-${item.variant}`}>
            {item.experimentId} / {item.queryId} · {item.variant}
            {item.queryId === 'Q06'
              ? ` · ${item.variant === 'baseline' ? 'PAID' : 'CANCELLED'}`
              : ''}
          </option>
        ))}
      </select>
      <div className="baseline-reading">
        <strong>
          {number(m.median, 6)} <small>ms</small>
        </strong>
        <span>
          {t.client} · {m.rows.toLocaleString('en-US')} {t.rows} · n = {m.n}
        </span>
      </div>
      <div
        className="distribution"
        role="img"
        aria-label={`${t.median}: ${number(m.median, 6)} ms; Q25: ${number(m.q25, 6)} ms; Q75: ${number(m.q75, 6)} ms; p95: ${number(m.p95, 6)} ms`}
      >
        <span>Q25 {number(m.q25)} ms</span>
        <div className="interval">
          <div
            className="quartiles"
            style={{
              left: `${(m.q25 / m.p95) * 100}%`,
              width: `${((m.q75 - m.q25) / m.p95) * 100}%`,
            }}
          />
          <div className="median-marker" style={{ left: `${(m.median / m.p95) * 100}%` }} />
        </div>
        <span>p95 {number(m.p95)} ms</span>
      </div>
      <p className="small muted">{t.baselineNote}</p>
      <Plan measurement={m} t={t} />
      <div className="table-scroll" role="region" tabIndex={0} aria-label={t.baselineCaption}>
        <table>
          <caption>{t.baselineCaption} · ms · n = 10</caption>
          <thead>
            <tr>
              <th scope="col">{t.experiment}</th>
              <th scope="col">{t.rows}</th>
              <th scope="col">{t.median}</th>
              <th scope="col">IQR</th>
              <th scope="col">p95</th>
            </tr>
          </thead>
          <tbody>
            {evidence.baselines.map((item) => (
              <tr key={`${item.queryId}-${item.variant}`}>
                <th scope="row">
                  {item.experimentId} / {item.queryId} · {item.variant}
                  {item.queryId === 'Q06'
                    ? ` (${item.variant === 'baseline' ? 'PAID' : 'CANCELLED'})`
                    : ''}
                </th>
                <td>{item.rows.toLocaleString('en-US')}</td>
                <td>{number(item.median, 6)}</td>
                <td>{number(item.iqr, 6)}</td>
                <td>{number(item.p95, 6)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
function Histogram({ t }: { t: Copy }) {
  return (
    <article id="histogram" className="histogram" aria-labelledby="histogram-heading">
      <div className="histogram-heading">
        <span className="eyebrow">GROUP B · E04</span>
        <h3 id="histogram-heading">{t.histogramTitle}</h3>
        <p>{t.histogramText}</p>
      </div>
      <div className="histogram-grid">
        <figure>
          <figcaption>{t.statusCaption}</figcaption>
          <div className="status-distribution">
            {Object.entries(evidence.statusCounts).map(([status, count]) => (
              <div key={status}>
                <div>
                  <code>{status}</code>
                  <span>
                    {count.toLocaleString('en-US')} · {number(count / 100, 2)}%
                  </span>
                </div>
                <div className="bar-track">
                  <div className="bar-fill alternative" style={{ width: `${count / 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          <Source path={evidence.histogram.evidence}>{t.evidence} · ORDERS.STATUS</Source>
        </figure>
        <div>
          <p className="figure-title">{t.cohortCaption}</p>
          {evidence.histogram.cohorts.map((c) => (
            <div className="cohort" key={c.status}>
              <div>
                <code>{c.status}</code>
                <span className="delta unfavorable">{percent(c.changePercent)}</span>
              </div>
              <p className="mono">
                {number(c.before.median, 6)} → {number(c.after.median, 6)} ms
              </p>
              <PairBars
                before={c.before.median}
                after={c.after.median}
                t={{ ...t, baseline: 'A · NONE', indexed: 'B · FREQUENCY' }}
              />
              <p className="small muted">
                IQR {number(c.before.iqr, 6)} → {number(c.after.iqr, 6)} ms
                <br />
                p95 {number(c.before.p95, 6)} → {number(c.after.p95, 6)} ms
              </p>
              <Source path={c.before.evidence}>A · {t.evidence}</Source>
              <Source path={c.after.evidence}>B · {t.evidence}</Source>
            </div>
          ))}
        </div>
      </div>
      <p className="callout">{t.cohortNote}</p>
      <div className="histogram-plan">
        <code>SELECT STATEMENT → SORT ORDER BY → TABLE ACCESS FULL ORDERS</code>
        <span>
          E-Rows = {evidence.histogram.estimatedRows.toLocaleString('en-US')} · Cost = 16 · hash
          36248429
        </span>
      </div>
      <p className="small muted">{t.cursorUnavailable}</p>
      <p className="restoration">
        <ShieldCheck size={19} aria-hidden="true" />
        {t.restoration}
      </p>
      <Source path="docs/evidence/phase4/group-b-histogram-final/field-comparison-after-recovery.json">
        SHA-256 / MAXDIFFPCT · {t.evidence}
      </Source>
    </article>
  );
}
export default function App() {
  const [language, setLanguage] = useState<Language>('en');
  const [menuOpen, setMenuOpen] = useState(false);
  const [view, setView] = useState<'groupA' | 'stageA' | 'storage'>('groupA');
  const t = translations[language];
  useEffect(() => {
    document.documentElement.lang = language;
    document.title = `OSPA — ${language === 'en' ? 'Oracle SQL Performance Analyzer' : 'Laboratorio de rendimiento SQL'}`;
  }, [language]);
  const e01 = evidence.indexes[0];
  const e03Range = evidence.indexes[4];
  return (
    <>
      <a href="#main" className="skip-link">
        {t.skip}
      </a>
      <header className="site-header">
        <div className="nav-shell">
          <a href="#top" className="brand" aria-label="OSPA">
            <span className="brand-icon">
              <Database size={21} aria-hidden="true" />
            </span>
            OSPA
            <span className="brand-divider" />
            <span className="brand-description">SQL PERFORMANCE LAB</span>
          </a>
          <nav
            aria-label={language === 'en' ? 'Main navigation' : 'Navegación principal'}
            className={menuOpen ? 'navigation open' : 'navigation'}
          >
            {sectionIds
              .filter((id) => !['features', 'future'].includes(id))
              .map((id) => (
                <a key={id} href={`#${id}`} onClick={() => setMenuOpen(false)}>
                  {t[id]}
                </a>
              ))}
          </nav>
          <div className="nav-actions">
            <div className="language-switch" role="group" aria-label={t.language}>
              {(['en', 'es'] as const).map((lang) => (
                <button
                  key={lang}
                  type="button"
                  lang={lang}
                  aria-pressed={language === lang}
                  onClick={() => setLanguage(lang)}
                >
                  {lang.toUpperCase()}
                </button>
              ))}
            </div>
            <a className="github-icon" href={repository} aria-label={t.source}>
              <Github size={21} aria-hidden="true" />
            </a>
            <button
              className="menu-button"
              aria-label={t.menu}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
            </button>
          </div>
        </div>
      </header>
      <main id="main">
        <section className="hero" id="top">
          <div className="hero-grid">
            <div className="hero-copy">
              <span className="eyebrow">
                <span className="status-dot cyan" />
                {t.eyebrow}
              </span>
              <h1>
                Oracle SQL
                <br />
                <span>Performance</span>
                <br />
                Analyzer<span className="title-dot">.</span>
              </h1>
              <p className="hero-subtitle">{t.subtitle}</p>
              <p className="hero-description">{t.heroText}</p>
              <div className="hero-actions">
                <a className="button primary" href="#results">
                  {t.explore}
                  <ArrowDown size={17} aria-hidden="true" />
                </a>
                <a className="button secondary" href={repository}>
                  <Github size={17} aria-hidden="true" />
                  {t.source}
                </a>
              </div>
              <a className="hero-docs" href="#docs">
                {t.technical}
                <ArrowRight size={16} aria-hidden="true" />
              </a>
            </div>
            <div className="hero-visual">
              <div className="visual-label">
                <span className="status-dot cyan" />
                {t.observation}
                <span className="mono">n = 10</span>
              </div>
              <div className="hero-result">
                <span>
                  {number(-e01.changePercent, 2)}
                  <small>%</small>
                </span>
                <p>{t.lower}</p>
              </div>
              <PairBars before={e01.before.median} after={e01.after.median} t={t} />
              <div className="terminal">
                <div className="terminal-title">
                  <Terminal size={15} aria-hidden="true" />
                  Q01 / EMAIL<span>EXPLAIN PLAN</span>
                </div>
                <pre tabIndex={0} role="region" aria-label="Q01 / SQL">
                  <code>
                    <span className="sql-keyword">SELECT</span> customer_id, full_name, email{'\n'}
                    <span className="sql-keyword">FROM</span> customers{'\n'}
                    <span className="sql-keyword">WHERE</span> email = :email
                  </code>
                </pre>
                <div className="plan-transition">
                  <span>TABLE ACCESS FULL</span>
                  <ArrowRight size={16} aria-hidden="true" />
                  <strong>INDEX RANGE SCAN</strong>
                </div>
              </div>
              <p className="small muted">{t.heroCaveat}</p>
              <Source path={e01.after.evidence}>{t.evidence} · Phase 4 / Group A</Source>
            </div>
          </div>
          <div className="metrics-strip">
            {[
              [number(evidence.dataset.businessRows, 0), t.synthetic],
              ['8', t.queries],
              [String(evidence.quality.unitTests), t.tests],
              ['5', t.experimental],
            ].map(([value, label]) => (
              <div key={label}>
                <strong>{value}</strong>
                <span>{label}</span>
              </div>
            ))}
          </div>
          <p className="hero-footnote">
            {t.heroNote}
            <a href="#highlights">
              <ArrowDown size={16} aria-hidden="true" />
              {language === 'en' ? 'Three key findings' : 'Tres hallazgos clave'}
            </a>
          </p>
        </section>
        <section id="highlights" className="recruiter-brief" aria-labelledby="brief-title">
          <div className="brief-heading">
            <div>
              <span className="eyebrow">{t.briefEyebrow}</span>
              <h2 id="brief-title">{t.briefTitle}</h2>
            </div>
            <p>{t.briefText}</p>
          </div>
          <div className="brief-grid">
            <article className="brief-card improvement">
              <div className="brief-card-top">
                <span>{t.briefImproveTag}</span>
                <span className="brief-card-symbol" aria-hidden="true">↘</span>
              </div>
              <p className="brief-value">{percent(e01.changePercent)}</p>
              <span className="brief-unit">{t.client}</span>
              <h3>{t.briefImproveTitle}</h3>
              <p className="brief-explanation">{t.briefImproveText}</p>
              <div className="brief-card-actions">
                <a href="#results">{t.briefInspect}<ArrowRight size={15} aria-hidden="true" /></a>
                <Source path={e01.after.evidence}>{t.evidence}</Source>
              </div>
            </article>
            <article className="brief-card regression">
              <div className="brief-card-top">
                <span>{t.briefRegressionTag}</span>
                <span className="brief-card-symbol" aria-hidden="true">↗</span>
              </div>
              <p className="brief-value">{percent(e03Range.changePercent)}</p>
              <span className="brief-unit">{t.client}</span>
              <h3>{t.briefRegressionTitle}</h3>
              <p className="brief-explanation">{t.briefRegressionText}</p>
              <div className="brief-card-actions">
                <a href="#results">{t.briefInspect}<ArrowRight size={15} aria-hidden="true" /></a>
                <Source path={e03Range.after.evidence}>{t.evidence}</Source>
              </div>
            </article>
            <article className="brief-card estimate">
              <div className="brief-card-top">
                <span>{t.briefHistogramTag}</span>
                <span className="brief-card-symbol" aria-hidden="true">≡</span>
              </div>
              <p className="brief-value brief-value-estimate">
                {number(evidence.histogram.estimatedRows, 0)}
                <span aria-hidden="true"> → </span>
                {number(evidence.histogram.estimatedRows, 0)}
              </p>
              <span className="brief-unit">E-Rows · {t.estimated}</span>
              <h3>{t.briefHistogramTitle}</h3>
              <p className="brief-explanation">{t.briefHistogramText}</p>
              <div className="brief-card-actions">
                <a href="#histogram">{t.briefInspect}<ArrowRight size={15} aria-hidden="true" /></a>
                <Source path={evidence.histogram.evidence}>{t.evidence}</Source>
              </div>
            </article>
          </div>
          <p className="brief-caveat"><ShieldCheck size={16} aria-hidden="true" />{t.briefCaveat}</p>
        </section>
        <section id="overview" className="section">
          <SectionHeading
            index={`01 / ${t.overview}`}
            title={t.overviewTitle}
            text={t.overviewText}
          />
          <div className="overview-grid">
            {[
              [t.problemTitle, t.problemText],
              [t.approachTitle, t.approachText],
              [t.proofTitle, t.proofText],
            ].map(([title, text], i) => (
              <article key={title}>
                <span className="step-number">0{i + 1}</span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
          <Source path="docs/portfolio-summary.md">{t.technical}</Source>
        </section>
        <section id="architecture" className="section">
          <SectionHeading
            index={`02 / ${t.architecture}`}
            title={t.architectureTitle}
            text={t.architectureText}
          />
          <figure className="architecture">
            <div className="architecture-live">
              <div className="arch-node cli-node">
                <Terminal aria-hidden="true" />
                <strong>{t.cli}</strong>
                <code>cli.py</code>
              </div>
              <div className="arch-modules">
                {[
                  [t.dataEngine, 'data_generator.py · loader.py · validation.py'],
                  [t.workload, 'queries.py · execution.py'],
                  [t.planEngine, 'plans.py'],
                  [t.benchmark, 'benchmark.py · indexes.py · statistics_experiment.py'],
                ].map(([label, file]) => (
                  <div className="arch-node" key={file}>
                    <strong>{label}</strong>
                    <code>{file}</code>
                  </div>
                ))}
              </div>
              <div className="arch-node oracle-node">
                <Database size={31} aria-hidden="true" />
                <strong>{t.database}</strong>
                <code>python-oracledb · Thin</code>
              </div>
            </div>
            <div className="architecture-offline">
              {[
                [t.artifact, 'docs/evidence/phase4/'],
                [t.analysis, 'analysis.py · phase5_report.py'],
                [t.ci, '.github/workflows/ci.yml'],
              ].map(([label, file]) => (
                <div className="arch-node" key={file}>
                  <FileCheck2 aria-hidden="true" />
                  <strong>{label}</strong>
                  <code>{file}</code>
                </div>
              ))}
            </div>
            <div className="portfolio-branch">
              <FileCheck2 aria-hidden="true" />
              <span>
                {t.artifact} → <code>evidence.mjs</code> → {t.website}
              </span>
              <code>portfolio/src/data/</code>
            </div>
            <figcaption>{t.diagramCaption}</figcaption>
          </figure>
          <Source path="docs/architecture.md">{t.architectureDoc}</Source>
        </section>
        <section id="features" className="section">
          <SectionHeading index={`03 / ${t.features}`} title={t.featuresTitle} />
          <div className="feature-grid">
            {[
              [Fingerprint, t.f1Title, t.f1Text],
              [Check, t.f2Title, t.f2Text],
              [GitBranch, t.f3Title, t.f3Text],
              [ShieldCheck, t.f4Title, t.f4Text],
              [ChartNoAxesCombined, t.f5Title, t.f5Text],
              [Layers3, t.f6Title, t.f6Text],
            ].map(([Icon, title, text]) => {
              const Component = Icon as typeof Fingerprint;
              return (
                <article className="feature" key={String(title)}>
                  <Component size={23} aria-hidden="true" />
                  <h3>{String(title)}</h3>
                  <p>{String(text)}</p>
                </article>
              );
            })}
          </div>
        </section>
        <section id="results" className="section results-section">
          <SectionHeading index={`04 / ${t.results}`} title={t.resultsTitle} text={t.resultsText} />
          <aside className="methodology">
            <span className="eyebrow">{t.methodology}</span>
            <p>{t.caveatText}</p>
          </aside>
          <div className="view-controls" role="group" aria-label={t.results}>
            {(['groupA', 'stageA', 'storage'] as const).map((key) => (
              <button
                type="button"
                key={key}
                aria-pressed={view === key}
                onClick={() => setView(key)}
              >
                {t[key]}
              </button>
            ))}
          </div>
          <div className="results-panel">
            {view === 'groupA' ? (
              <>
                <h3 className="figure-title">{t.indexCaption}</h3>
                <p className="small muted">
                  {t.client} · ms · n = 10 · IQR / p95: {t.details}
                </p>
                <div className="experiments-grid">
                  {evidence.indexes.map((item) => (
                    <ExperimentCard item={item} t={t} key={item.id} />
                  ))}
                </div>
                <div className="insights">
                  <h3>{t.interpretation}</h3>
                  <p>{t.emailInsight}</p>
                  <p>{t.dateInsight}</p>
                  <p>{t.topInsight}</p>
                  <p className="small muted">{t.inference}</p>
                </div>
              </>
            ) : view === 'stageA' ? (
              <Baselines t={t} />
            ) : (
              <StorageChart t={t} />
            )}
          </div>
          <Histogram t={t} />
        </section>
        <section id="quality" className="section">
          <SectionHeading index={`05 / ${t.quality}`} title={t.qualityTitle} text={t.qualityText} />
          <div className="quality-banner">
            <div>
              <strong>
                {evidence.quality.unitTests}
                <small> + {evidence.quality.subtests}</small>
              </strong>
              <span>
                {t.tests} / {language === 'en' ? 'subtests' : 'subpruebas'}
              </span>
            </div>
            <div>
              <strong>SHA-256</strong>
              <span>{t.q1Title}</span>
            </div>
            <div>
              <strong>0</strong>
              <span>
                {language === 'en'
                  ? 'Oracle connections needed by this site'
                  : 'conexiones Oracle requeridas por este sitio'}
              </span>
            </div>
          </div>
          <div className="quality-grid">
            {[
              [t.q1Title, t.q1Text],
              [t.q2Title, t.q2Text],
              [t.q3Title, t.q3Text],
            ].map(([title, text]) => (
              <article key={title}>
                <ShieldCheck aria-hidden="true" />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
          <div className="source-row">
            <Source path={evidence.quality.unitEvidence}>Phase 5 / Stage D</Source>
            <Source path={evidence.quality.integrationEvidence}>Phase 5 / Stage A</Source>
            <a className="source-link" href={`${import.meta.env.BASE_URL}data/evidence.json`}>
              {t.provenance}
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </div>
          <p className="small muted">{t.historical}</p>
        </section>
        <section id="docs" className="section">
          <SectionHeading index={`06 / ${t.docs}`} title={t.docsTitle} />
          <p className="callout">
            {t.repositoryAccess}
            <br />
            <a className="source-link" href={`${import.meta.env.BASE_URL}data/evidence.json`}>
              {t.provenance}
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </p>
          <div className="demo-grid">
            <article className="demo-card">
              <Terminal aria-hidden="true" />
              <h3>{t.offline}</h3>
              <p>{t.offlineText}</p>
              <pre tabIndex={0} role="region" aria-label={t.offline}>
                <code>
                  .venv/bin/python -m pytest -q tests/unit{'\n'}.venv/bin/python -m oracle_spa.cli
                  report-all --output results/phase5
                </code>
              </pre>
              <Source path="docs/demo.md#flow-a--offline-demonstration-no-oracle-required">
                {t.guide}
              </Source>
            </article>
            <article className="demo-card">
              <Database aria-hidden="true" />
              <h3>{t.live}</h3>
              <p>{t.liveText}</p>
              <div className="lab-tag">
                <ShieldCheck size={18} aria-hidden="true" />
                {t.lab}
              </div>
              <Source path="docs/demo.md#flow-b--live-oracle-laboratory-demonstration-rootless-podman-on-arch-linux">
                {t.guide}
              </Source>
            </article>
          </div>
          <div className="doc-links">
            {[
              ['README.md', t.technical],
              ['docs/architecture.md', t.architectureDoc],
              ['docs/development.md', t.reproducibilityDoc],
              ['docs/findings.md', t.findingsDoc],
            ].map(([path, label]) => (
              <Source key={path} path={path}>
                {label}
              </Source>
            ))}
            <a className="source-link" href={repository}>
              {t.source}
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </div>
        </section>
        <section id="future" className="section future-section">
          <SectionHeading index={`07 / ${t.future}`} title={t.futureTitle} />
          <div className="future-grid">
            {[
              [t.future1, t.future1Text],
              [t.future2, t.future2Text],
              [t.future3, t.future3Text],
              [t.future4, t.future4Text],
            ].map(([title, text]) => (
              <article key={title}>
                <span className="future-badge">{t.futureBadge}</span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <footer>
        <a href="#top" className="brand">
          <Braces size={23} aria-hidden="true" />
          OSPA
        </a>
        <p>{t.footer}</p>
        <Source path="THIRD_PARTY_NOTICES.md">{language === 'en' ? 'Third-party notices' : 'Avisos de terceros'}</Source>
        <a href="#top">
          {t.back}
          <ArrowRight size={15} aria-hidden="true" />
        </a>
      </footer>
    </>
  );
}
