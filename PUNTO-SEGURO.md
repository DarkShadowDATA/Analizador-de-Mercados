# Tarea: Paso 4 — operar señales en demo (Bitget + cartera simulada) y probar reglas nuevas
Empezó: 2026-11-21 19:56 UTC · Estado: en curso
Decisión de Alejandro: "Las dos cosas a la vez" (demo desde el lunes 23-nov con lo positivo + probar reglas de ScottFDX/ZcoinTv).

## Decisiones tomadas (no volver a preguntar)
- Bitget demo (SUSDT-FUTURES) solo tiene SBTCSUSDT y SETHSUSDT: S&P, Nasdaq y oro van en cartera simulada propia.
- Cartera: ETH 4H (Bitget demo SETHSUSDT), oro 4H, S&P 500 1D, Nasdaq 1H. Señales desde 2026-11-23 00:00 UTC.
- Claves como GitHub secrets BITGET_API_KEY / BITGET_API_SECRET / BITGET_PASSPHRASE.
- Riesgo 1 % por operación, margen aislado, apalancamiento 5, stop y objetivo puestos en Bitget.

## Pasos
- [x] 1. Revisar contratos Bitget (scripts/bitget_contratos.py, workflow diagnostico.yml)
- [x] 2. analizador/bitget_api.py + analizador/demo.py + scripts/operar_demo.py (19 pruebas pasan)
- [x] 3. Sección "Cuenta demo" en la web
- [ ] 4. Probar con las claves reales de la demo ← SIGUIENTE (esperando a Alejandro)
- [ ] 5. Probar reglas de ScottFDX / ZcoinTv (esperando que las pase)

## Paso 1 (terminado 2026-11-21)
Web: https://darkshadowdata.github.io/Analizador-de-Mercados/ · datos cada hora por Actions.

## Para retomar
- `pip install -r requirements.txt -r requirements-dev.txt && python -m pytest -q`
- Los datos reales ya están en data/*.csv (la máquina de Claude no llega a Yahoo/Bitget).
