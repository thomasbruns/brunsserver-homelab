from __future__ import annotations

import subprocess


def run(cmd: list[str], timeout: float = 5.0) -> tuple[int, str]:
    """Roda um comando sem shell. Retorna (returncode, stdout); 127 se não existir/estourar."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip()
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return 127, ""


def humanize(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"
