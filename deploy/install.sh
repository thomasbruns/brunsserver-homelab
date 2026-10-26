#!/usr/bin/env bash
# Instala o dashboard como serviço systemd. Rode no brunsserver, a partir da raiz do repo:
#   ./deploy/install.sh                      # usa os padrões abaixo
#   BIND=100.80.165.68 PORT=8088 ./deploy/install.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_USER="${RUN_USER:-$USER}"
BIND="${BIND:-$(tailscale ip -4 2>/dev/null | head -n1 || true)}"
PORT="${PORT:-8088}"

if [[ -z "$BIND" ]]; then
  echo "Não consegui descobrir o IP do Tailscale. Rode com BIND=<ip> ./deploy/install.sh" >&2
  exit 1
fi

echo ">> venv + dependências"
python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/pip" install -q -r "$REPO/requirements.txt"

echo ">> unit systemd (user=$RUN_USER bind=$BIND:$PORT)"
sed -e "s|%USER%|$RUN_USER|g" -e "s|%REPO%|$REPO|g" -e "s|%BIND%|$BIND|g" -e "s|%PORT%|$PORT|g" \
  "$REPO/deploy/brunsserver-dashboard.service" | sudo tee /etc/systemd/system/brunsserver-dashboard.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now brunsserver-dashboard

echo ">> pronto: http://$BIND:$PORT"
id -nG "$RUN_USER" | grep -qw docker || \
  echo "!! $RUN_USER não está no grupo docker: o status dos containers aparecerá como 'desconhecido'." \
       "Corrija com: sudo usermod -aG docker $RUN_USER (e relogue)"
