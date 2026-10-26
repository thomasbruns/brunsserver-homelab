"""Status dos serviços: systemd, Docker ou processo (para o Zomboid, que roda sob outro usuário)."""
from __future__ import annotations

import time
from datetime import datetime

from ..util import humanize, run


def _result(state: str, detail: str = "", since: float | None = None) -> dict:
    uptime = int(time.time() - since) if since and state in ("up", "degraded") else None
    return {
        "state": state,  # up | degraded | down | missing | unknown
        "detail": detail,
        "since": since,
        "uptime_seconds": uptime,
        "uptime": humanize(uptime),
    }


def check_systemd(unit: str) -> dict:
    code, out = run([
        "systemctl", "show", unit,
        "-p", "LoadState", "-p", "ActiveState", "-p", "SubState",
        "-p", "ActiveEnterTimestamp", "--timestamp=unix",
    ])
    if code == 127:
        return _result("unknown", "systemctl indisponível")
    props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    if code != 0 or "ActiveState" not in props:
        # systemctl existe mas não respondeu (ex.: container sem systemd): não dá para afirmar "parado"
        return _result("unknown", "systemctl não respondeu")
    if props.get("LoadState") == "not-found":
        return _result("missing", f"unit {unit} não existe")
    active, sub = props.get("ActiveState", ""), props.get("SubState", "")
    ts = props.get("ActiveEnterTimestamp", "")
    since = float(ts[1:]) if ts.startswith("@") else None
    return _result("up" if active == "active" else "down", f"{active}/{sub}", since)


def _parse_docker_time(value: str) -> float | None:
    # '2026-10-23T12:00:00.123456789Z' -> trunca para microssegundos
    try:
        base, _, frac = value.rstrip("Z").partition(".")
        frac = (frac + "000000")[:6]
        dt = datetime.fromisoformat(f"{base}.{frac}+00:00")
        return dt.timestamp() if dt.year > 1 else None
    except ValueError:
        return None


def check_docker(names: list[str]) -> dict:
    fmt = "{{.State.Status}}|{{.State.StartedAt}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}"
    states, starts, missing, unhealthy = [], [], [], []
    for name in names:
        code, out = run(["docker", "inspect", "-f", fmt, name])
        if code == 127:
            return _result("unknown", "docker indisponível (usuário no grupo docker?)")
        if code != 0:
            missing.append(name)
            continue
        status, started, health = (out.split("|") + ["", ""])[:3]
        states.append(status)
        if status == "running":
            ts = _parse_docker_time(started)
            if ts:
                starts.append(ts)
            if health == "unhealthy":
                unhealthy.append(name)
    if missing and not states:
        return _result("missing", "container não encontrado: " + ", ".join(missing))
    if missing or any(s != "running" for s in states):
        down = missing + [n for n, s in zip(names, states) if s != "running"]
        return _result("down", "parado: " + ", ".join(down))
    since = max(starts) if starts else None  # stack: vale o container que subiu por último
    if unhealthy:
        return _result("degraded", "unhealthy: " + ", ".join(unhealthy), since)
    return _result("up", f"{len(names)} container(s) rodando", since)


def check_process(pattern: str) -> dict:
    code, out = run(["pgrep", "-f", "-o", pattern])
    if code == 127:
        return _result("unknown", "pgrep indisponível")
    if code != 0 or not out:
        return _result("down", f"nenhum processo casa com '{pattern}'")
    pid = out.splitlines()[0]
    code, etimes = run(["ps", "-o", "etimes=", "-p", pid])
    since = time.time() - int(etimes) if code == 0 and etimes.strip().isdigit() else None
    return _result("up", f"pid {pid}", since)


def check_service(svc: dict) -> dict:
    check = svc.get("check") or {}
    kind = check.get("kind")
    try:
        if kind == "systemd":
            res = check_systemd(check["unit"])
        elif kind == "docker":
            names = check.get("containers") or [check["container"]]
            res = check_docker(names)
        elif kind == "process":
            res = check_process(check["match"])
        else:
            res = _result("unknown", "sem 'check' no services.yaml")
    except KeyError as e:
        res = _result("unknown", f"campo ausente no check: {e}")
    return {"id": svc["id"], "name": svc.get("name", svc["id"]), **res}
