import errno
import subprocess
import unittest
from unittest.mock import MagicMock, patch

from scripts.check_env import command, port_status, tun_status


class EnvironmentTests(unittest.TestCase):
    def test_missing_tool_is_pending(self):
        with patch("scripts.check_env.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(command(["missing"])["status"], "PENDING")

    def test_denied_and_timed_out_commands_are_unknown(self):
        for error in (PermissionError(), subprocess.TimeoutExpired("tool", 20)):
            with patch("scripts.check_env.subprocess.run", side_effect=error):
                self.assertEqual(command(["tool"])["status"], "NOT VERIFIED")

    def test_command_errors_do_not_echo_output(self):
        result = subprocess.CompletedProcess([], 1, "password=private", "password=private")
        with patch("scripts.check_env.subprocess.run", return_value=result):
            report = command(["tool"])
        self.assertEqual(report["status"], "NOT VERIFIED")
        self.assertNotIn("private", str(report))

    def test_port_status_distinguishes_denied_from_busy(self):
        for number, expected in ((errno.EACCES, "NOT VERIFIED"), (errno.EPERM, "NOT VERIFIED"),
                                  (errno.EADDRINUSE, "FAIL")):
            with self.subTest(number=number), patch("scripts.check_env.socket.socket", side_effect=OSError(number, "test")):
                self.assertEqual(port_status()["status"], expected)

    def test_bindable_port(self):
        with patch("scripts.check_env.socket.socket", return_value=MagicMock()):
            self.assertEqual(port_status()["status"], "PASS")

    def test_tun_missing_device_and_permission_errors(self):
        for number, expected in ((errno.ENOENT, "FAIL"), (errno.ENODEV, "FAIL"),
                                 (errno.EACCES, "NOT VERIFIED")):
            with self.subTest(number=number), patch("scripts.check_env.os.open", side_effect=OSError(number, "test")):
                self.assertEqual(tun_status()["status"], expected)

    def test_tun_probe_closes_descriptor(self):
        with patch("scripts.check_env.os.open", return_value=42), patch("scripts.check_env.os.close") as close:
            self.assertEqual(tun_status()["status"], "PASS")
        close.assert_called_once_with(42)
