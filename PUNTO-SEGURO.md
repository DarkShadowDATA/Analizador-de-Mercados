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

## 22-nov (noche): más operaciones (Alejandro eligió "Las dos")
- [x] 4H en 19 criptos extra de Bitget (scripts/backtest_extra_4h.py). Positivas en las dos mitades: OP, INJ, BCH, SUI -> añadidas a MERCADOS y a la cartera 4H (solo papel). Promedio de las 19 ~0R: hay sesgo de selección.
- [x] Experimento 5m: analizador/rango_asia.py (falsa ruptura del rango asiático 00-08 UTC, señales 08-20 UTC, stop >= 0,4 %, objetivo el otro lado, cierre 23:55). En CARTERA BTC/ETH 5m con Bitget demo; la 4H tiene prioridad sobre el contrato. Cuenta aparte (capital_experimento). Backtest -0,26/-0,37R.
- [x] Workflow demo-5m.yml cada 5 min (velas_5m.py + operar_demo.py); la corrida horaria ya no opera.
- [ ] Verificar el lunes 23 que entren las primeras operaciones de 5m; claves de Bitget siguen pendientes.
