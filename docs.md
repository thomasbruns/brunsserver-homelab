Edite este arquivo direto no servidor (`docs.md`): a página renderiza na hora, sem restart.
**Não coloque senhas aqui**, só *onde* elas estão guardadas.

### Hardware

| Item | Detalhe |
|---|---|
| Máquina | Dell OptiPlex 7010 |
| CPU | Intel i7-3770 (4 núcleos / 8 threads) |
| Fonte | ATX genérica 250 W (não é a original da Dell) |
| Disco do sistema | SSD 240 GB, LVM |
| Disco de backup | HD em `/mnt/hdd` (ext4, label `backup`, montagem por UUID com `nofail`) |
| SO | Ubuntu Server 24.04 LTS |

### Rede e acesso

- Acesso remoto só pelo **Tailscale** (IP `100.80.165.68`), usuário SSH `thomasbruns`.
- O roteador é gerenciado pela operadora (sem acesso de admin): nada é exposto na internet.
- Os amigos entram no Zomboid via compartilhamento de máquina do Tailscale.

### Backup

- **restic** todo dia às **3h** (cron do root), script `/home/thomasbruns/backup.sh`, log em `backup.log`.
- Repositório: `/mnt/hdd/restic-repo`. Senha em `/root/.restic-pass`; há uma cópia no gerenciador de senhas.
- Tags: `nextcloud`, `zomboid` (`/home/pzuser/Zomboid`) e `sistema` (`/etc`, `/usr/local/bin`, `/var/lib/tailscale`, crontab, `go2rtc.yaml`).
- O script confere se `/mnt/hdd` está montado e avisa por e-mail (msmtp/Gmail) se falhar.

```bash
sudo restic -r /mnt/hdd/restic-repo --password-file /root/.restic-pass snapshots
```

### Alertas

- smartmontools monitora os dois discos.
- Aviso por e-mail quando o uso de disco passa de 85%.

### Se o servidor parar

1. Veja se aparece no Tailscale; se não, vá até a máquina (vídeo/teclado).
2. Em caso de reboot inesperado, confira temperatura e fonte (histórico na página **Servidor**).
3. Depois de religar: `docker ps`, `systemctl --failed` e a página **Serviços** deste dashboard.
