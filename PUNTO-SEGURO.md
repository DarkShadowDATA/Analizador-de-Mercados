# Tarea: Paso 4 — operar señales en demo (Bitget + cartera simulada) y probar reglas nuevas
Empezó: 2026-11-21 19:56 UTC · Estado: en curso
Decisión de Alejandro: "Las dos cosas a la vez" (demo desde el lunes 23-nov con lo positivo + probar reglas de ScottFDX/ZcoinTv).

## Decisiones tomadas (no volver a preguntar)
- Bitget demo (SUSDT-FUTURES) solo tiene SBTCSUSDT y SETHSUSDT: S&P, Nasdaq y oro van en cartera simulada propia.
- 22-nov: rango de 30 velas. Cartera solo 4H: ETH y BTC (Bitget demo), oro, S&P 500, Nasdaq (simulados). Señales desde 2026-11-23 00:00 UTC.
- Claves como GitHub secrets BITGET_API_KEY / BITGET_API_SECRET / BITGET_PASSPHRASE.
- Riesgo 1 % por operación, margen aislado, apalancamiento 5, stop y objetivo puestos en Bitget.

## Pasos
- [x] 1. Revisar contratos Bitget (scripts/bitget_contratos.py, workflow diagnostico.yml)
- [x] 2. analizador/bitget_api.py + analizador/demo.py + scripts/operar_demo.py (19 pruebas pasan)
- [x] 3. Sección "Cuenta demo" en la web
- [ ] 4. Probar con las claves reales de la demo ← SIGUIENTE (esperando a Alejandro)
- [x] 5a. ScottFDX (video KddTTcjBHPI, 22-nov): analizador/scott.py + scripts/backtest_scott.py. 1 año 5m BTC/ETH: sin costos ~0R, con costos −0,3/−0,5R; TP1 solo ~35 % (no 75 %). Ninguna variante positiva (k3/k10, escalera 15m, stop mín 0,5 %, solo largos/cortos, filtro EMA200 1h).
- [x] 5b. Reglas reales del indicador ZS (niveles = máx/mín de bloques de 400 min desde 00:00 UTC; alerta = toca nivel y cierra al otro lado de la EMA12): niveles='acumulado'/'anterior' en scott.py. Sin costos −0,3 a +0,05R; con costos −0,4 a −10R (stops minúsculos). Sin ventaja.
- [ ] 5c. ZcoinTv / más material de ScottFDX (indicador "pupú", filtro de acumulación en 1H) si Alejandro lo pasa

## Paso 1 (terminado 2026-11-21)
Web: https://darkshadowdata.github.io/Analizador-de-Mercados/ · datos cada hora por Actions.

## Para retomar
- `pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
- Los datos reales ya están en data/*.csv (la máquina de Claude no llega a Yahoo/Bitget).
