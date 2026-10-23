from contextlib import redirect_stderr, redirect_stdout
import io
import os
import unittest
from unittest.mock import patch

from oracle_spa.cli import main
from oracle_spa.db import Diagnosis, DiagnosticError


class CliTests(unittest.TestCase):
    def run_cli(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["doctor"])
        return code, out.getvalue(), err.getvalue()

    def test_missing_configuration_prevents_connection(self):
        with patch("oracle_spa.config.local_environment", return_value={}), patch("oracle_spa.cli.diagnose") as diagnose:
            code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("ORACLE_DSN", err)
        self.assertEqual(out, "")
        diagnose.assert_not_called()

    def test_success_output(self):
        with patch("oracle_spa.cli.Config.from_env"), patch("oracle_spa.cli.diagnose", return_value=
                Diagnosis("ORACLE_SPA", "FREEPDB1", "23.26.0.0.0", 1)):
            code, out, err = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("PASS SELECT 1 FROM dual: 1", out)
        self.assertIn("FREEPDB1", out)

    def test_safe_diagnostic_and_unexpected_errors(self):
        for error, expected in ((DiagnosticError("Safe diagnostic"), "Safe diagnostic"),
                                (RuntimeError("password=private-value"), "unexpected error"),
                                (KeyboardInterrupt(), "interrupted")):
            with self.subTest(error=type(error).__name__), patch("oracle_spa.cli.Config.from_env"), \
                    patch("oracle_spa.cli.diagnose", side_effect=error):
                code, out, err = self.run_cli()
            self.assertEqual(code, 130 if isinstance(error, KeyboardInterrupt) else 1)
            self.assertEqual(out, "")
            self.assertIn(expected, err)
            self.assertNotIn("private-value", err)

    def test_invalid_command(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["benchmark"])
        self.assertEqual(error.exception.code, 2)

