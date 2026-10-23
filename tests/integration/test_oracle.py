"""Live Oracle evidence only. Explicitly select with python -m pytest -m oracle."""

import pytest

from oracle_spa.config import Config
from oracle_spa.db import diagnose

pytestmark = pytest.mark.oracle


def test_real_oracle_connection():
    result = diagnose(Config.from_env())
    assert result.user == "ORACLE_SPA"
    assert result.pdb == "FREEPDB1"
    assert result.probe == 1
    assert result.version
