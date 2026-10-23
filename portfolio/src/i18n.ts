export type Language = 'en' | 'es';
const en = {
  skip: 'Skip to content',
  menu: 'Toggle navigation',
  language: 'Language / Idioma',
  overview: 'Overview',
  architecture: 'Architecture',
  features: 'Capabilities',
  results: 'Results',
  quality: 'Reproducibility',
  docs: 'Documentation',
  future: 'Future work',
  eyebrow: 'DATABASE PERFORMANCE ENGINEERING',
  subtitle: 'A Reproducible Database Performance Engineering Laboratory',
  heroText:
    'From SQL hypotheses to verifiable evidence. Explore execution plans, B-tree indexes, optimizer statistics, and measured trade-offs on Oracle Database.',
  explore: 'Explore Results',
  source: 'View Source Code',
  technical: 'Technical Documentation',
  lab: 'Independent engineering project',
  evidence: 'Evidence',
  client: 'Median end-to-end client latency',
  synthetic: 'synthetic business rows',
  queries: 'parameterized SQL queries',
  tests: 'offline unit tests',
  experimental: 'experimental indexes evaluated',
  heroNote:
    'One small dataset. Real Oracle experiments. Favorable and unfavorable results preserved.',
  observation: 'OBSERVED · E01 / Q01',
  lower: 'lower median client latency',
  baseline: 'Baseline',
  indexed: 'With index',
  heroCaveat: '10 measured repetitions per state · descriptive observation, not causal proof.',
  overviewTitle: 'Performance claims need a chain of evidence.',
  overviewText:
    'A faster-looking plan is only the beginning. SQL tuning needs correct results, controlled experiments, and measurements that another engineer can inspect.',
  problemTitle: 'The engineering problem',
  problemText:
    'Indexes, predicate shape, and skewed data can change access paths. Lower optimizer cost does not guarantee lower client latency.',
  approachTitle: 'The approach',
  approachText:
    'Generate a seeded e-commerce dataset, verify full query results against Python ground truth, capture estimated plans, and measure execute + complete fetch.',
  proofTitle: 'The verification strategy',
  proofText:
    'Preserve raw samples and receipts, compare equivalent results, verify restoration, and regenerate analytical reports offline from committed evidence.',
  architectureTitle: 'A laboratory with an offline evidence pipeline.',
  architectureText:
    'The Python CLI orchestrates the Oracle laboratory. A separate reporting path consumes historical evidence. This website only displays curated public data.',
  cli: 'Python CLI',
  dataEngine: 'Dataset generation + validation',
  workload: 'SQL catalog + result verification',
  planEngine: 'Estimated plan inspection',
  benchmark: 'Guarded benchmark engine',
  database: 'Oracle AI Database Free',
  artifact: 'Versioned JSON evidence',
  analysis: 'Statistical analysis + reports',
  ci: 'GitHub Actions · offline verification',
  website: 'Static portfolio · curated data',
  diagramCaption:
    'CLI → data/workload/plan/benchmark modules → Oracle. Benchmark runs → evidence → analysis/report generation → offline CI verification. Evidence also supplies this static portfolio.',
  featuresTitle: 'Built to make the experiment defensible.',
  f1Title: 'Deterministic workloads',
  f1Text: 'Seeded synthetic data, a fixed reference date, and full table SHA-256 checksums.',
  f2Title: 'Correctness before timing',
  f2Text:
    'Ordered row checks and disk-backed multiset validation against an independent Python result oracle.',
  f3Title: 'Estimated plan inspection',
  f3Text: 'EXPLAIN PLAN and DBMS_XPLAN.DISPLAY with operator trees, costs, and estimated rows.',
  f4Title: 'Guarded experiments',
  f4Text:
    'Allowlisted objects, explicit permits, identity checks, and OBJECT_ID receipts for index removal.',
  f5Title: 'Honest statistics',
  f5Text: 'Warmups separated from measurements. Median, IQR, and p95 retain every measured sample.',
  f6Title: 'Offline reports',
  f6Text: 'CSV, JSON, Markdown, charts, and provenance manifests regenerated without Oracle.',
  resultsTitle: 'An index is a hypothesis. Measure the outcome.',
  resultsText:
    'Phase 4 · small profile · seed 20261016 · 5 warmups + 10 measured repetitions per variant and state.',
  methodology: 'Measurement scope',
  caveatText:
    'All times include client execute + complete fetch over loopback, driver decoding, and Python row collection. Index states ran in sequential blocks. Cache, order, and host-load confounders remain. These observations are descriptive; they are not universal gains or server CPU measurements.',
  groupA: 'Index experiments',
  stageA: 'Baseline explorer',
  storage: 'Storage trade-offs',
  indexCaption: 'Group A · contemporaneous baseline vs. indexed state',
  baselineCaption: 'Stage A · different workloads, shown for context only',
  baselineNote:
    'Q03–Q05 have no timed Phase 4 benchmarks. PAID and CANCELLED return different rows and must not be ranked as equivalent workloads.',
  storageCaption: 'Allocated index storage vs. change in median client latency',
  storageNote:
    'Each point is one query variant. E03 shares one 256 KiB index across two variants; do not add its size twice. DML overhead was not measured.',
  storageAxis: 'Allocated storage (KiB)',
  changeAxis: 'Median latency change (%) · lower is favorable',
  experiment: 'Experiment / variant',
  median: 'Median',
  iqr: 'IQR',
  p95: 'p95',
  rows: 'Rows',
  delta: 'Change',
  size: 'Storage',
  details: 'Inspect plans and provenance',
  estimated: 'Captured estimated plan',
  cursorUnavailable:
    'Runtime cursor metrics: NOT VERIFIED (Group C deferred). Cost is an optimizer estimate, not milliseconds.',
  selected: 'Index selected in estimated plan',
  ignored: 'Index not selected in estimated plan',
  interpretation: 'Interpretation',
  inference:
    'Possible explanations are hypotheses; runtime buffers and server CPU were not observed.',
  emailInsight:
    'E01 and E02: selective lookups used index range scans and had lower observed medians.',
  dateInsight:
    'E03 range: the estimated plan selected the date index, but median latency rose. Small-table access overhead is a plausible explanation, not a measured cause.',
  topInsight:
    'E03 TRUNC retained a full scan. E05 also retained a full scan and STOPKEY sort; its SQL has no STATUS filter matching the index leading column.',
  histogramTitle: 'E04 / A histogram changed statistics. The estimated plan stayed the same.',
  histogramText:
    'ORDERS.STATUS moved from NONE to a 4-bucket FREQUENCY histogram. Captured EXPLAIN PLAN trees still estimated 2,500 rows for both binds. This is consistent with unpeeked binds; runtime bind peeking was not inspected.',
  statusCaption: 'Observed ORDERS.STATUS distribution · 10,000 rows',
  cohortCaption: 'Same-cohort client latency · A: NONE → B: FREQUENCY',
  cohortNote:
    'Compare PAID A with PAID B, and CANCELLED A with CANCELLED B. Cross-cohort comparisons are NOT COMPARABLE. Each state has n = 10 per cohort.',
  restoration:
    'Historical recovery verified identical baseline statistics (SHA-256 match; MAXDIFFPCT = 0). No recovery or database operation runs on this website.',
  qualityTitle: 'Reproducibility is part of the result.',
  qualityText:
    'The latest Phase 5 Stage D record reports 180 unit tests and 55 subtests passed. The last recorded live suite in Stage A passed 4 Oracle integration tests; they do not run in offline CI.',
  q1Title: 'Evidence you can trace',
  q1Text:
    'The Phase 5 report pipeline validates 40 input files and 12 output artifacts with SHA-256 manifests. This site has its own curated source hashes.',
  q2Title: 'CI without a database',
  q2Text:
    'GitHub Actions runs Python unit tests, regenerates reports twice, and checks deterministic output. No Oracle credentials or integration database are required.',
  q3Title: 'Safety by design',
  q3Text:
    'Least-privilege Oracle user, closed SQL catalog, secret redaction, single-use mutation permits, and verified object/statistics restoration in historical experiments.',
  provenance: 'View curated data and source hashes',
  historical: 'Historical verification; not a new live Oracle test.',
  docsTitle: 'Read the evidence. Reproduce the analysis.',
  repositoryAccess:
    'Reviewed documentation, source files and benchmark evidence are available locally. The future public repository URL is pending.',
  offline: '01 / Offline demonstration',
  offlineText:
    'Run unit tests and regenerate historical reports from the repository. No Oracle, container, or credentials required.',
  live: '02 / Oracle laboratory',
  liveText:
    'Explore the documented Oracle-backed workflow in an isolated laboratory. Changes to a preserved database require fresh owner authorization.',
  guide: 'Open demonstration guide',
  architectureDoc: 'Architecture reference',
  reproducibilityDoc: 'Reproducibility guide',
  findingsDoc: 'Engineering findings',
  futureTitle: 'The next questions are clearly marked.',
  futureBadge: 'Not Implemented / Future Work',
  future1: 'Group C · Runtime cursor metrics',
  future1Text:
    'Inspect A-Rows, Starts, and Buffers through DBMS_XPLAN.DISPLAY_CURSOR after separately approved fixed-view access.',
  future2: 'Bind peeking inspection',
  future2Text: 'Inspect child cursors and bind-sensitive plans for skewed predicates.',
  future3: 'Advanced optimizer diagnostics',
  future3Text:
    'Investigate Adaptive Cursor Sharing and estimates against observed operator metrics.',
  future4: 'Multi-scale experiments',
  future4Text:
    'Evaluate larger profiles, multiple seeds, and stronger cache/order controls. Current measurements cover small only.',
  footer:
    'Independent educational engineering project. Not affiliated with or certified by Oracle.',
  back: 'Back to top',
};
export type Copy = { [K in keyof typeof en]: string };
const es: Copy = {
  skip: 'Saltar al contenido',
  menu: 'Alternar navegación',
  language: 'Language / Idioma',
  overview: 'Proyecto',
  architecture: 'Arquitectura',
  features: 'Capacidades',
  results: 'Resultados',
  quality: 'Reproducibilidad',
  docs: 'Documentación',
  future: 'Trabajo futuro',
  eyebrow: 'INGENIERÍA DE RENDIMIENTO DE BASES DE DATOS',
  subtitle: 'Un laboratorio reproducible de ingeniería de rendimiento de bases de datos',
  heroText:
    'De hipótesis SQL a evidencia verificable. Explora planes de ejecución, índices B-tree, estadísticas del optimizador y compromisos medidos en Oracle Database.',
  explore: 'Explorar resultados',
  source: 'Ver código fuente',
  technical: 'Documentación técnica',
  lab: 'Proyecto independiente de ingeniería',
  evidence: 'Evidencia',
  client: 'Mediana de latencia de extremo a extremo del cliente',
  synthetic: 'filas sintéticas de negocio',
  queries: 'consultas SQL parametrizadas',
  tests: 'pruebas unitarias sin Oracle',
  experimental: 'índices experimentales evaluados',
  heroNote:
    'Un conjunto pequeño de datos. Experimentos reales en Oracle. Resultados favorables y desfavorables preservados.',
  observation: 'OBSERVADO · E01 / Q01',
  lower: 'menos latencia mediana del cliente',
  baseline: 'Base',
  indexed: 'Con índice',
  heroCaveat: '10 repeticiones medidas por estado · observación descriptiva, sin prueba causal.',
  overviewTitle: 'Afirmar rendimiento exige una cadena de evidencia.',
  overviewText:
    'Un plan que parece más rápido es solo el comienzo. Optimizar SQL exige resultados correctos, experimentos controlados y mediciones que otro ingeniero pueda revisar.',
  problemTitle: 'El problema de ingeniería',
  problemText:
    'Los índices, la forma del predicado y el sesgo de los datos pueden cambiar las rutas de acceso. Un menor costo del optimizador no garantiza menor latencia del cliente.',
  approachTitle: 'El enfoque',
  approachText:
    'Generar datos de comercio electrónico con semilla, verificar los resultados completos contra un oráculo Python, capturar planes estimados y medir ejecución más recuperación completa.',
  proofTitle: 'La estrategia de verificación',
  proofText:
    'Preservar muestras y recibos, comparar resultados equivalentes, verificar restauración y regenerar reportes sin Oracle desde evidencia versionada.',
  architectureTitle: 'Un laboratorio con un flujo de evidencia sin Oracle.',
  architectureText:
    'La CLI Python coordina el laboratorio Oracle. Una ruta separada de reportes consume evidencia histórica. Este sitio solo presenta datos públicos seleccionados.',
  cli: 'CLI Python',
  dataEngine: 'Generación y validación de datos',
  workload: 'Catálogo SQL y verificación de resultados',
  planEngine: 'Inspección de planes estimados',
  benchmark: 'Motor de medición con controles',
  database: 'Oracle AI Database Free',
  artifact: 'Evidencia JSON versionada',
  analysis: 'Análisis estadístico y reportes',
  ci: 'GitHub Actions · verificación sin Oracle',
  website: 'Portafolio estático · datos seleccionados',
  diagramCaption:
    'CLI → módulos de datos/consultas/planes/medición → Oracle. Mediciones → evidencia → análisis/reportes → verificación CI sin Oracle. La evidencia también alimenta este portafolio estático.',
  featuresTitle: 'Diseñado para sostener cada experimento.',
  f1Title: 'Cargas deterministas',
  f1Text: 'Datos sintéticos con semilla, fecha de referencia fija y SHA-256 completos por tabla.',
  f2Title: 'Correctitud antes de medir',
  f2Text:
    'Comparación de filas ordenadas y multiconjuntos en disco contra un oráculo independiente en Python.',
  f3Title: 'Inspección de planes estimados',
  f3Text: 'EXPLAIN PLAN y DBMS_XPLAN.DISPLAY con árboles de operadores, costos y filas estimadas.',
  f4Title: 'Experimentos con controles',
  f4Text:
    'Objetos permitidos, permisos explícitos, verificación de identidad y recibos OBJECT_ID para eliminar índices.',
  f5Title: 'Estadística honesta',
  f5Text:
    'Calentamientos separados de mediciones. Mediana, IQR y p95 conservan todas las muestras medidas.',
  f6Title: 'Reportes sin Oracle',
  f6Text: 'CSV, JSON, Markdown, gráficas y manifiestos de procedencia regenerados sin Oracle.',
  resultsTitle: 'Un índice es una hipótesis. Mide el resultado.',
  resultsText:
    'Fase 4 · perfil small · semilla 20261016 · 5 calentamientos + 10 repeticiones medidas por variante y estado.',
  methodology: 'Alcance de la medición',
  caveatText:
    'Los tiempos incluyen ejecución y recuperación completa del cliente por loopback, decodificación del driver y materialización de filas en Python. Los estados de índices se midieron en bloques secuenciales. Persisten factores de caché, orden y carga del equipo. Son observaciones descriptivas; no son mejoras universales ni mediciones de CPU del servidor.',
  groupA: 'Experimentos de índices',
  stageA: 'Explorar bases',
  storage: 'Costo de almacenamiento',
  indexCaption: 'Grupo A · base contemporánea frente al estado con índice',
  baselineCaption: 'Etapa A · cargas diferentes, mostradas solo como contexto',
  baselineNote:
    'Q03–Q05 no tienen mediciones de tiempo en la Fase 4. PAID y CANCELLED devuelven filas distintas y no deben clasificarse como cargas equivalentes.',
  storageCaption:
    'Almacenamiento asignado al índice frente al cambio de latencia mediana del cliente',
  storageNote:
    'Cada punto representa una variante. E03 comparte un índice de 256 KiB entre dos variantes; no sumes su tamaño dos veces. No se midió sobrecarga DML.',
  storageAxis: 'Almacenamiento asignado (KiB)',
  changeAxis: 'Cambio de latencia mediana (%) · menor es favorable',
  experiment: 'Experimento / variante',
  median: 'Mediana',
  iqr: 'IQR',
  p95: 'p95',
  rows: 'Filas',
  delta: 'Cambio',
  size: 'Espacio',
  details: 'Inspeccionar planes y procedencia',
  estimated: 'Plan estimado capturado',
  cursorUnavailable:
    'Métricas de cursores en ejecución: NOT VERIFIED (Grupo C diferido). El costo es una estimación del optimizador, no milisegundos.',
  selected: 'Índice elegido en el plan estimado',
  ignored: 'Índice no elegido en el plan estimado',
  interpretation: 'Interpretación',
  inference:
    'Las posibles explicaciones son hipótesis; no se observaron buffers en ejecución ni CPU del servidor.',
  emailInsight:
    'E01 y E02: las búsquedas selectivas usaron recorridos de rango de índice y mostraron medianas menores.',
  dateInsight:
    'E03 range: el plan estimado eligió el índice de fecha, pero la latencia mediana aumentó. La sobrecarga de acceso en tablas pequeñas es una explicación posible, no una causa medida.',
  topInsight:
    'E03 TRUNC conservó un recorrido completo. E05 también conservó el recorrido completo y ordenamiento STOPKEY; su SQL no filtra STATUS, primera columna del índice.',
  histogramTitle: 'E04 / El histograma cambió las estadísticas. El plan estimado siguió igual.',
  histogramText:
    'ORDERS.STATUS pasó de NONE a un histograma FREQUENCY de 4 grupos. Los árboles EXPLAIN PLAN capturados siguieron estimando 2,500 filas para ambos binds. Es consistente con binds no inspeccionados; no se inspeccionó bind peeking en ejecución.',
  statusCaption: 'Distribución observada de ORDERS.STATUS · 10,000 filas',
  cohortCaption: 'Latencia del cliente por cohorte · A: NONE → B: FREQUENCY',
  cohortNote:
    'Compara PAID A con PAID B y CANCELLED A con CANCELLED B. Las comparaciones entre cohortes son NOT COMPARABLE. Cada estado tiene n = 10 por cohorte.',
  restoration:
    'La recuperación histórica verificó estadísticas base idénticas (SHA-256 coincidente; MAXDIFFPCT = 0). Este sitio no ejecuta recuperación ni operaciones de base de datos.',
  qualityTitle: 'La reproducibilidad forma parte del resultado.',
  qualityText:
    'El último registro de la Fase 5 Etapa D reporta 180 pruebas unitarias y 55 subpruebas aprobadas. La última suite en vivo registrada en la Etapa A aprobó 4 pruebas de integración Oracle; no se ejecutan en el CI sin Oracle.',
  q1Title: 'Evidencia rastreable',
  q1Text:
    'El flujo de reportes de la Fase 5 valida 40 archivos de entrada y 12 artefactos de salida con manifiestos SHA-256. Este sitio tiene sus propios hashes de fuentes seleccionadas.',
  q2Title: 'CI sin base de datos',
  q2Text:
    'GitHub Actions ejecuta pruebas unitarias Python, regenera reportes dos veces y verifica salidas deterministas. No requiere credenciales ni base Oracle de integración.',
  q3Title: 'Seguridad desde el diseño',
  q3Text:
    'Usuario Oracle con privilegios mínimos, catálogo SQL cerrado, ocultamiento de secretos, permisos de mutación de un solo uso y restauración verificada en experimentos históricos.',
  provenance: 'Ver datos seleccionados y hashes de fuentes',
  historical: 'Verificación histórica; no es una nueva prueba Oracle en vivo.',
  docsTitle: 'Lee la evidencia. Reproduce el análisis.',
  repositoryAccess:
    'La documentación, los archivos fuente y la evidencia revisados están disponibles localmente. La URL del futuro repositorio público está pendiente.',
  offline: '01 / Demostración sin Oracle',
  offlineText:
    'Ejecuta pruebas unitarias y regenera reportes históricos desde el repositorio. Sin Oracle, contenedores ni credenciales.',
  live: '02 / Laboratorio Oracle',
  liveText:
    'Explora el flujo documentado con Oracle en un laboratorio aislado. Modificar una base preservada requiere nueva autorización del propietario.',
  guide: 'Abrir guía de demostración',
  architectureDoc: 'Referencia de arquitectura',
  reproducibilityDoc: 'Guía de reproducibilidad',
  findingsDoc: 'Hallazgos de ingeniería',
  futureTitle: 'Las siguientes preguntas están claramente marcadas.',
  futureBadge: 'No implementado / Trabajo futuro',
  future1: 'Grupo C · Métricas de cursores en ejecución',
  future1Text:
    'Inspeccionar A-Rows, Starts y Buffers mediante DBMS_XPLAN.DISPLAY_CURSOR tras aprobar acceso específico a vistas fijas.',
  future2: 'Inspección de bind peeking',
  future2Text: 'Inspeccionar cursores hijos y planes sensibles a binds en predicados sesgados.',
  future3: 'Diagnóstico avanzado del optimizador',
  future3Text:
    'Investigar Adaptive Cursor Sharing y estimaciones frente a métricas observadas de operadores.',
  future4: 'Experimentos a distintas escalas',
  future4Text:
    'Evaluar perfiles mayores, varias semillas y controles más sólidos de caché y orden. Las mediciones actuales cubren solo small.',
  footer:
    'Proyecto independiente educativo de ingeniería. Sin afiliación ni certificación de Oracle.',
  back: 'Volver al inicio',
};
export const translations: Record<Language, Copy> = { en, es };
