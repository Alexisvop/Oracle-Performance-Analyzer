"""Offline correctness and safety checks; no real DDL or credentials."""

from collections import Counter
from decimal import Decimal
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from oracle_spa.config import Config, ConfigError, local_environment
from oracle_spa.data_generator import Dataset, TABLES, batches, canonical, checksum
from oracle_spa.db import DiagnosticError
from oracle_spa.loader import load_data
from oracle_spa.schema import (ALL_TABLES, RESET_CONFIRMATION, assert_identity,
                               create_statements, expected_columns, init_schema,
                               inspect_schema, lock_tables, marker, reset_data)
from oracle_spa.validation import compare_rows


def test_dictionary_type_parameters_exclude_digits_in_type_names():
    columns = {(row[0], row[1]): row for row in expected_columns()}
    assert columns['CUSTOMERS', 'FULL_NAME'][3:] == ('VARCHAR2', None, None, 100, 'C', 'N')
    assert columns['OSPA_DATASET', 'MANIFEST'][6] == 4000
    assert columns['PRODUCTS', 'UNIT_PRICE'][3:6] == ('NUMBER', 12, 2)


def test_profiles_defaults_and_input_boundaries():
    sizes = [(200, 50, 1000, 3000), (2000, 500, 10000, 30000),
             (10000, 2000, 50000, 150000), (20000, 5000, 100000, 300000)]
    for profile, expected in zip(("tiny", "small", "medium", "large"), sizes):
        d = Dataset(profile)
        assert tuple(d.counts[t.lower()] for t in TABLES) == expected
        assert d.seed == 20261016
    for seed in (-1, 2**63, True, "1"):
        with pytest.raises(ConfigError):
            Dataset(seed=seed)
    with pytest.raises(ConfigError):
        Dataset("invalid")
    with pytest.raises(ConfigError):
        list(batches([], 0))


def test_tiny_integrity_distributions_and_totals():
    d = Dataset()
    customers, products, orders, items = (list(d.rows(t)) for t in TABLES)
    for table, rows in zip(TABLES, (customers, products, orders, items)):
        assert len(rows) == d.counts[table.lower()]
        assert [row[0] for row in rows] == list(range(1, len(rows) + 1))
        assert all(all(v is not None for v in row) for row in rows)
    assert all(r[2].endswith('@example.invalid') for r in customers)
    assert all(1 <= o[1] <= len(customers) and customers[o[1]-1][4] <= o[2] < d.reference for o in orders)
    totals = Counter()
    for item in items:
        assert 1 <= item[1] <= len(orders) and 1 <= item[2] <= len(products)
        assert item[3] > 0 and item[4] > 0
        totals[item[1]] += item[3] * item[4]
    assert all(o[4] == totals[o[0]] for o in orders)
    regions = Counter(c[3] for c in customers)
    assert set(regions) == {'NORTH', 'SOUTH', 'EAST', 'WEST', 'CENTRAL'}
    assert all(20 <= n <= 60 for n in regions.values())
    statuses = Counter(o[3] for o in orders)
    assert statuses['PAID'] > statuses['SHIPPED'] > statuses['CANCELLED']
    assert sum(o[1] <= 20 for o in orders) > 700
    assert Counter(p[1] for p in products)['BOOKS'] > 15


def test_seed_batch_size_and_stream_determinism():
    a, b, changed = Dataset(), Dataset(), Dataset(seed=42)
    assert a.manifest() == b.manifest()
    assert a.manifest()['checksums'] != changed.manifest()['checksums']
    for table in TABLES:
        flattened = (r for batch in batches(a.rows(table), 17) for r in batch)
        assert checksum(flattened) == checksum(b.rows(table))
    assert canonical((Decimal('1.20'), 1)) == canonical((1.2, Decimal('1.0')))
    with pytest.raises(DiagnosticError):
        compare_rows([(1, 'a')], [(1, 'b')])
    with pytest.raises(DiagnosticError):
        compare_rows([], [(1,)])


def test_versioned_ddl_matches_contract():
    from oracle_spa.data_generator import ROOT
    assert (ROOT/'sql/01_schema.sql').read_text() == ';\n\n'.join(create_statements()) + ';\n'
    assert all('DROP' not in s and 'TRUNCATE' not in s for s in create_statements())
    assert len(expected_columns()) == 25


def test_schema_identity_and_unknown_objects_stop_before_ddl():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ('SYSTEM', 'FREEPDB1', 'SYSTEM')
    with pytest.raises(DiagnosticError):
        init_schema(connection)
    assert cursor.execute.call_count == 1
    cursor.fetchone.return_value = ('ORACLE_SPA', 'FREEPDB1', 'ORACLE_SPA')
    cursor.fetchall.return_value = [('FOREIGN_DATA', 'TABLE', 'VALID')]
    with pytest.raises(DiagnosticError, match='unrecognized'):
        inspect_schema(connection)
    assert not any(c.args[0].startswith(('CREATE', 'DELETE')) for c in cursor.execute.call_args_list)


def test_init_schema_requires_privilege_and_complete_marker():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [('CREATE SESSION',)]
    with patch('oracle_spa.schema.inspect_schema', return_value='empty'), pytest.raises(DiagnosticError, match='CREATE TABLE'):
        init_schema(connection)
    assert cursor.execute.call_count == 1
    with patch('oracle_spa.schema.inspect_schema', return_value='ready'):
        assert init_schema(connection)['schema'] == 'reused'


def test_reset_requires_confirmation_and_schema_gate():
    connection = MagicMock()
    with pytest.raises(DiagnosticError, match='confirm'):
        reset_data(connection)
    connection.cursor.assert_not_called()
    with patch('oracle_spa.schema.inspect_schema', side_effect=DiagnosticError('unsafe')), pytest.raises(DiagnosticError):
        reset_data(connection, RESET_CONFIRMATION)
    connection.commit.assert_not_called()


def test_reset_rolls_back_failure_and_only_deletes_allowlisted_rows():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    with patch('oracle_spa.schema.lock_tables'):
        result = reset_data(connection, RESET_CONFIRMATION)
    statements = [call.args[0] for call in cursor.execute.call_args_list]
    assert statements == [f'DELETE FROM {t}' for t in ('ORDER_ITEMS', 'ORDERS', 'PRODUCTS', 'CUSTOMERS', 'OSPA_DATASET')]
    assert result['ddl_used'] is False
    connection.commit.assert_called_once()
    connection.reset_mock()
    cursor.execute.side_effect = RuntimeError('synthetic failure')
    with patch('oracle_spa.schema.lock_tables'), pytest.raises(RuntimeError):
        reset_data(connection, RESET_CONFIRMATION)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_load_refuses_nonempty_unknown_data_and_rolls_back():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1,)
    with patch('oracle_spa.loader.lock_tables'), patch('oracle_spa.loader.read_manifest', side_effect=DiagnosticError('partial')), pytest.raises(DiagnosticError):
        load_data(connection)
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    cursor.executemany.assert_not_called()


def test_load_validation_failure_rolls_back_all_batches():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (0,)
    with patch('oracle_spa.loader.lock_tables'), patch('oracle_spa.loader.validate_data', side_effect=DiagnosticError('invalid')), pytest.raises(DiagnosticError):
        load_data(connection)
    assert cursor.executemany.call_count > 4
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_local_env_preserves_existing_values_and_literal_password(tmp_path):
    p = tmp_path/'.env'
    p.write_text('ORACLE_DSN=localhost:1521/FREEPDB1\nORACLE_USER=ORACLE_SPA\nORACLE_PASSWORD= synthetic #=$ value \n')
    p.chmod(0o600)
    with patch('oracle_spa.config.PROJECT_ROOT', tmp_path), patch.dict('os.environ', {'ORACLE_USER': 'oracle_spa'}, clear=True):
        c = Config.from_env()
        assert c.user == 'ORACLE_SPA' and c.password == ' synthetic #=$ value '
        assert local_environment()['ORACLE_USER'] == 'oracle_spa'
    p.chmod(0o644)
    with patch('oracle_spa.config.PROJECT_ROOT', tmp_path), patch.dict('os.environ', {}, clear=True), pytest.raises(ConfigError):
        Config.from_env()


def test_local_env_symlink_duplicate_and_unknown_keys_are_rejected(tmp_path):
    elsewhere = tmp_path/'private'
    elsewhere.write_text('not read')
    p = tmp_path/'.env'
    p.symlink_to(elsewhere)
    with patch('oracle_spa.config.PROJECT_ROOT', tmp_path), patch.dict('os.environ', {}, clear=True), pytest.raises(ConfigError):
        Config.from_env()
    p.unlink()
    for content in ('ORACLE_PASSWORD=synthetic\nORACLE_PASSWORD=duplicate', 'UNSUPPORTED=synthetic'):
        p.write_text(content); p.chmod(0o600)
        with patch('oracle_spa.config.PROJECT_ROOT', tmp_path), patch.dict('os.environ', {}, clear=True), pytest.raises(ConfigError) as error:
            Config.from_env()
        assert 'synthetic' not in str(error.value)


def test_explicit_config_does_not_read_local_file():
    with patch('oracle_spa.config.local_environment', side_effect=AssertionError('must not read')):
        assert Config.from_env({'ORACLE_DSN': 'localhost:1521/FREEPDB1', 'ORACLE_USER': 'ORACLE_SPA', 'ORACLE_PASSWORD': 'synthetic'}).user == 'ORACLE_SPA'


def schema_fixture():
    from oracle_spa.schema import CHECKS, COLUMNS, FOREIGN_KEYS
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ('ORACLE_SPA', 'FREEPDB1', 'ORACLE_SPA')
    constraints, cons_columns = [], []
    def add(table, name, kind, cols, condition=None, owner=None, parent=None, rule=None, generated='USER NAME'):
        constraints.append((table, name, kind, 'ENABLED', 'VALIDATED', owner, parent, rule,
                            condition, generated, 'NOT DEFERRABLE', 'IMMEDIATE'))
        cons_columns.extend((name, c) for c in cols)
    for table in ALL_TABLES:
        add(table, table+'_PK', 'P', [COLUMNS[table][0][0]])
        for col, _ in COLUMNS[table]:
            add(table, table+'_'+col+'_NN', 'C', [col], f'"{col}" IS NOT NULL', generated='GENERATED NAME')
        for name, condition in CHECKS[table].items():
            add(table, name, 'C', [], condition)
        for name, col, parent in FOREIGN_KEYS.get(table, []):
            add(table, name, 'R', [col], owner='ORACLE_SPA', parent=parent+'_PK', rule='NO ACTION')
    replies = [[(t, 'TABLE', 'VALID') for t in ALL_TABLES] + [(t+'_PK', 'INDEX', 'VALID') for t in ALL_TABLES],
               [(t, marker()) for t in ALL_TABLES], expected_columns(), constraints, cons_columns,
               [(t+'_PK', t, 'UNIQUE', 'NORMAL') for t in ALL_TABLES]]
    cursor.fetchall.side_effect = replies
    return connection, replies


def test_exact_schema_contract_and_altered_constraint_rejection():
    connection, _ = schema_fixture()
    assert inspect_schema(connection) == 'ready'
    for index in (0, 1, 2, 3, 5):
        connection, replies = schema_fixture()
        replies[index].pop()
        with pytest.raises(DiagnosticError):
            inspect_schema(connection)
    connection, replies = schema_fixture()
    # An extra disabled constraint cannot hide behind valid object names/comments.
    row = list(replies[3][0]); row[3] = 'DISABLED'; replies[3][0] = tuple(row)
    with pytest.raises(DiagnosticError):
        inspect_schema(connection)


def test_lock_rechecks_after_acquiring_all_tables():
    connection = MagicMock()
    with patch('oracle_spa.schema.inspect_schema', side_effect=['ready', DiagnosticError('changed')]) as inspect:
        with pytest.raises(DiagnosticError):
            lock_tables(connection)
    assert inspect.call_count == 2
    assert connection.cursor.return_value.__enter__.return_value.execute.call_count == 5


def test_bad_dataset_config_is_rejected(tmp_path):
    from oracle_spa.data_generator import settings
    (tmp_path/'config').mkdir()
    p=tmp_path/'config/datasets.json'
    for content in ('{}', '{broken', json.dumps({'version': 1})):
        p.write_text(content)
        with patch('oracle_spa.data_generator.ROOT', tmp_path), pytest.raises(ConfigError):
            settings()


def test_cli_phase2_rejects_unsafe_reset_and_redacts_driver_errors():
    from contextlib import redirect_stderr, redirect_stdout
    from oracle_spa.cli import main
    import contextlib
    @contextlib.contextmanager
    def session(config):
        yield MagicMock()
    output=io.StringIO()
    with patch('oracle_spa.cli.Config.from_env'), patch('oracle_spa.cli.laboratory_session', session), redirect_stdout(output), redirect_stderr(output):
        assert main(['reset-data', '--confirm', 'wrong']) == 1
    assert 'Affected ORACLE_SPA tables' in output.getvalue()
    assert 'requires --confirm' in output.getvalue()


def test_same_seed_fresh_process_matches():
    import os
    import subprocess
    import sys
    snippet="from oracle_spa.data_generator import Dataset; import json; print(json.dumps(Dataset().manifest(),sort_keys=True))"
    output=subprocess.check_output([sys.executable, '-c', snippet], text=True,
                                   env=os.environ | {'PYTHONHASHSEED': '99'})
    assert json.loads(output) == Dataset().manifest()
