"""Validate the local laboratory connection without echoing input values."""

from collections.abc import Mapping
from dataclasses import dataclass, field
import os
import re
from pathlib import Path
import stat

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_KEYS = {"ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD"}


def local_environment():
    """Read only the checkout's owner-only regular .env; never evaluate shell text."""
    values = dict(os.environ)
    if ENV_KEYS <= values.keys():
        return values
    path = PROJECT_ROOT / ".env"
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return values
    except OSError:
        raise ConfigError("Cannot safely open the project's .env file.") from None
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > 16384):
                raise ConfigError(".env must be an owner-owned regular file with mode 600, at most 16 KiB.")
            text = stream.read(16385)
            if len(text) > 16384:
                raise ConfigError(".env exceeds the allowed size.")
            loaded = {}
            for line in text.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                key, separator, value = line.partition("=")
                if not separator or key not in ENV_KEYS or key in loaded:
                    raise ConfigError("Invalid .env format: use each supported KEY=literal-value once.")
                loaded[key] = value
            return loaded | values
    except (OSError, UnicodeError):
        raise ConfigError("Cannot read the project's .env safely.") from None


class ConfigError(ValueError):
    """An actionable, secret-free configuration error."""


@dataclass(frozen=True)
class Config:
    dsn: str = field(repr=False)
    user: str = field(repr=False)
    password: str = field(repr=False)

    def __post_init__(self) -> None:
        match = re.fullmatch(r"(?:localhost|127\.0\.0\.1):([0-9]{1,5})/FREEPDB1", self.dsn)
        if not match or not 1 <= int(match[1]) <= 65535:
            raise ConfigError(
                "ORACLE_DSN must be localhost:PORT/FREEPDB1 or "
                "127.0.0.1:PORT/FREEPDB1 (port 1-65535); omit credentials."
            )
        if self.user != "ORACLE_SPA":
            raise ConfigError("ORACLE_USER must be ORACLE_SPA; administrative accounts are forbidden.")
        if not self.password.strip() or any(ord(c) < 32 or ord(c) == 127 for c in self.password):
            raise ConfigError("ORACLE_PASSWORD must be nonempty and contain no control characters.")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Config":
        values = local_environment() if environ is None else environ
        for name in ("ORACLE_DSN", "ORACLE_USER", "ORACLE_PASSWORD"):
            if not values.get(name, "").strip():
                raise ConfigError(f"Set {name} before running doctor; see README.md.")
        return cls(values["ORACLE_DSN"], values["ORACLE_USER"].upper(), values["ORACLE_PASSWORD"])

