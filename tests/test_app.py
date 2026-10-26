import importlib
import time

import pytest
from fastapi.testclient import TestClient

from app.collectors import ports, services
from app.config import parse_port
from app.util import humanize

SS_OUTPUT = """\
tcp   LISTEN 0 4096 127.0.0.53%lo:53      0.0.0.0:*
tcp   LISTEN 0 128  0.0.0.0:22            0.0.0.0:*
tcp   LISTEN 0 4096 0.0.0.0:8080          0.0.0.0:*
tcp   LISTEN 0 4096 [::]:8080             [::]:*
tcp   LISTEN 0 4096 [::1]:631             [::]:*
udp   UNCONN 0 0    0.0.0.0:16261         0.0.0.0:*
udp   UNCONN 0 0    *:41641               *:*
tcp   LISTEN 0 4096 100.80.165.68:9999    0.0.0.0:*
"""


def test_parse_ss_ignores_loopback_and_dedupes():
    assert ports.parse_ss(SS_OUTPUT) == {
        (22, "tcp"), (8080, "tcp"), (16261, "udp"), (41641, "udp"), (9999, "tcp"),
    }


def test_check_ports_reports_diff(monkeypatch):
    monkeypatch.setattr(ports, "run", lambda cmd, timeout=5.0: (0, SS_OUTPUT))
    cfg = {
        "services": [{"ports": ["8080/tcp", "16261/udp", "1984"]}],
        "ignore_ports": ["22/tcp", "41641/udp"],
    }
    res = ports.check_ports(cfg)
    assert res["undocumented"] == ["9999/tcp"]
    assert res["not_listening"] == ["1984/tcp"]


def test_parse_port_and_humanize():
    assert parse_port("16261/UDP") == (16261, "udp")
    assert parse_port(8080) == (8080, "tcp")
    assert humanize(59) == "0m"
    assert humanize(3 * 3600 + 120) == "3h 2m"
    assert humanize(2 * 86400 + 5 * 3600) == "2d 5h"
    assert humanize(None) == "—"


def test_docker_parse_time_handles_nanoseconds():
    ts = services._parse_docker_time("2026-10-23T12:00:00.123456789Z")
    assert ts is not None and ts > 1.7e9
    assert services._parse_docker_time("0001-01-01T00:00:00Z") is None


def test_check_docker_states(monkeypatch):
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000000000Z", time.gmtime(time.time() - 7200))
    answers = {
        "a": (0, f"running|{now}|"),
        "b": (0, f"running|{now}|unhealthy"),
        "c": (0, "exited|0001-01-01T00:00:00Z|"),
        "d": (1, ""),
    }
    monkeypatch.setattr(services, "run", lambda cmd, timeout=5.0: answers[cmd[-1]])
    up = services.check_docker(["a"])
    assert up["state"] == "up" and 7000 < up["uptime_seconds"] < 7400
    assert services.check_docker(["a", "b"])["state"] == "degraded"
    assert services.check_docker(["a", "c"])["state"] == "down"
    assert services.check_docker(["d"])["state"] == "missing"


def test_check_systemd(monkeypatch):
    out = "LoadState=loaded\nActiveState=active\nSubState=running\nActiveEnterTimestamp=@1700000000"
    monkeypatch.setattr(services, "run", lambda cmd, timeout=5.0: (0, out))
    res = services.check_systemd("x")
    assert res["state"] == "up" and res["since"] == 1700000000.0
    monkeypatch.setattr(services, "run", lambda cmd, timeout=5.0: (0, "LoadState=not-found\nActiveState=inactive"))
    assert services.check_systemd("x")["state"] == "missing"
    # systemctl presente mas sem resposta (sem systemd): "unknown", nunca "down"
    monkeypatch.setattr(services, "run", lambda cmd, timeout=5.0: (1, ""))
    assert services.check_systemd("x")["state"] == "unknown"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_DB", str(tmp_path / "m.db"))
    from app import config, db, main
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_pages_render(client):
    for path, marker in [("/", "Serviços"), ("/server", "Temperatura"), ("/docs", "Documentação")]:
        r = client.get(path)
        assert r.status_code == 200 and marker in r.text


def test_docs_lists_services_from_yaml(client):
    html = client.get("/docs").text
    assert "Nextcloud" in html and "16261/udp" in html and "OptiPlex" in html


def test_api_endpoints(client):
    svcs = client.get("/api/services").json()
    assert {s["id"] for s in svcs} >= {"nextcloud", "zomboid", "go2rtc"}
    assert all("state" in s and "uptime" in s for s in svcs)
    assert "mounts" in client.get("/api/system").json()
    assert "undocumented" in client.get("/api/ports").json()
    temps = client.get("/api/temps?hours=1").json()
    assert temps["interval_seconds"] == 1800
    assert client.get("/api/temps?hours=0").status_code == 422


def test_sampler_writes_first_sample_on_startup(client):
    # o lifespan grava uma amostra ao subir; espera a thread terminar
    for _ in range(50):
        if client.get("/api/temps?hours=1").json()["samples"]:
            break
        time.sleep(0.1)
    assert client.get("/api/temps?hours=1").json()["samples"]
