# Architecture

## Online laboratory path

Python cli.py dispatches diagnostics, dataset/schema validation, approved query execution and guarded experiments. config.py/db.py validate secure configuration and identity; data_generator.py/loader.py/validation.py provide deterministic data and independent expectations; queries.py/execution.py own catalog correctness; plans.py captures estimated plans. benchmark.py, indexes.py and statistics_experiment.py orchestrate explicitly authorized experiments. statistics_backup.py verifies backup structure/provenance and exact recovery.

No online operation was executed for public-edition preparation.

## Offline path

Public historical JSON -> analysis.py + phase5_report.py -> deterministic JSON/CSV/Markdown/SVG/PNG reports. The report-all flow never connects to Oracle. Public evidence retains 17 final benchmark runs / 345 samples: 115 warmups and 230 measured repetitions, 23 variant/state measurements.

Public historical JSON -> portfolio/scripts/evidence.mjs -> typed curated JSON -> React EN/ES -> Vite static assets. The build also emits a strictly allowlisted local source/documentation browser and third-party notices. It reads no ignored results or private repository input. There is no backend, tracker, font CDN or database connection.

[Modules and reproduction](development.md), [evidence](evidence/README.md), [SQL catalog](query-catalog.md), [experiments](experiments.md).
