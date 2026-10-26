"""Métricas do servidor: temperatura, carga, RAM, disco, uptime."""
from __future__ import annotations

import glob
import json
import os
import shutil
import socket
from pathlib import Path

from ..util import humanize, run


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def cpu_temp() -> float | None:
    """Temperatura da CPU em °C. Prefere hwmon (coretemp/k10temp); cai para thermal_zone."""
    best: list[float] = []
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        if _read(f"{hw}/name") in ("coretemp", "k10temp", "zenpower"):
            for f in glob.glob(f"{hw}/temp*_input"):
                raw = _read(f)
                if raw and raw.lstrip("-").isdigit():
                    best.append(int(raw) / 1000)
    if not best:
        for f in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
            raw = _read(f)
            if raw and raw.lstrip("-").isdigit():
                best.append(int(raw) / 1000)
    return round(max(best), 1) if best else None


def disk_temps(devices: list[str]) -> dict[str, float]:
    """Temperatura dos discos via smartctl. Precisa de root: tenta `sudo -n` (ver README)."""
    out: dict[str, float] = {}
    for dev in devices:
        for cmd in (["sudo", "-n", "smartctl", "-j", "-A", dev], ["smartctl", "-j", "-A", dev]):
            _, stdout = run(cmd, timeout=10)  # smartctl usa bitmask de exit code; ignora
            try:
                temp = json.loads(stdout)["temperature"]["current"]
            except (ValueError, KeyError, TypeError):
                continue
            out[dev] = float(temp)
            break
    return out


def memory_percent() -> float | None:
    info: dict[str, int] = {}
    raw = _read("/proc/meminfo")
    if not raw:
        return None
    for line in raw.splitlines():
        key, _, rest = line.partition(":")
        info[key] = int(rest.split()[0])
    total, avail = info.get("MemTotal"), info.get("MemAvailable")
    return round(100 * (1 - avail / total), 1) if total and avail is not None else None


def mount_usage(mounts: list[str]) -> list[dict]:
    result = []
    for m in mounts:
        try:
            u = shutil.disk_usage(m)
            result.append({
                "mount": m,
                "mounted": os.path.ismount(m),
                "percent": round(100 * u.used / u.total, 1),
                "used_gb": round(u.used / 1e9, 1),
                "total_gb": round(u.total / 1e9, 1),
            })
        except OSError:
            result.append({"mount": m, "mounted": False, "percent": None, "used_gb": None, "total_gb": None})
    return result


def uptime_seconds() -> int | None:
    raw = _read("/proc/uptime")
    return int(float(raw.split()[0])) if raw else None


def snapshot(disks: list[str], mounts: list[str]) -> dict:
    up = uptime_seconds()
    load1, load5, load15 = os.getloadavg()
    return {
        "hostname": socket.gethostname(),
        "cpu_temp": cpu_temp(),
        "disk_temps": disk_temps(disks),
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "cpus": os.cpu_count(),
        "mem_percent": memory_percent(),
        "mounts": mount_usage(mounts),
        "uptime_seconds": up,
        "uptime": humanize(up),
    }
