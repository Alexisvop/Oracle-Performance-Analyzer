from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from oracle_spa.config import Config
from oracle_spa.db import DiagnosticError, database_error, diagnose, load_driver


class DriverError(Exception):
    pass


def fake_driver():
    driver = MagicMock()
    driver.Error = DriverError
    driver.is_thin_mode.return_value = True
    connection = driver.connect.return_value.__enter__.return_value
    connection.thin = True
    connection.version = "23.26.0.0.0"
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [("FREEPDB1", "ORACLE_SPA"), (1,)]
    return driver, connection, cursor


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.config = Config("localhost:1521/FREEPDB1", "ORACLE_SPA", "test-only")
        self.driver, self.connection, self.cursor = fake_driver()
        self.patcher = patch("oracle_spa.db.load_driver", return_value=self.driver)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def assert_closed(self):
        self.driver.connect.return_value.__exit__.assert_called_once()
        self.connection.cursor.return_value.__exit__.assert_called_once()

    def test_real_query_path_with_mock_driver(self):
        result = diagnose(self.config)
        self.assertEqual((result.user, result.pdb, result.probe, result.version),
                         ("ORACLE_SPA", "FREEPDB1", 1, "23.26.0.0.0"))
        self.assertEqual(self.cursor.execute.call_args_list[-1].args, ("SELECT 1 FROM dual",))
        self.assertEqual(self.driver.connect.call_args.kwargs["retry_count"], 0)
        self.assertEqual(self.connection.call_timeout, 5000)
        self.assert_closed()

    def test_wrong_user_or_pdb_stops_before_probe(self):
        for identity in (("CDB$ROOT", "ORACLE_SPA"), ("FREEPDB1", "SYSTEM"), None):
            self.cursor.fetchone.side_effect = [identity]
            with self.assertRaisesRegex(DiagnosticError, "identity mismatch"):
                diagnose(self.config)
        self.assertEqual(self.cursor.execute.call_count, 3)

    def test_bad_probe_closes_resources(self):
        self.cursor.fetchone.side_effect = [("FREEPDB1", "ORACLE_SPA"), (0,)]
        with self.assertRaisesRegex(DiagnosticError, "SELECT 1"):
            diagnose(self.config)
        self.assert_closed()

    def test_query_error_closes_resources_and_redacts(self):
        self.cursor.execute.side_effect = DriverError("test-only sensitive descriptor")
        with self.assertRaises(DiagnosticError) as error:
            diagnose(self.config)
        self.assertNotIn("test-only", str(error.exception))
        self.assert_closed()

    def test_rejects_thick_mode_before_connecting(self):
        self.driver.is_thin_mode.return_value = False
        with self.assertRaisesRegex(DiagnosticError, "Thin mode"):
            diagnose(self.config)
        self.driver.connect.assert_not_called()

    def test_connection_mode_must_be_thin(self):
        self.connection.thin = False
        with self.assertRaisesRegex(DiagnosticError, "Thin mode"):
            diagnose(self.config)
        self.driver.connect.return_value.__exit__.assert_called_once()

    def test_invalid_version_is_not_echoed(self):
        self.connection.version = "sensitive-server-output"
        with self.assertRaisesRegex(DiagnosticError, "NOT VERIFIED") as error:
            diagnose(self.config)
        self.assertNotIn("sensitive-server-output", str(error.exception))
        self.assert_closed()

    def test_connect_failure(self):
        self.driver.connect.side_effect = DriverError("password=test-only")
        with self.assertRaises(DiagnosticError) as error:
            diagnose(self.config)
        self.assertNotIn("test-only", str(error.exception))

    def test_error_categories(self):
        for code, expected in (("ORA-01017", "Authentication"), ("ORA-28000", "Authentication"),
                               ("ORA-28001", "Authentication"), ("ORA-01031", "Permission"),
                               ("ORA-00942", "Permission"), ("DPY-6005", "readiness")):
            with self.subTest(code=code):
                message = database_error(DriverError(SimpleNamespace(full_code=code)))
                self.assertIn(expected, message)

    def test_missing_driver_is_actionable(self):
        with patch("oracle_spa.db.importlib.import_module", side_effect=ImportError("sensitive")):
            with self.assertRaisesRegex(DiagnosticError, "Install the project dependencies"):
                load_driver()

