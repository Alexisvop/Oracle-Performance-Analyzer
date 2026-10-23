"""Read-only diagnostics through python-oracledb Thin mode."""

from dataclasses import dataclass
from contextlib import contextmanager
import importlib
import re

from oracle_spa.config import Config


class DiagnosticError(RuntimeError):
    """A diagnostic failure whose message is safe to display."""


def load_driver():
    try:
        return importlib.import_module("oracledb")
    except ImportError:
        raise DiagnosticError("Install the project dependencies in .venv; python-oracledb is unavailable.") from None


def database_error(exc: Exception) -> str:
    # Driver messages may contain connect descriptors or credentials.
    code = getattr(exc.args[0], "full_code", "") if exc.args else ""
    if code in {"ORA-01017", "ORA-28000", "ORA-28001"}:
        return "Authentication failed: verify the password and account status with the administrator."
    if code in {"ORA-01031", "ORA-00942"}:
        return "Permission check failed: review the exact missing grant; do not grant DBA roles."
    return "Oracle operation failed: check container readiness, listener, FREEPDB1 and credentials."


@dataclass(frozen=True)
class Diagnosis:
    user: str
    pdb: str
    version: str
    probe: int


@contextmanager
def laboratory_session(config):
    """Dedicated transaction boundary for schema, data and statistics commands."""
    from oracle_spa.schema import assert_identity
    driver = load_driver()
    if not driver.is_thin_mode():
        raise DiagnosticError("Thin mode is required.")
    try:
        with driver.connect(user=config.user, password=config.password, dsn=config.dsn,
                            tcp_connect_timeout=5, retry_count=0) as connection:
            connection.call_timeout = 30000
            if not connection.thin:
                raise DiagnosticError("Thin mode was not verified.")
            assert_identity(connection)
            yield connection
    except driver.Error as exc:
        raise DiagnosticError(database_error(exc)) from None


def diagnose(config: Config) -> Diagnosis:
    driver = load_driver()
    if not driver.is_thin_mode():
        raise DiagnosticError("Thin mode is required; start a fresh process without Oracle Client initialization.")
    try:
        with driver.connect(
            user=config.user, password=config.password, dsn=config.dsn,
            tcp_connect_timeout=5, retry_count=0,
        ) as connection:
            connection.call_timeout = 5000
            if not connection.thin:
                raise DiagnosticError("Thin mode was not verified.")
            with connection.cursor() as cursor:
                cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CON_NAME'), USER FROM dual")
                if cursor.fetchone() != ("FREEPDB1", "ORACLE_SPA"):
                    raise DiagnosticError("Session identity mismatch: expected ORACLE_SPA in FREEPDB1.")
                cursor.execute("SELECT 1 FROM dual")
                if cursor.fetchone() != (1,):
                    raise DiagnosticError("SELECT 1 FROM dual did not return the expected result.")
            version = connection.version
            if not isinstance(version, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,5}", version):
                raise DiagnosticError("Oracle server version: NOT VERIFIED.")
            return Diagnosis(user="ORACLE_SPA", pdb="FREEPDB1", version=version, probe=1)
    except driver.Error as exc:
        raise DiagnosticError(database_error(exc)) from None

