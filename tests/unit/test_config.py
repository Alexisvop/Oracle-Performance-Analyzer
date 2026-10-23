import os
import unittest
from unittest.mock import patch

from oracle_spa.config import Config, ConfigError


def environment():
    return {"ORACLE_DSN": "localhost:1521/FREEPDB1", "ORACLE_USER": "ORACLE_SPA",
            "ORACLE_PASSWORD": "unit-test-only-value"}


class ConfigTests(unittest.TestCase):
    def test_reads_environment_and_redacts_repr(self):
        values = environment()
        with patch.dict(os.environ, values, clear=True):
            config = Config.from_env()
        self.assertEqual(config.dsn, values["ORACLE_DSN"])
        self.assertEqual(config.password, values["ORACLE_PASSWORD"])
        self.assertNotIn(config.password, repr(config))
        self.assertNotIn(config.dsn, repr(config))

    def test_required_variables(self):
        for name in environment():
            for value in (None, "", "  "):
                with self.subTest(name=name, value=value):
                    values = environment()
                    if value is None:
                        del values[name]
                    else:
                        values[name] = value
                    with self.assertRaisesRegex(ConfigError, name):
                        Config.from_env(values)

    def test_dsn_validation(self):
        for dsn in ("remote:1521/FREEPDB1", "localhost:0/FREEPDB1", "localhost:65536/FREEPDB1",
                    "localhost:1521/FREE", "user/password@localhost:1521/FREEPDB1",
                    "localhost:1521/FREEPDB1?password=private", "localhost:1521/FREEPDB1\n",
                    "(DESCRIPTION=secret)"):
            with self.subTest(dsn=dsn):
                with self.assertRaises(ConfigError) as error:
                    Config.from_env(environment() | {"ORACLE_DSN": dsn})
                self.assertNotIn(dsn, str(error.exception))

    def test_allowed_user_and_ports(self):
        for host in ("localhost", "127.0.0.1"):
            for port in (1, 1521, 65535):
                config = Config.from_env(environment() | {"ORACLE_USER": "oracle_spa",
                                        "ORACLE_DSN": f"{host}:{port}/FREEPDB1"})
                self.assertEqual(config.user, "ORACLE_SPA")

    def test_rejects_admin_and_proxy_users(self):
        for user in ("SYS", "SYSTEM", "OTHER", "ORACLE_SPA[SYS]", " ORACLE_SPA"):
            with self.subTest(user=user), self.assertRaises(ConfigError):
                Config.from_env(environment() | {"ORACLE_USER": user})

    def test_password_is_not_trimmed_and_controls_are_rejected(self):
        self.assertEqual(Config.from_env(environment() | {"ORACLE_PASSWORD": " x "}).password, " x ")
        for password in ("x\n", "x\x00", "x\x7f"):
            with self.assertRaises(ConfigError):
                Config.from_env(environment() | {"ORACLE_PASSWORD": password})

    def test_direct_constructor_also_validates(self):
        with self.assertRaises(ConfigError):
            Config("localhost:1521/FREEPDB1", "SYSTEM", "test-only")

