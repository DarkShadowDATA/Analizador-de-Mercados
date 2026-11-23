#!/usr/bin/env bash
# Bucle de la demo dentro de un solo job de GitHub Actions (los cron de GitHub se retrasan horas).
# Cada 5 minutos: velas de 5m + operar_demo + commit. Cada hora (minuto >= 17): lanza
# "Actualizar datos y publicar web". Al terminar (~5,5 h) se relanza a sí mismo.
set -u
FIN=$(( $(date +%s) + ${DURACION_MIN:-330} * 60 ))
ULTIMA_HORA=""
git config user.name "analizador-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
while [ "$(date +%s)" -lt "$FIN" ]; do
  git pull -q --rebase origin main || git rebase --abort || true
  python scripts/velas_5m.py || echo "fallo velas_5m"
  python scripts/operar_demo.py || echo "fallo operar_demo"
  git add data/btc/5m.csv data/eth/5m.csv data/demo docs/data/demo.json
  if ! git diff --cached --quiet; then
    git commit -q -m "Demo $(date -u +'%Y-%m-%d %H:%M') UTC"
    for i in 1 2 3; do git pull -q --rebase origin main && git push -q && break; sleep 5; done
  fi
  HORA=$(date -u +%H); MIN=$(date -u +%M)
  if [ "$HORA" != "$ULTIMA_HORA" ] && [ "$((10#$MIN))" -ge 17 ]; then
    gh workflow run actualizar-datos.yml --ref main -R "$GITHUB_REPOSITORY" && ULTIMA_HORA=$HORA
  fi
  # dormir hasta 1 minuto después del próximo múltiplo de 5 minutos (vela recién cerrada)
  AHORA=$(date +%s); SIG=$(( (AHORA / 300 + 1) * 300 + 60 ))
  sleep $(( SIG - AHORA ))
done
gh workflow run demo-5m.yml --ref main -R "$GITHUB_REPOSITORY"
