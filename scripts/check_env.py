"""Read-only, secret-free host inspection. Unknown is never treated as success."""

from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import platform
import pwd
import shutil
import socket
import subprocess
import sys


def command(args: list[str]) -> dict:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
    except FileNotFoundError:
        return {"status": "PENDING", "reason": "tool not installed"}
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "NOT VERIFIED", "reason": "execution unavailable or timed out"}
    if result.returncode:
        return {"status": "NOT VERIFIED", "exit_code": result.returncode}
    return {"status": "PASS", "output": result.stdout.strip()}


def port_status() -> dict:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 1521))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            return {"status": "FAIL", "reason": "127.0.0.1:1521 is occupied"}
        return {"status": "NOT VERIFIED", "reason": "socket inspection denied or unavailable"}
    return {"status": "PASS", "reason": "127.0.0.1:1521 was bindable at inspection time"}


def tun_status() -> dict:
    try:
        # Opening the device alone creates no TAP interface or network configuration.
        descriptor = os.open("/dev/net/tun", os.O_RDWR | os.O_CLOEXEC)
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ENODEV}:
            return {"status": "FAIL", "reason": "TUN unavailable; check running kernel modules and reboot after kernel upgrades"}
        return {"status": "NOT VERIFIED", "reason": "TUN access denied or unavailable"}
    os.close(descriptor)
    return {"status": "PASS", "reason": "TUN device can be opened for rootless networking"}


def disk(path: Path) -> dict:
    while not path.exists() and path != path.parent:
        path = path.parent
    usage = shutil.disk_usage(path)
    return {"path": str(path), "total_bytes": usage.total, "free_bytes": usage.free}


def inspect() -> dict:
    root = Path(__file__).resolve().parents[1]
    username = pwd.getpwuid(os.getuid()).pw_name
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            memory[key] = int(value.split()[0]) * 1024
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), platform.machine())
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "os": platform.freedesktop_os_release().get("PRETTY_NAME"),
        "kernel": platform.release(), "architecture": platform.machine(),
        "running_kernel_modules_present": (Path("/usr/lib/modules") / platform.release()).is_dir(),
        "tun_device": tun_status(),
        "cpu": cpu, "logical_cpus": os.cpu_count(), "memory_bytes": memory,
        "uid": os.getuid(), "shell_environment": os.environ.get("SHELL", "NOT VERIFIED"),
        "parent_process": command(["ps", "-p", str(os.getppid()), "-o", "comm="]),
        "project_disk": disk(root), "project_path": str(root),
        "port_1521": port_status(),
        "python": sys.version.split()[0],
        "pip": command([sys.executable, "-m", "pip", "--version"]),
        "fish": command(["fish", "--version"]),
        "git": command(["git", "--version"]),
        "git_status": command(["git", "-C", str(root), "status", "--short"]),
        "podman_version": command(["podman", "--version"]),
        "podman_rootless": command(["podman", "info", "--format", "{{.Host.Security.Rootless}}"]),
        "podman_graphroot": command(["podman", "info", "--format", "{{.Store.GraphRoot}}"]),
        "containers": command(["podman", "ps", "-a", "--format", "{{.Names}} {{.Status}}"]),
        "images": command(["podman", "images", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}"]),
        "volumes": command(["podman", "volume", "ls", "--format", "{{.Name}}"]),
        "secrets_names_only": command(["podman", "secret", "ls", "--format", "{{.Name}}"]),
    }
    rootless = report["podman_rootless"]
    if rootless["status"] == "PASS" and rootless["output"] != "true":
        rootless["status"] = "FAIL"
    graphroot = report["podman_graphroot"]
    if graphroot["status"] == "PASS" and Path(graphroot["output"]).is_absolute():
        report["podman_disk"] = disk(Path(graphroot["output"]))
    else:
        report["podman_disk"] = {"status": "NOT VERIFIED"}
    for name in ("subuid", "subgid"):
        path = Path("/etc") / name
        try:
            entries = [line for line in path.read_text().splitlines()
                       if line.split(":")[0] in {username, str(os.getuid())}]
        except OSError:
            entries = []
        report[name] = {"status": "PASS" if entries else "NOT VERIFIED", "entries": entries}
    for path in ("/proc/sys/user/max_user_namespaces", "/proc/sys/kernel/unprivileged_userns_clone"):
        try:
            report[Path(path).name] = Path(path).read_text().strip()
        except OSError:
            report[Path(path).name] = "NOT VERIFIED"
    return report


def main() -> int:
    report = inspect()
    print(json.dumps(report, indent=2))
    checks = ("podman_rootless", "podman_disk", "tun_device", "port_1521", "git_status")
    return int(any(report[key].get("status", "PASS") != "PASS" for key in checks))


if __name__ == "__main__":
    raise SystemExit(main())

