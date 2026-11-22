# Analizador de mercados

Detección de señales de compra/venta y backtesting para **S&P 500, Nasdaq 100, oro y cripto (BTC, ETH)**.

Estado: **paso 2 de 4 — señales y backtesting.** Web: https://darkshadowdata.github.io/Analizador-de-Mercados/

| Paso | Qué | Estado |
|---|---|---|
| 1 | Datos OHLCV (con volumen) + web con gráficos | ✅ |
| 2 | Señales (RSI, perfil de volumen anclado, Wyckoff) + backtesting | ✅ primera versión |
| 3 | Reportes automáticos diarios en la web | pendiente |
| 4 | Trading automático en la cuenta demo de Bitget | pendiente |

## Cómo funciona

```
GitHub Actions (cada hora)
  └─ scripts/actualizar_datos.py
       ├─ Yahoo Finance: ES=F, NQ=F, GC=F (futuros: traen volumen real)
       ├─ Bitget API pública: BTCUSDT, ETHUSDT (si falla, Yahoo BTC-USD / ETH-USD)
       ├─ data/<mercado>/<1h|4h|1d>.csv   ← histórico completo, crece con cada corrida
       └─ docs/data/*.json                ← lo que lee la web
  └─ publica docs/ en GitHub Pages
```

- **Por qué futuros y no el índice:** `^GSPC` y `^NDX` no tienen volumen negociado real, y el perfil de volumen y Wyckoff dependen de él. Los futuros E-mini (y el de oro de COMEX) sí lo tienen.
- **Temporalidades:** 1h, 4h y diario. Yahoo solo da 730 días de velas de 1 hora; como el histórico se guarda en el repo, a partir de ahora va creciendo.
- **Cripto en vivo:** la web se conecta al WebSocket público de Bitget y mueve la última vela con el precio en tiempo real.
- No se mezclan fuentes: si un día Bitget falla y responde Yahoo, ese día no se toca el histórico de Bitget (el volumen no es comparable).

## Señales (paso 2)

- `analizador/indicadores.py`: RSI 14 (Wilder), ATR, pivotes y **perfil de volumen anclado** al último giro importante confirmado (POC, VAH, VAL). Sin mirar al futuro.
- `analizador/senales.py`: **spring**, **upthrust** y **test** de Wyckoff dentro de rangos laterales. Cada señal suma puntos (1 a 4) si la confirman el RSI, el perfil de volumen y el volumen.
- `analizador/backtest.py`: entra en la apertura siguiente, stop 1 ATR tras el extremo, objetivo al otro lado del área de valor (1R a 3R), solo a favor de la media de 200, con comisiones.
- `scripts/generar_senales.py`: genera `docs/data/analisis_*.json` y `docs/data/resumen_senales.json` para la web (y para los pasos 3 y 4).

**Resultados (22 nov 2026):** con rango de 40 velas, en conjunto no había ventaja (~−0,1R por operación). Con **rango de 30 velas en 4H** sale positivo en el histórico antiguo (+0,26R) y en el reciente (+0,24R), con ~55 % de aciertos; casi toda la ganancia viene de ETH 4H. 1H es negativo con cualquier rango (las comisiones pesan más). La demo opera solo 4H. No usar con dinero real hasta validarlo en demo.

## Usarlo en tu PC (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python scripts/actualizar_datos.py          # descarga todo
python scripts/generar_senales.py           # señales + backtest
python -m http.server 8000 -d docs          # abre http://localhost:8000
```

## Para los siguientes pasos

```python
from analizador.almacen import cargar
df = cargar("btc", "4h")   # DataFrame: índice UTC, columnas open high low close volume
```

Mercados en `analizador/mercados.py` (añadir uno = una entrada en la lista).

## Pruebas

```bash
python -m pytest -q
```

Gráficos: [Lightweight Charts](https://github.com/tradingview/lightweight-charts) de TradingView (Apache 2.0), incluido en `docs/vendor/`.
Solo informativo, no es consejo financiero.
