#!/bin/bash
# =============================================================================
# setup-server.sh — Configuració inicial d'un servidor nou
# Executa una sola vegada després de clonar el repositori.
# Requereix: Debian/Ubuntu, Docker, docker compose
# =============================================================================
set -euo pipefail

echo "=== Configuració del servidor Gestor Substitucions ==="

# -----------------------------------------------------------------------------
# 1. Límits de logs del sistema (journald)
# -----------------------------------------------------------------------------
echo ""
echo "1) Configurant límits de journald..."

cat > /etc/systemd/journald.conf.d/limits.conf << 'EOF'
[Journal]
SystemMaxUse=200M
SystemKeepFree=500M
MaxRetentionSec=1month
EOF

mkdir -p /etc/systemd/journald.conf.d
systemctl restart systemd-journald
echo "   OK — journald limitat a 200M, retenció màxima 1 mes"

# -----------------------------------------------------------------------------
# 2. Logrotate per als logs de l'aplicació
# -----------------------------------------------------------------------------
echo ""
echo "2) Configurant logrotate per a logs de l'app..."

cat > /etc/logrotate.d/gestor << 'EOF'
/var/log/gestor*.log {
    weekly
    rotate 4
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
EOF

echo "   OK — logs /var/log/gestor*.log: rotació setmanal, 4 setmanes, comprimit"

# -----------------------------------------------------------------------------
# 3. Cron setmanal per netejar imatges Docker antigues
# -----------------------------------------------------------------------------
echo ""
echo "3) Configurant cron de neteja Docker..."

CRON_FILE="/etc/cron.weekly/docker-prune"
cat > "$CRON_FILE" << 'EOF'
#!/bin/bash
# Elimina imatges i contenidors Docker de més de 7 dies (no els actius)
docker system prune -f --filter "until=168h" >> /var/log/docker-prune.log 2>&1
EOF

chmod +x "$CRON_FILE"
echo "   OK — neteja Docker cada diumenge (imatges >7 dies)"

# -----------------------------------------------------------------------------
# 4. Neteja immediata de l'espai actual
# -----------------------------------------------------------------------------
echo ""
read -r -p "4) Netejar imatges Docker no usades ara mateix? [s/N] " resposta
if [[ "${resposta,,}" == "s" ]]; then
    docker system prune -f --filter "until=168h"
    echo "   OK — espai alliberat"
else
    echo "   Omès"
fi

# -----------------------------------------------------------------------------
# Resum
# -----------------------------------------------------------------------------
echo ""
echo "=== Configuració completada ==="
echo "   journald : màx 200M, 1 mes de retenció"
echo "   logrotate: setmanal, 4 setmanes, comprimit"
echo "   docker   : neteja automàtica cada diumenge"
echo ""
echo "Pròxim pas: docker compose up -d --build"
