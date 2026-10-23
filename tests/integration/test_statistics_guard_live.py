"""Real, read-only reconciliation and guards; no creation/export/import rehearsal."""
import os
import pytest
from oracle_spa.config import Config
from oracle_spa.db import DiagnosticError,laboratory_session
from oracle_spa.schema import inspect_schema
from oracle_spa.statistics_backup import BackupPermit,digest,inspect_original,prepare_operation,query,validate_backup

pytestmark=[pytest.mark.oracle,pytest.mark.skipif(os.environ.get('OSPA_BACKUP_INSPECTION')!='1',reason='Explicit read-only backup inspection required')]


def test_real_backup_reconciliation_is_read_only_and_mutations_remain_blocked(backup_reconciliation):
    permit=BackupPermit(**backup_reconciliation['permit_proposal'])
    with laboratory_session(Config.from_env()) as c:
        with pytest.raises(DiagnosticError):inspect_schema(c)
        assert inspect_schema(c,backup_permit=permit)=='ready'
        observed=inspect_original(c,permit)
        assert observed['effective']['dataset']['profile']=='small'
        assert observed['effective']['dataset']['seed']==20261016
        assert digest(observed['effective']['statistics'])=='6f27e295160307428e1deff18e1dfacdb9cd86c244a9c92f1b3a7e4551d1280d'
        count=query(c,'SELECT COUNT(*) FROM ospa_orders_stats_bak')['rows'][0][0]['oracle_number']
        if 'export_receipt' in backup_reconciliation:
            contents=validate_backup(c,permit,backup_reconciliation['export_receipt'])
            assert int(count)==len(contents['rows'])>0
            position=contents['columns'].index('STATID')
            assert {row[position] for row in contents['rows']}=={'B_ORIGINAL_V1'}
        else:
            assert count=='0'
        # The export-only audit does not run import/recovery tests.
        operations=('export',) if 'export_receipt' in backup_reconciliation else ('export','import-rehearsal','import-recovery')
        for operation in operations:
            with pytest.raises(DiagnosticError,match='external approval'):
                prepare_operation(c,operation,observed,permit)
        assert inspect_original(c,permit)==observed
        assert backup_reconciliation['reconciliation']['original_journal'][-1]['status']=='STOP; POSSIBLE PARTIAL EFFECTS'
