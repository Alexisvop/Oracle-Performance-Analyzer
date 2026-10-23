"""Explicit read-only backup inspection; never approves a statistics mutation."""
import os
import json
from hashlib import sha256
from pathlib import Path
import pytest
from oracle_spa.config import Config
from oracle_spa.db import laboratory_session
from oracle_spa.statistics_backup import BackupPermit,reconcile_existing,validate_backup


@pytest.fixture(scope='session')
def backup_reconciliation():
    pin=os.environ.get('OSPA_BACKUP_REVIEWED_MANIFEST_SHA256')
    if os.environ.get('OSPA_BACKUP_INSPECTION')!='1' or not pin:
        pytest.fail('Backup inspection requires explicit opt-in and a reviewed manifest hash.')
    export_receipt=os.environ.get('OSPA_BACKUP_EXPORT_RECEIPT')
    if export_receipt:
        # A populated backup cannot rerun the empty-table reconciliation.
        # Reuse the explicitly pinned, previously reviewed inspection proposal.
        proposal_bytes=Path('docs/evidence/phase4/group-b-guard-repair/backup-permit-proposal.json').read_bytes()
        if sha256(proposal_bytes).hexdigest()!=os.environ.get('OSPA_BACKUP_REVIEWED_PROPOSAL_SHA256'):
            pytest.fail('Previously reviewed backup proposal changed.')
        proposal=json.loads(proposal_bytes)
        receipt=json.loads(Path(export_receipt).read_text())
        with laboratory_session(Config.from_env()) as c:
            validate_backup(c,BackupPermit(**proposal),receipt)
        result={'reconciliation':proposal['creation_receipt'],'permit_proposal':proposal,'export_receipt':receipt}
    else:
        with laboratory_session(Config.from_env()) as c:
            result=reconcile_existing(c,'docs/evidence/phase4/group-b-create-stat-table',reviewed_manifest_sha256=pin)
    assert result['permit_proposal']['statistics_approval'] is None
    return result


@pytest.fixture
def backup_options(request):
    if os.environ.get('OSPA_BACKUP_INSPECTION')!='1':
        return {}
    result=request.getfixturevalue('backup_reconciliation')
    return {'backup_permit':BackupPermit(**result['permit_proposal'])}
