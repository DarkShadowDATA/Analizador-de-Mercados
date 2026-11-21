# Tarea: Paso 1 del analizador — datos + web base ("Va")
Empezó: 2026-11-21 13:47 UTC · Actualizado: 2026-11-21 · Estado: terminada

## Decisiones tomadas (no volver a preguntar)
- Repo: DarkShadowDATA/Analizador-de-Mercados (lo creó Alejandro).
- Índices y oro con futuros de Yahoo (ES=F, NQ=F, GC=F) por el volumen real.
- Cripto con Bitget API pública (BTCUSDT, ETHUSDT), respaldo Yahoo.
- Temporalidades 1h, 4h (remuestreo de 1h en Yahoo), 1d.
- Datos los baja GitHub Actions cada hora y se guardan en el repo; web estática en docs/ (GitHub Pages).
- Nada de MACD.

## Pasos
- [x] 1. Código: descarga, almacén, script, web, pruebas (8 pasan)
- [x] 2. Subido a GitHub; datos reales OK en Actions (Bitget + Yahoo)
- [x] 2b. Repo público y Pages activo: https://darkshadowdata.github.io/Analizador-de-Mercados/
- [x] 3. Corridas con datos reales OK (Bitget + Yahoo, 0 fallos)
- [x] 4. Entregado. Siguiente: paso 2 (señales + backtesting) cuando Alejandro lo apruebe

## Para retomar
- Código en el repo. `pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
- La máquina de Claude no llega a Yahoo/Bitget (proxy): los datos reales solo se prueban en Actions.
