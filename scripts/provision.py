"""Interactively provision only ORACLE_SPA in FREEPDB1; never reset existing users."""

import getpass
import re
import sys
import warnings

from oracle_spa.db import DiagnosticError, database_error, load_driver


def read_password(prompt: str) -> str:
    # Refuse getpass's echoing fallback when no secure terminal is available.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass(prompt)


def validate_password(password: str) -> None:
    if (not re.fullmatch(r"[A-Za-z0-9!#$%*+.:=?@_-]{16,30}", password)
            or not any(c.islower() for c in password)
            or not any(c.isupper() for c in password)
            or not any(c.isdigit() for c in password)):
        raise ValueError("Use 16-30 ASCII characters, including uppercase, lowercase and digits; symbols: !#$%*+.:=?@_-")


def provision(connection, password: str) -> None:
    validate_password(password)
    connection.call_timeout = 5000
    with connection.cursor() as cursor:
        cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CON_NAME'), USER FROM dual")
        if cursor.fetchone() != ("FREEPDB1", "SYSTEM"):
            raise DiagnosticError("Provisioning requires SYSTEM connected directly to FREEPDB1.")
        cursor.execute("SELECT COUNT(*) FROM dba_users WHERE username = 'ORACLE_SPA'")
        if cursor.fetchone() != (0,):
            raise DiagnosticError("ORACLE_SPA already exists; inspect its grants and quota manually. No changes made.")
        # Oracle DDL cannot bind passwords; the strict allowlist excludes SQL delimiters.
        cursor.execute(
            f'CREATE USER ORACLE_SPA IDENTIFIED BY "{password}" '
            'DEFAULT TABLESPACE USERS TEMPORARY TABLESPACE TEMP QUOTA 1G ON USERS'
        )
        cursor.execute("GRANT CREATE SESSION TO ORACLE_SPA")
        cursor.execute("SELECT privilege FROM dba_sys_privs WHERE grantee = 'ORACLE_SPA'")
        if set(cursor.fetchall()) != {("CREATE SESSION",)}:
            raise DiagnosticError("Provisioned grants differ from the Phase 1 policy; review manually.")
        cursor.execute("SELECT granted_role FROM dba_role_privs WHERE grantee = 'ORACLE_SPA'")
        if cursor.fetchall():
            raise DiagnosticError("Unexpected role grants; review manually.")
        cursor.execute("SELECT table_name FROM dba_tab_privs WHERE grantee = 'ORACLE_SPA'")
        if cursor.fetchall():
            raise DiagnosticError("Unexpected object grants; review manually.")
        cursor.execute("SELECT tablespace_name, max_bytes FROM dba_ts_quotas WHERE username = 'ORACLE_SPA'")
        if cursor.fetchall() != [("USERS", 1073741824)]:
            raise DiagnosticError("Storage quota differs from the 1 GiB policy; review manually.")


def main() -> int:
    try:
        driver = load_driver()
        if not driver.is_thin_mode():
            raise DiagnosticError("Provisioning requires Thin mode.")
        admin_password = read_password("SYSTEM password (provisioning only): ")
        password = read_password("New ORACLE_SPA password: ")
        validate_password(password)
        if read_password("Confirm ORACLE_SPA password: ") != password:
            raise ValueError("Passwords do not match.")
        try:
            with driver.connect(user="SYSTEM", password=admin_password,
                                dsn="127.0.0.1:1521/FREEPDB1",
                                tcp_connect_timeout=5, retry_count=0) as connection:
                provision(connection, password)
        except driver.Error as exc:
            raise DiagnosticError(database_error(exc)) from None
    except (DiagnosticError, ValueError) as exc:
        message = str(exc) if isinstance(exc, DiagnosticError) else "Invalid input: check the documented password policy and matching confirmation."
        print(f"FAIL provisioning: {message}", file=sys.stderr)
        print("DDL may already have committed. Inspect the account before retrying; never drop it automatically.", file=sys.stderr)
        return 1
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print("FAIL provisioning: a secure interactive terminal is required; operation cancelled.", file=sys.stderr)
        return 1
    except Exception:
        print("FAIL provisioning: unexpected error. Inspect the account; DDL may have committed.", file=sys.stderr)
        return 1
    print("PASS provisioning: ORACLE_SPA in FREEPDB1; CREATE SESSION only; no direct roles/object grants; USERS quota 1 GiB.")
    print("Run doctor as ORACLE_SPA to verify its effective session.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
