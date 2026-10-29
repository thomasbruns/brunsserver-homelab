"""Compara as portas em escuta (ss) com as documentadas no services.yaml."""
from __future__ import annotations

import re

from ..config import parse_port, parse_port_range
from ..util import run

# `ss -p` mostra o processo como users:(("nome",pid=123,fd=4))
PROCESS_RE = re.compile(r'users:\(\("([^"]+)"')


def parse_local(local: str) -> tuple[str, str, str]:
    """'addr%iface:port' ou '[v6]%iface:port' -> (host, iface, porta)."""
    host, _, port = local.rpartition(":")
    host, _, iface = host.partition("%")
    return host.strip("[]"), iface, port


def is_local_only(host: str, iface: str) -> bool:
    """Loopback, link-local (fe80::) ou preso a uma interface tailscale*."""
    return (host.startswith("127.") or host == "::1" or iface == "lo"
            or host.lower().startswith("fe80:") or iface.startswith("tailscale"))


def parse_ss(output: str) -> dict[tuple[int, str], str | None]:
    """Extrai {(porta, proto): processo} das linhas de `ss -H -tuln[p]`.

    Ignora o que não é alcançável pela rede (ver is_local_only). Sem `-p`, o processo é None.
    """
    found: dict[tuple[int, str], str | None] = {}
    for line in output.splitlines():
        cols = line.split()
        if len(cols) < 5:
            continue
        proto, local = cols[0], cols[4]
        if proto not in ("tcp", "udp"):
            continue
        host, iface, port = parse_local(local)
        if is_local_only(host, iface) or not port.isdigit():
            continue
        m = PROCESS_RE.search(line)
        key = (int(port), proto)
        found[key] = found.get(key) or (m.group(1) if m else None)
    return found


def documented_ports(cfg: dict) -> set[tuple[int, str]]:
    return {parse_port(p) for svc in cfg["services"] for p in svc.get("ports", [])}


def optional_ports(cfg: dict) -> set[tuple[int, str]]:
    """Portas que podem não estar escutando (ex.: só abrem com alguém conectado)."""
    return {parse_port(p) for svc in cfg["services"] for p in svc.get("optional_ports", [])}


def is_ignored(port: int, proto: str, ranges: list[tuple[int, int, str]]) -> bool:
    return any(lo <= port <= hi and proto == p for lo, hi, p in ranges)


def check_ports(cfg: dict) -> dict:
    # Com sudo (ver README) o ss mostra o processo de qualquer usuário; sem, só os nossos.
    code, out = run(["sudo", "-n", "ss", "-H", "-tulnp"])
    if code != 0:
        code, out = run(["ss", "-H", "-tuln"])
    if code == 127:
        return {"available": False, "undocumented": [], "not_listening": []}
    listening = parse_ss(out)
    documented = documented_ports(cfg)
    ignored = [parse_port_range(p) for p in cfg["ignore_ports"]]
    return {
        "available": True,
        "undocumented": [
            {"port": p, "proto": proto, "process": listening[(p, proto)]}
            for p, proto in sorted(listening.keys() - documented)
            if not is_ignored(p, proto, ignored)
        ],
        "not_listening": [f"{p}/{proto}" for p, proto
                          in sorted(documented - listening.keys() - optional_ports(cfg))],
    }
