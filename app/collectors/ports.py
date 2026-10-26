"""Compara as portas em escuta (ss) com as documentadas no services.yaml."""
from __future__ import annotations

from ..config import parse_port
from ..util import run


def parse_ss(output: str) -> set[tuple[int, str]]:
    """Extrai {(porta, proto)} das linhas de `ss -H -tuln`, ignorando loopback."""
    found: set[tuple[int, str]] = set()
    for line in output.splitlines():
        cols = line.split()
        if len(cols) < 5:
            continue
        proto, local = cols[0], cols[4]
        if proto not in ("tcp", "udp"):
            continue
        host, _, port = local.rpartition(":")
        host = host.strip("[]").split("%")[0]
        if host.startswith("127.") or host == "::1" or not port.isdigit():
            continue  # só nos interessa o que é alcançável pela rede
        found.add((int(port), proto))
    return found


def documented_ports(cfg: dict) -> set[tuple[int, str]]:
    return {parse_port(p) for svc in cfg["services"] for p in svc.get("ports", [])}


def check_ports(cfg: dict) -> dict:
    code, out = run(["ss", "-H", "-tuln"])
    if code == 127:
        return {"available": False, "undocumented": [], "not_listening": []}
    listening = parse_ss(out)
    documented = documented_ports(cfg)
    ignored = {parse_port(p) for p in cfg["ignore_ports"]}
    fmt = lambda s: [f"{p}/{proto}" for p, proto in sorted(s)]  # noqa: E731
    return {
        "available": True,
        "undocumented": fmt(listening - documented - ignored),
        "not_listening": fmt(documented - listening),
    }
