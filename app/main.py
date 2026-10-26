from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import markdown
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import config, db
from .collectors import ports, services, system

log = logging.getLogger("dashboard")
templates = Jinja2Templates(directory=str(config.BASE_DIR / "app" / "templates"))

NAV = [
    ("services", "/", "Serviços"),
    ("server", "/server", "Servidor"),
    ("docs", "/docs", "Documentação"),
]


def take_sample() -> None:
    cfg = config.load_config()
    db.insert_sample(system.snapshot(cfg["disks"], cfg["mounts"]))


async def sampler() -> None:
    """Grava uma amostra ao subir e depois a cada SAMPLE_SECONDS."""
    while True:
        try:
            await asyncio.to_thread(take_sample)
        except Exception:  # o logger nunca pode derrubar o app
            log.exception("falha ao coletar amostra")
        await asyncio.sleep(config.SAMPLE_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    task = asyncio.create_task(sampler())
    yield
    task.cancel()
    db.close()


# Sem swagger/openapi: a rota /docs é a nossa página de documentação.
app = FastAPI(title="brunsserver dashboard", lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "app" / "static")), name="static")


def page(request: Request, name: str, active: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(
        request, f"{name}.html", {"nav": NAV, "active": active, **ctx}
    )


# ---------- páginas ----------

@app.get("/", response_class=HTMLResponse)
def page_services(request: Request):
    return page(request, "services", "services")


@app.get("/server", response_class=HTMLResponse)
def page_server(request: Request):
    return page(request, "server", "server", interval_min=config.SAMPLE_SECONDS // 60)


@app.get("/docs", response_class=HTMLResponse)
def page_docs(request: Request):
    cfg = config.load_config()
    try:
        extra = markdown.markdown(config.DOCS_FILE.read_text(encoding="utf-8"),
                                  extensions=["tables", "fenced_code"])
    except OSError:
        extra = "<p><em>docs.md não encontrado.</em></p>"
    return page(request, "docs", "docs", services=cfg["services"], extra_html=extra)


# ---------- API ----------

@app.get("/api/services")
def api_services():
    cfg = config.load_config()
    out = []
    for svc in cfg["services"]:
        status = services.check_service(svc)
        out.append({
            **status,
            "description": svc.get("description", ""),
            "ports": svc.get("ports", []),
            "web_port": svc.get("web_port"),
            "web_path": svc.get("web_path", "/"),
        })
    return out


@app.get("/api/system")
def api_system():
    cfg = config.load_config()
    return system.snapshot(cfg["disks"], cfg["mounts"])


@app.get("/api/temps")
def api_temps(hours: int = Query(24, ge=1, le=24 * 90)):
    return {"interval_seconds": config.SAMPLE_SECONDS, "samples": db.query(hours)}


@app.get("/api/ports")
def api_ports():
    return ports.check_ports(config.load_config())
