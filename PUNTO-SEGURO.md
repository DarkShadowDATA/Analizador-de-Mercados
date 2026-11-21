# Tarea: Paso 1 del analizador — datos + web base ("Va")
Empezó: 2026-11-21 13:47 UTC · Actualizado: 2026-11-21 · Estado: en curso

## Decisiones tomadas (no volver a preguntar)
- Repo: DarkShadowDATA/Analizador-de-Mercados (lo creó Alejandro).
- Índices y oro con futuros de Yahoo (ES=F, NQ=F, GC=F) por el volumen real.
- Cripto con Bitget API pública (BTCUSDT, ETHUSDT), respaldo Yahoo.
- Temporalidades 1h, 4h (remuestreo de 1h en Yahoo), 1d.
- Datos los baja GitHub Actions cada hora y se guardan en el repo; web estática en docs/ (GitHub Pages).
- Nada de MACD.

## Pasos
- [x] 1. Código: descarga, almacén, script, web, pruebas (8 pasan)
- [ ] 2. Subir a GitHub y activar Pages ← SIGUIENTE
- [ ] 3. Primera corrida del workflow con datos reales y revisar la web
- [ ] 4. Entregar a Alejandro

## Para retomar
- Código en el repo. `pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
- La máquina de Claude no llega a Yahoo/Bitget (proxy): los datos reales solo se prueban en Actions.
