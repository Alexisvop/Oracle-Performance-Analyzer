# Experiment catalog

| ID | SQL/workload | Historical treatment |
| --- | --- | --- |
| E01 | Q01 exact email | CUSTOMERS.EMAIL B-tree |
| E02 | Q02 customer/date orders | simple CUSTOMER_ID and composite CUSTOMER_ID, ORDER_DATE B-trees, separate blocks |
| E03 | Q07 TRUNC versus sargable date range | ORDERS.ORDER_DATE B-tree |
| E04 | Q06 frequent/rare status | ORDERS.STATUS NONE -> four-bucket FREQUENCY histogram, same-cohort A/B comparison |
| E05 | Q08 deterministic Top-N | ORDERS.STATUS, ORDER_DATE, ORDER_ID B-tree |

Five experimental index objects were evaluated and removed historically. E04 used a verified backup/export/rehearsal, guarded statistics collection and a single import-recovery with exact baseline comparison. Those historical operations are not permission to repeat them. Earlier failed/STOP forensic evidence is included only where offline guard regression tests need it and is never relabeled as successful.

[Query catalog](query-catalog.md), [methodology](benchmark-methodology.md), [restoration/results](phase4-results.md), [evidence provenance](evidence/PROVENANCE.json).
