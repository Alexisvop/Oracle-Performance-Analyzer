"""Closed experimental index plans. DDL requires an exact operation confirmation."""
from dataclasses import dataclass
from oracle_spa.db import DiagnosticError

@dataclass(frozen=True)
class Index:
    table: str
    columns: tuple[str, ...]

INDEXES = {
    'OSPA_CUSTOMERS_EMAIL': Index('CUSTOMERS', ('EMAIL',)),
    'OSPA_ORDERS_CUSTOMER': Index('ORDERS', ('CUSTOMER_ID',)),
    'OSPA_ORDERS_CUST_DATE': Index('ORDERS', ('CUSTOMER_ID', 'ORDER_DATE')),
    'OSPA_ORDERS_DATE': Index('ORDERS', ('ORDER_DATE',)),
    'OSPA_ORDERS_STATUS_DATE': Index('ORDERS', ('STATUS', 'ORDER_DATE', 'ORDER_ID')),
}

def definitions(names):
    if isinstance(names, str) or len(set(names)) != len(names) or any(n not in INDEXES for n in names):
        raise DiagnosticError('Unknown or duplicate experimental index; operation refused.')
    return {n: INDEXES[n] for n in names}

def operation_plan(action, name):
    spec = definitions((name,))[name]
    if action not in ('create', 'drop'):
        raise DiagnosticError('Unknown index operation.')
    sql = (f'CREATE INDEX ORACLE_SPA.{name} ON ORACLE_SPA.{spec.table} ({", ".join(spec.columns)}) TABLESPACE USERS'
           if action == 'create' else f'DROP INDEX ORACLE_SPA.{name}')
    return {'action': action, 'name': name, 'sql': sql,
            'confirmation': f'ORACLE_SPA/FREEPDB1/{action.upper()}/{name}',
            'implicit_commit': True, 'rollback_restores_index': False}

def inspect_indexes(connection, names):
    """Full definition and PK exclusion checks; called by the complete schema guard."""
    specs = definitions(names)
    observed = []
    with connection.cursor() as cur:
        for name, spec in specs.items():
            cur.execute('SELECT table_owner,table_name,uniqueness,index_type,status,visibility,partitioned FROM user_indexes WHERE index_name=:name', name=name)
            if cur.fetchall() != [('ORACLE_SPA', spec.table, 'NONUNIQUE', 'NORMAL', 'VALID', 'VISIBLE', 'NO')]:
                raise DiagnosticError('Experimental index definition differs from the allowlist.')
            cur.execute('SELECT column_name,column_position,descend FROM user_ind_columns WHERE index_name=:name ORDER BY column_position', name=name)
            if cur.fetchall() != [(col, pos, 'ASC') for pos, col in enumerate(spec.columns, 1)]:
                raise DiagnosticError('Experimental index columns/order differ.')
            cur.execute('SELECT constraint_name FROM user_constraints WHERE index_name=:name', name=name)
            if cur.fetchall():
                raise DiagnosticError('Constraint indexes cannot be experimental or removed.')
            cur.execute("SELECT object_id FROM user_objects WHERE object_name=:name AND object_type='INDEX'", name=name)
            object_id = cur.fetchone()[0]
            cur.execute("SELECT SUM(bytes) FROM user_segments WHERE segment_name=:name AND segment_type='INDEX'", name=name)
            observed.append({'name': name, 'table': spec.table, 'columns': spec.columns,
                             'type': 'NORMAL', 'object_id': object_id, 'bytes': cur.fetchone()[0]})
    return observed

def apply_index(connection, action, name, confirmation, existing=(), created_object_id=None):
    """No retries/automatic cleanup after partial DDL. Drop requires creation receipt."""
    from oracle_spa.schema import inspect_schema
    plan = operation_plan(action, name)
    if confirmation != plan['confirmation']:
        raise DiagnosticError('Explicit approval required for the exact index operation.')
    definitions(existing)
    if connection.transaction_in_progress:
        raise DiagnosticError('Finish the existing transaction before implicit-commit DDL.')
    if inspect_schema(connection, existing) != 'ready':
        raise DiagnosticError('Expected complete laboratory schema.')
    if action == 'create':
        if name in existing:
            raise DiagnosticError('Index already exists; no replacement authorized.')
        after = (*existing, name)
    else:
        if name not in existing:
            raise DiagnosticError('Index is not in the authorized existing state.')
        observed = inspect_indexes(connection, (name,))[0]
        if created_object_id is None or observed['object_id'] != created_object_id:
            raise DiagnosticError('Drop requires the matching creation object ID receipt.')
        after = tuple(n for n in existing if n != name)
    with connection.cursor() as cur:
        cur.execute(plan['sql'])
    if inspect_schema(connection, after) != 'ready':
        raise DiagnosticError('Post-DDL verification failed; inspect state without retrying.')
    return {'operation': plan, 'indexes': inspect_indexes(connection, after)}
