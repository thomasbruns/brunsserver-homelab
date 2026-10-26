# brunsserver-homelab

Dashboard web do brunsserver, pensado para abrir no celular via Tailscale. FastAPI + SQLite, sem build de frontend.

Três páginas no menu:

| Página | O que mostra |
|---|---|
| **Serviços** (`/`) | Cards verde/vermelho por serviço: estado, há quanto tempo está no ar, portas, botão "abrir". Avisa se há porta escutando sem estar documentada (ou documentada sem ninguém escutando). |
| **Servidor** (`/server`) | Temperatura da CPU e dos discos, carga, RAM, uso dos pontos de montagem (avisa se `/mnt/hdd` não está montado) e gráfico de temperatura de 24h / 7 dias / 30 dias. |
| **Documentação** (`/docs`) | Tabela de portas e fichas de cada serviço (dados, como reiniciar, logs, backup, notas), mais o `docs.md` renderizado (hardware, rede, backup, o que fazer se o servidor parar). |

## Como funciona

Tudo gira em torno de **um arquivo**: `services.yaml`. Ele define o que é monitorado *e* o que aparece na documentação, então os dois não se desencontram. Ele é relido a cada request: editar não exige restart. O texto livre fica em `docs.md`, também sem restart.

O app grava uma amostra (temperatura, carga, RAM, disco) ao subir e depois a cada 30 min (`DASH_SAMPLE_SECONDS`), guardando 90 dias (`DASH_RETENTION_DAYS`).

## Instalar no brunsserver

```bash
git clone <seu-remoto> ~/brunsserver-homelab && cd ~/brunsserver-homelab
./deploy/install.sh        # venv, deps, unit systemd, enable --now
```

O script descobre o IP do Tailscale e faz o app escutar **só nele**, porta 8088 (a 8080 é do Nextcloud). Abra `http://brunsserver:8088` no celular. Para outro IP/porta: `BIND=... PORT=... ./deploy/install.sh`.

Não há login: a proteção é escutar apenas na interface do Tailscale. Não troque `BIND` por `0.0.0.0`.

### Permissões

- **Docker:** o usuário precisa estar no grupo `docker` (o install avisa). Sem isso os containers aparecem como "desconhecido".
- **Temperatura dos discos:** `smartctl` exige root. Crie `/etc/sudoers.d/dashboard-smartctl` com `sudo visudo -f` e uma linha por disco:
  ```
  thomasbruns ALL=(root) NOPASSWD: /usr/sbin/smartctl -j -A /dev/sda, /usr/sbin/smartctl -j -A /dev/sdb
  ```
  Ajuste os dispositivos em `disks:` no `services.yaml` (veja com `lsblk`). Sem isso o gráfico mostra só a CPU.
- **Zomboid:** roda como `pzuser`, então o status vem de `pgrep` (kind `process`), sem sudo.

### Ajustes depois da primeira subida

Os itens marcados `CONFIRMAR` no `services.yaml` foram preenchidos com padrões: nomes dos containers do Immich, porta do Immich (2283), se o go2rtc é systemd ou Docker, padrão do processo do Zomboid e os discos. Confira com:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
pgrep -fa Zomboid
ss -tuln
lsblk
```

## Desenvolvimento

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
.venv/bin/uvicorn app.main:app --reload --port 8088
```

Fora do servidor real, os serviços aparecem como "desconhecido"/"não encontrado" e a temperatura da CPU fica vazia: é esperado.

## Estrutura

```
app/
  main.py            rotas (páginas + /api/*) e o logger em background
  config.py          variáveis de ambiente e leitura do services.yaml
  db.py              SQLite (data/metrics.db)
  collectors/        services.py (systemd/docker/processo), system.py, ports.py
  templates/ static/ HTML, CSS, JS e Chart.js local (funciona sem internet)
deploy/              unit do systemd e install.sh
services.yaml        fonte da verdade
docs.md              texto livre da página Documentação
tests/
```

## API

`GET /api/services` · `/api/system` · `/api/temps?hours=24` · `/api/ports`
