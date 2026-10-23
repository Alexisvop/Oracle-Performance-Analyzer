"""Five bounded experiments; scenario selection never performs DDL."""
from dataclasses import dataclass
from oracle_spa.db import DiagnosticError

@dataclass(frozen=True)
class Experiment:
    id: str
    query: str
    variants: tuple[str, ...]
    scenarios: dict
    equivalent: bool
    hypothesis: str

EXPERIMENTS = {
    'email-index': Experiment('E01','Q01',('baseline',),{'baseline':(), 'email':('OSPA_CUSTOMERS_EMAIL',)},True,
        'A selective email B-tree may reduce access work; small tables may not benefit.'),
    'customer-index': Experiment('E02','Q02',('baseline',),{'baseline':(), 'simple':('OSPA_ORDERS_CUSTOMER',), 'composite':('OSPA_ORDERS_CUST_DATE',)},True,
        'Equality on customer before date range may reduce table visits; measure rather than assume.'),
    'sargability': Experiment('E03','Q07',('baseline','range'),{'baseline':(), 'date-index':('OSPA_ORDERS_DATE',)},True,
        'Separate rewrite effects under identical indexes from index-state effects.'),
    'status-skew': Experiment('E04','Q06',('baseline','rare'),{'baseline':(), 'status-histogram':(), 'histogram':()},False,
        'Different selectivity cohorts; no interchangeable-result speedup claim. Histogram stage needs separate approval.'),
    'top-n': Experiment('E05','Q08',('baseline',),{'baseline':(), 'status-date':('OSPA_ORDERS_STATUS_DATE',)},True,
        'Equality status then date/id order may avoid sorting; verify all twenty rows and tie breaks.'),
}

def get_experiment(name, scenario='baseline'):
    if name not in EXPERIMENTS or scenario not in EXPERIMENTS[name].scenarios:
        raise DiagnosticError('Unknown experiment or scenario.')
    return EXPERIMENTS[name]
