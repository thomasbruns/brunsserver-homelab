"""Configuração: variáveis de ambiente + services.yaml (relido a cada request)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent

SERVICES_FILE = Path(os.environ.get("DASH_SERVICES", BASE_DIR / "services.yaml"))
DOCS_FILE = Path(os.environ.get("DASH_DOCS", BASE_DIR / "docs.md"))
DB_PATH = Path(os.environ.get("DASH_DB", BASE_DIR / "data" / "metrics.db"))

# Intervalo entre amostras de temperatura (padrão: 30 min).
SAMPLE_SECONDS = int(os.environ.get("DASH_SAMPLE_SECONDS", "1800"))
# Amostras mais antigas que isso são apagadas.
RETENTION_DAYS = int(os.environ.get("DASH_RETENTION_DAYS", "90"))


def load_config() -> dict:
    """Lê o services.yaml. Relido a cada chamada: editar o arquivo não exige restart."""
    with open(SERVICES_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("services", [])
    data.setdefault("disks", [])
    data.setdefault("mounts", ["/"])
    data.setdefault("ignore_ports", [])
    return data


def parse_port(spec: str | int) -> tuple[int, str]:
    """'8080/tcp' -> (8080, 'tcp'); '8080' -> (8080, 'tcp')."""
    port, _, proto = str(spec).partition("/")
    return int(port), (proto or "tcp").lower()
