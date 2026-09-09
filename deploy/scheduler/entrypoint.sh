#!/bin/sh
set -e

# Resolve KIOSK_API_KEY aqui (no shell do entrypoint) em vez de deixar o cron
# tentar expandir a variável — evita depender de como cada cron passa o
# ambiente do container pros jobs.
cat > /etc/crontabs/root <<EOF
0 0 * * * curl -fsS -X POST -H "X-Kiosk-Key: ${KIOSK_API_KEY}" http://api:8000/api/repor-estoque
2 0 * * * curl -fsS -X POST -H "X-Kiosk-Key: ${KIOSK_API_KEY}" http://api:8000/api/limpar-expirados
EOF

exec busybox crond -f -l 2
