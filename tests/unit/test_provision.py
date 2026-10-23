from contextlib import redirect_stderr, redirect_stdout
import getpass
import io
import unittest
from unittest.mock import MagicMock, patch

from oracle_spa.db import DiagnosticError
from scripts.provision import main, provision, read_password, validate_password


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.password = "UnitTestOnly123456"
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.side_effect = [("FREEPDB1", "SYSTEM"), (0,)]
        self.cursor.fetchall.side_effect = [[("CREATE SESSION",)], [], [], [("USERS", 1073741824)]]

    def test_minimum_grants_and_quota(self):
        provision(self.connection, self.password)
        statements = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertIn("GRANT CREATE SESSION TO ORACLE_SPA", statements)
        self.assertEqual(sum(sql.startswith("GRANT") for sql in statements), 1)
        self.assertIn("QUOTA 1G ON USERS", statements[2])
        self.connection.cursor.return_value.__exit__.assert_called_once()

    def test_existing_user_is_not_modified(self):
        self.cursor.fetchone.side_effect = [("FREEPDB1", "SYSTEM"), (1,)]
        with self.assertRaisesRegex(DiagnosticError, "already exists"):
            provision(self.connection, self.password)
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_wrong_container_is_not_modified(self):
        for identity in (("CDB$ROOT", "SYSTEM"), ("FREEPDB1", "SYS"), None):
            with self.subTest(identity=identity):
                self.cursor.reset_mock()
                self.cursor.fetchone.side_effect = [identity]
                with self.assertRaisesRegex(DiagnosticError, "FREEPDB1"):
                    provision(self.connection, self.password)
                self.assertEqual(self.cursor.execute.call_count, 1)

    def test_password_injection_and_policy(self):
        for password in ('UnitTestOnly123456"; DROP USER x', "A" * 31, "short", "lowercase123456789",
                         "UPPERCASE123456789", "NoDigitsAnywhereHere", "UnitTestOnly123456\n"):
            with self.subTest(length=len(password)), self.assertRaises(ValueError):
                validate_password(password)
        validate_password(self.password + "!@_-")

    def test_unexpected_grants_are_reported(self):
        self.cursor.fetchall.side_effect = [[("CREATE SESSION",), ("UNLIMITED TABLESPACE",)]]
        with self.assertRaisesRegex(DiagnosticError, "grants differ"):
            provision(self.connection, self.password)

    def test_wrong_quota_is_reported(self):
        for quota in (-1, 104857600):
            with self.subTest(quota=quota):
                self.cursor.fetchone.side_effect = [("FREEPDB1", "SYSTEM"), (0,)]
                self.cursor.fetchall.side_effect = [[("CREATE SESSION",)], [], [], [("USERS", quota)]]
                with self.assertRaisesRegex(DiagnosticError, "quota differs"):
                    provision(self.connection, self.password)

    def test_unexpected_roles_and_object_grants_are_reported(self):
        for results, message in (([[("CREATE SESSION",)], [("DBA",)]], "role"),
                                 ([[("CREATE SESSION",)], [], [("OTHER_TABLE",)]], "object")):
            with self.subTest(message=message):
                self.cursor.fetchone.side_effect = [("FREEPDB1", "SYSTEM"), (0,)]
                self.cursor.fetchall.side_effect = results
                with self.assertRaisesRegex(DiagnosticError, message):
                    provision(self.connection, self.password)

    def test_driver_errors_are_redacted_and_connection_closed(self):
        class DriverError(Exception):
            pass
        for stage in ("connect", "ddl"):
            with self.subTest(stage=stage):
                driver = MagicMock()
                driver.Error = DriverError
                driver.connect.side_effect = DriverError(self.password) if stage == "connect" else None
                output = io.StringIO()
                with patch("scripts.provision.load_driver", return_value=driver), \
                        patch("scripts.provision.read_password", return_value=self.password), \
                        patch("scripts.provision.provision", side_effect=DriverError(self.password)), \
                        redirect_stderr(output), redirect_stdout(output):
                    self.assertEqual(main(), 1)
                self.assertNotIn(self.password, output.getvalue())
                self.assertIn("FAIL provisioning", output.getvalue())
                if stage == "ddl":
                    driver.connect.return_value.__exit__.assert_called_once()

    def test_insecure_terminal_fallback_is_rejected(self):
        def insecure_getpass(prompt):
            import warnings
            warnings.warn("No terminal", getpass.GetPassWarning)
        with patch("scripts.provision.getpass.getpass", side_effect=insecure_getpass):
            with self.assertRaises(getpass.GetPassWarning):
                read_password("Password: ")

    def test_unexpected_error_never_echoes_password(self):
        for error in (RuntimeError, ValueError):
            with self.subTest(error=error):
                output = io.StringIO()
                with patch("scripts.provision.load_driver", side_effect=error(self.password)), redirect_stderr(output):
                    self.assertEqual(main(), 1)
                self.assertNotIn(self.password, output.getvalue())

