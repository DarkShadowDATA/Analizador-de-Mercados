# Tarea: Paso 2 — señales (RSI + perfil de volumen anclado + Wyckoff) y backtesting
Empezó: 2026-11-21 16:47 UTC · Estado: en curso
Pedido: "Podemos avanzar al paso 2 mientras esperamos? ... dejarlo operativo esta semana, desde el lunes"

## Decisiones tomadas (no volver a preguntar)
- Sin MACD. RSI(14) Wilder.
- Perfil de volumen anclado al último pivote mayor confirmado (sin mirar al futuro).
- Wyckoff: spring / upthrust (falsa ruptura que cierra de vuelta dentro del rango) y test (retroceso con menos volumen).
- Entrada en la apertura de la vela siguiente; stop tras el extremo de la falsa ruptura; objetivo en el otro lado del área de valor (mín. 1,5R).
- Largos y cortos (Bitget demo permite cortos en futuros).

## Pasos
- [x] 1. Indicadores (analizador/indicadores.py)
- [x] 2. Detector Wyckoff (analizador/senales.py)
- [x] 3. Backtest (analizador/backtest.py). Resultado honesto: sin ventaja (~-0,1R por operación con costos). Config por defecto: pm3, filtro SMA200, stop 1 ATR, 1-3R
- [x] 3b. scripts/generar_senales.py (JSON para la web)
- [x] 4. Web: marcas, niveles, RSI, tabla de resultados (docs/analisis.js)
- [ ] 5. Workflow + publicar ← SIGUIENTE

## Paso 1 (terminado 2026-11-21)
Web: https://darkshadowdata.github.io/Analizador-de-Mercados/ · datos cada hora por Actions.

## Para retomar
- `pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
- Los datos reales ya están en data/*.csv (la máquina de Claude no llega a Yahoo/Bitget).
