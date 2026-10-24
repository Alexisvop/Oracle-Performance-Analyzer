# Public evidence summary

## English Version

OSPA is a reproducible synthetic database performance laboratory. It combines approved SQL workloads, independent correctness checks, estimated plans, guarded index/statistics experiments, descriptive latency analysis and deterministic offline reports. The portfolio presents favorable and unfavorable observations without claiming causality. Client latency, optimizer cost and unavailable runtime metrics remain distinct.

## Versión en Español

OSPA es un laboratorio reproducible de rendimiento SQL con datos sintéticos. Integra consultas aprobadas, validación independiente de resultados, planes estimados, experimentos controlados mediante autorizaciones e informes offline. Conserva resultados favorables y desfavorables; las comparaciones descriptivas no demuestran causalidad. La latencia cliente, el costo estimado y las métricas reales no verificadas se distinguen explícitamente.

## Fast technical readout / Lectura técnica rápida

**EN:** E01 Q01 email-index experiment recorded a **53.17% lower** median client
execute + full-fetch latency. E03 Q07 date-range experiment recorded a **25.24%
higher** median with an INDEX RANGE SCAN. E04 histogram collection left the
captured estimated cardinality at **2,500** rows for the tested binds; this
is not an A-Rows/actual-cursor observation. Each claim is a descriptive Phase 4
small-profile sample result (n = 10 per state), not evidence of causality or
production performance. The [portfolio](https://oracle-performance-analyzer.pages.dev/)
now presents these three outcomes before the deep dive.

**ES:** El experimento E01 Q01 con índice de correo registró una mediana de
latencia cliente **53.17% menor**. E03 Q07 para un rango de fechas registró una
mediana **25.24% mayor** pese al INDEX RANGE SCAN. Tras el histograma E04, la
cardinalidad estimada capturada permaneció en **2,500** filas para los binds
probados; no son filas reales de operadores. Son mediciones descriptivas de
Fase 4 con el perfil pequeño (n = 10 por estado), no pruebas causales ni de
rendimiento en producción.

[Architecture](architecture.md), [results](phase4-results.md), [methodology](benchmark-methodology.md), [source queries](query-catalog.md).
