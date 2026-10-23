"""Explicit Phase 2 integration gates; never erase data without a second opt-in."""

import os
import pytest

from oracle_spa.config import Config
from oracle_spa.db import DiagnosticError, laboratory_session
from oracle_spa.data_generator import Dataset
from oracle_spa.loader import load_data
from oracle_spa.schema import RESET_CONFIRMATION, inspect_schema, reset_data
from oracle_spa.stats import gather_stats
from oracle_spa.validation import read_manifest, validate_data

pytestmark = [pytest.mark.oracle, pytest.mark.skipif(os.environ.get('OSPA_PHASE2_INTEGRATION') != '1', reason='Set OSPA_PHASE2_INTEGRATION=1 explicitly for schema/data integration')]


def test_existing_dataset_validation_stats_and_reconnect():
    with laboratory_session(Config.from_env()) as connection:
        assert inspect_schema(connection) == 'ready'
        dataset, manifest = read_manifest(connection)
        assert dataset.profile in ('tiny', 'small')
        result = load_data(connection, dataset.profile, dataset.seed)
        assert result['load'] == 'reused'
        assert result['validation']['counts'] == {t.upper(): n for t, n in dataset.counts.items()}
        different_profile = 'small' if dataset.profile == 'tiny' else 'tiny'
        with pytest.raises(DiagnosticError, match='explicit authorized reset'):
            load_data(connection, different_profile, dataset.seed)
        assert read_manifest(connection)[1] == manifest
        before = validate_data(connection)['checksums']
        assert len(gather_stats(connection)['tables']) == 4
        # Prove FK and CHECK enforcement without committing any test mutation.
        import oracledb
        with connection.cursor() as cursor:
            for sql, expected in [("INSERT INTO order_items VALUES (999999,999999,1,1,1)", 'ORA-02291'),
                                  ("INSERT INTO order_items VALUES (999999,1,1,0,1)", 'ORA-02290')]:
                with pytest.raises(oracledb.Error) as error:
                    cursor.execute(sql)
                assert error.value.args[0].full_code == expected
                connection.rollback()
    with laboratory_session(Config.from_env()) as connection:
        assert validate_data(connection)['checksums'] == before


@pytest.mark.skipif(os.environ.get('OSPA_ALLOW_DATA_RESET') != RESET_CONFIRMATION, reason='Separate owner-approved reset opt-in required')
def test_authorized_tiny_reset_reproduces_rows():
    with laboratory_session(Config.from_env()) as connection:
        dataset, before = read_manifest(connection)
        assert dataset.profile == 'tiny' and dataset.seed == 20261016
        reset_data(connection, RESET_CONFIRMATION)
        load_data(connection, 'tiny', 20261016)
        _, after = read_manifest(connection)
        assert after == before == Dataset().manifest()
