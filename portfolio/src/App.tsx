import { useEffect, useState, type ReactNode } from 'react';
import {
  ArrowUpRight,
  ChevronDown,
  CodeXml as Github,
  Menu,
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
function SectionHeading({ title, text }: { title: string; text?: string }) {
  return (
    <div className="section-heading">
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
function planDepth(ops: { id: number; parent_id: number | null }[], id: number): number {
  const op = ops.find((o) => o.id === id);
  return op && op.parent_id !== null ? 1 + planDepth(ops, op.parent_id) : 0;
}
function HeroPlan({ item, t }: { item: IndexExperiment; t: Copy }) {
  const columns = t.planColumns.split('|');
  const states = [
    [t.planBefore, item.before],
    [t.planAfter, item.after],
  ] as const;
  return (
    <div className="xplan">
      {states.map(([label, measurement]) => {
        const ops = measurement.estimatedPlan.operators;
        return (
          <div className="xplan-block" key={label} role="group" aria-label={label}>
            <p className="xplan-head">
              <span>{label}</span>
              <span className="xplan-median">
                {t.planMedian} <b>{number(measurement.median)} ms</b>
              </span>
            </p>
            <div className="xplan-row xplan-cols" aria-hidden="true">
              {columns.map((c) => (
                <span key={c}>{c}</span>
              ))}
            </div>
            <ol className="xplan-ops">
              {ops.map((op) => (
                <li
                  key={op.id}
                  className={
                    'xplan-row' + (op.object === item.index || op.options === 'FULL' ? ' xplan-key' : '')
                  }
                >
                  <span>{op.id}</span>
                  <span style={{ paddingLeft: `${planDepth(ops, op.id)}ch` }}>
                    {[op.operation, op.options].filter(Boolean).join(' ')}
                  </span>
                  <span>
                    {op.object && <span className="sr-only">{columns[2]} </span>}
                    {op.object ?? ''}
                  </span>
                  <span>
                    <span className="sr-only">{columns[3]} </span>
                    {op.estimated_rows ?? '—'}
                  </span>
                  <span>
                    <span className="sr-only">{columns[4]} </span>
                    {op.optimizer_cost ?? '—'}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        );
      })}
    </div>
  );
}
const experimentNames: Record<string, keyof Copy> = {
  'E01-email-baseline': 'expE01',
  'E02-simple-baseline': 'expE02s',
  'E02-composite-baseline': 'expE02c',
  'E03-date-index-baseline': 'expE03t',
  'E03-date-index-range': 'expE03r',
  'E05-status-date-baseline': 'expE05',
};
const baselineNames: Record<string, keyof Copy> = {
  'Q01-baseline': 'expE01',
  'Q02-baseline': 'expE02s',
  'Q07-baseline': 'expE03t',
  'Q07-range': 'expE03r',
  'Q06-baseline': 'expQ06p',
  'Q06-rare': 'expQ06c',
  'Q08-baseline': 'expE05',
};
/** Plain-language query name; Q02 baselines drop the index suffix because no index existed yet. */
function baselineName(m: { queryId: string; variant: string }, t: Copy) {
  const key = baselineNames[`${m.queryId}-${m.variant}`];
  const name = key ? t[key] : `${m.queryId} · ${m.variant}`;
  return m.queryId === 'Q02' ? name.split(' · ')[0] : name;
}
/** Deepest operator that touches a table or index: the access path a reader compares. */
function accessPath(m: Measurement) {
  const ops = m.estimatedPlan.operators.filter((op) => op.object);
  const leaf = ops[ops.length - 1];
  return leaf ? [leaf.operation, leaf.options].filter(Boolean).join(' ') : '—';
}
const glossaryKeys = ['g1', 'g2', 'g3', 'g4', 'g5', 'g6', 'g7', 'g8'] as const;
function ExperimentCard({ item, t }: { item: IndexExperiment; t: Copy }) {
  const before = accessPath(item.before);
  const after = accessPath(item.after);
  const key = experimentNames[item.id];
  return (
    <article className="experiment-card">
      <div className="experiment-main">
        <h4>{key ? t[key] : item.id}</h4>
        <p className="experiment-id">
          {item.before.experimentId} / {item.before.queryId}
        </p>
      </div>
      <p className="experiment-plan">
        <span className="sr-only">{t.planLabel}: </span>
        <code>{before}</code>
        {before === after ? (
          <span className="experiment-same"> · {t.samePlan}</span>
        ) : (
          <>
            {' → '}
            <code>{after}</code>
          </>
        )}
      </p>
      <PairBars before={item.before.median} after={item.after.median} t={t} />
      <span className={`delta ${item.changePercent < 0 ? 'favorable' : 'unfavorable'}`}>
        {percent(item.changePercent)}
      </span>
      <details>
        <summary>
          {t.details}
          <ChevronDown size={16} aria-hidden="true" />
        </summary>
        <p>{usesIndex(item) ? t.selected : t.ignored}.</p>
        <code className="sql">{item.configuration}</code>
        <p>
          {item.storageKiB} KiB · {item.before.rows.toLocaleString('en-US')} {t.rows} · n = 10 /{' '}
          {t.baseline}, n = 10 / {t.indexed}
        </p>
        <div className="table-scroll" role="region" tabIndex={0} aria-label={`${item.id} · ${t.client} (ms)`}>
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
        </div>
        <code className="sql">{item.before.sql}</code>
        <Plan measurement={item.before} t={t} />
        <Plan measurement={item.after} t={t} />
        <a className="source-link" href="#method">
          {t.methodology}
        </a>
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
            {baselineName(item, t)} ({item.experimentId} / {item.queryId})
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
                  {baselineName(item, t)}
                  <span className="row-id">
                    {item.experimentId} / {item.queryId}
                  </span>
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
      <p className="restoration">
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
  const [activeSection, setActiveSection] = useState<string>('');
  const t = translations[language];
  useEffect(() => {
    document.documentElement.lang = language;
    document.title = `OSPA — ${language === 'en' ? 'Oracle SQL Performance Analyzer' : 'Laboratorio de rendimiento SQL'}`;
  }, [language]);
  // Mark the section being read in the sticky navigation; skipped where IntersectionObserver is missing.
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) if (entry.isIntersecting) setActiveSection(entry.target.id);
      },
      { rootMargin: '-40% 0px -55% 0px' },
    );
    for (const id of sectionIds) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, []);
  const e01 = evidence.indexes[0];
  const e03Range = evidence.indexes[4];
  const navCurrent = activeSection === 'features' ? 'overview' : activeSection;
  return (
    <>
      <a href="#main" className="skip-link">
        {t.skip}
      </a>
      <header className="site-header">
        <div className="nav-shell">
          <a href="#top" className="brand" aria-label="OSPA">
            OSPA
            <span className="brand-description">SQL performance lab</span>
          </a>
          <nav
            aria-label={language === 'en' ? 'Main navigation' : 'Navegación principal'}
            className={menuOpen ? 'navigation open' : 'navigation'}
          >
            {sectionIds
              .filter((id) => !['features', 'future'].includes(id))
              .map((id) => (
                <a
                  key={id}
                  href={`#${id}`}
                  aria-current={navCurrent === id ? 'location' : undefined}
                  onClick={() => setMenuOpen(false)}
                >
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
              <h1>Oracle SQL Performance Analyzer</h1>
              <p className="hero-subtitle">{t.subtitle}</p>
              <p className="hero-description">{t.heroText}</p>
              <div className="hero-actions">
                <a className="button primary" href="#results">
                  {t.explore}
                </a>
                <a className="button secondary" href={repository}>
                  {t.source}
                </a>
              </div>
              <a className="hero-docs" href="#docs">
                {t.technical}
              </a>
            </div>
            <figure className="hero-visual">
              <figcaption className="visual-label">
                <span>{t.observation}</span>
                <span className="mono">E01 / Q01 · n = 10</span>
              </figcaption>
              <pre className="hero-sql">
                <code>
                  <span className="sql-keyword">SELECT</span> customer_id, full_name, email{'\n'}
                  <span className="sql-keyword">FROM</span> customers{'\n'}
                  <span className="sql-keyword">WHERE</span> email = :email
                </code>
              </pre>
              <HeroPlan item={e01} t={t} />
              <p className="plan-key">{t.planKey}</p>
              <p className="hero-result">
                <span className="hero-result-value">
                  <span>{number(-e01.changePercent, 2)}</span>%
                </span>
                <span>{t.lower}</span>
              </p>
              <div className="hero-links">
                <a className="source-link" href="#method">
                  {t.howMeasured}
                </a>
                <Source path={e01.after.evidence}>{t.evidence} · Phase 4 / Group A</Source>
              </div>
            </figure>
          </div>
          <p className="hero-facts">
            <b>{number(evidence.dataset.businessRows, 0)}</b> {t.synthetic}, <b>8</b> {t.queries},{' '}
            <b>5</b> {t.experimental} {t.and} <b>{evidence.quality.unitTests}</b> {t.tests}.
          </p>
        </section>
        <section id="highlights" className="recruiter-brief" aria-labelledby="brief-title">
          <div className="brief-heading">
            <h2 id="brief-title">{t.briefTitle}</h2>
            <p>{t.briefText}</p>
          </div>
          <div className="brief-grid">
            <article className="brief-card improvement">
              <div className="brief-card-top">
                <span>{t.briefImproveTag}</span>
              </div>
              <p className="brief-value">{percent(e01.changePercent)}</p>
              <span className="brief-unit">{t.client}</span>
              <h3>{t.briefImproveTitle}</h3>
              <p className="brief-explanation">{t.briefImproveText}</p>
              <div className="brief-card-actions">
                <a href="#results">{t.briefInspect}</a>
                <Source path={e01.after.evidence}>{t.evidence}</Source>
              </div>
            </article>
            <article className="brief-card regression">
              <div className="brief-card-top">
                <span>{t.briefRegressionTag}</span>
              </div>
              <p className="brief-value">{percent(e03Range.changePercent)}</p>
              <span className="brief-unit">{t.client}</span>
              <h3>{t.briefRegressionTitle}</h3>
              <p className="brief-explanation">{t.briefRegressionText}</p>
              <div className="brief-card-actions">
                <a href="#results">{t.briefInspect}</a>
                <Source path={e03Range.after.evidence}>{t.evidence}</Source>
              </div>
            </article>
            <article className="brief-card estimate">
              <div className="brief-card-top">
                <span>{t.briefHistogramTag}</span>
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
                <a href="#histogram">{t.briefInspect}</a>
                <Source path={evidence.histogram.evidence}>{t.evidence}</Source>
              </div>
            </article>
          </div>
          <p className="brief-caveat">
            {t.briefCaveat}{' '}
            <a href="#method">{t.howMeasured}</a>
          </p>
        </section>
        <section id="overview" className="section">
          <SectionHeading title={t.overviewTitle} text={t.overviewText} />
          <ol className="approach">
            {[
              [t.problemTitle, t.problemText],
              [t.approachTitle, t.approachText],
              [t.proofTitle, t.proofText],
            ].map(([title, text]) => (
              <li key={title}>
                <h3>{title}</h3>
                <p>{text}</p>
              </li>
            ))}
          </ol>
          <div id="features" className="capabilities">
            <h3>{t.featuresTitle}</h3>
            <dl className="feature-list">
              {[
                [t.f1Title, t.f1Text],
                [t.f2Title, t.f2Text],
                [t.f3Title, t.f3Text],
                [t.f4Title, t.f4Text],
                [t.f5Title, t.f5Text],
                [t.f6Title, t.f6Text],
              ].map(([title, text]) => (
                <div className="feature" key={title}>
                  <dt>{title}</dt>
                  <dd>{text}</dd>
                </div>
              ))}
            </dl>
          </div>
          <Source path="docs/portfolio-summary.md">{t.technical}</Source>
        </section>
        <section id="architecture" className="section">
          <SectionHeading title={t.architectureTitle} text={t.architectureText} />
          <figure className="architecture">
            <div className="architecture-live">
              <div className="arch-node cli-node">
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
                  <strong>{label}</strong>
                  <code>{file}</code>
                </div>
              ))}
            </div>
            <div className="portfolio-branch">
              <span>
                {t.artifact} → <code>evidence.mjs</code> → {t.website}
              </span>
              <code>portfolio/src/data/</code>
            </div>
            <figcaption>{t.diagramCaption}</figcaption>
          </figure>
          <Source path="docs/architecture.md">{t.architectureDoc}</Source>
        </section>
        <section id="results" className="section results-section">
          <SectionHeading title={t.resultsTitle} text={t.resultsText} />
          <div id="method" className="method">
            <h3>{t.methodology}</h3>
            <p>{t.caveatText}</p>
            <dl className="glossary">
              {glossaryKeys.map((key) => {
                const [term, definition] = t[key].split('|');
                return (
                  <div key={key}>
                    <dt>{term}</dt>
                    <dd>{definition}</dd>
                  </div>
                );
              })}
            </dl>
            <p className="small muted">
              {t.cursorUnavailable} {t.inference}
            </p>
          </div>
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
                <p className="small muted">{t.client} · ms · n = 10</p>
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
          <SectionHeading title={t.qualityTitle} text={t.qualityText} />
          <div className="quality-grid">
            {[
              [t.q1Title, t.q1Text],
              [t.q2Title, t.q2Text],
              [t.q3Title, t.q3Text],
            ].map(([title, text]) => (
              <article key={title}>
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
        <section id="future" className="section future-section" aria-label={t.future}>
          <details className="future">
            <summary>
              <h2>{t.futureTitle}</h2>
              <ChevronDown size={20} aria-hidden="true" />
            </summary>
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
          </details>
        </section>
        <section id="docs" className="section docs-section">
          <SectionHeading title={t.docsTitle} />
          <div className="demo-grid">
            <article className="demo-card">
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
              <h3>{t.live}</h3>
              <p>{t.liveText}</p>
              <p className="lab-tag">{t.lab}</p>
              <Source path="docs/demo.md#flow-b--live-oracle-laboratory-demonstration-rootless-podman-on-arch-linux">
                {t.guide}
              </Source>
            </article>
          </div>
          <p className="callout">
            {t.repositoryAccess}{' '}
            <a className="source-link" href={`${import.meta.env.BASE_URL}data/evidence.json`}>
              {t.provenance}
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </p>
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
      </main>
      <footer>
        <a href="#top" className="brand">
          OSPA
        </a>
        <p>{t.footer}</p>
        <Source path="THIRD_PARTY_NOTICES.md">{language === 'en' ? 'Third-party notices' : 'Avisos de terceros'}</Source>
        <a href="#top">{t.back}</a>
      </footer>
    </>
  );
}
