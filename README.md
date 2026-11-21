# Analizador de mercados

Detección de señales de compra/venta y backtesting para **S&P 500, Nasdaq 100, oro y cripto (BTC, ETH)**.

Estado: **paso 1 de 4 — datos y web con gráficos.** Web: https://darkshadowdata.github.io/Analizador-de-Mercados/

| Paso | Qué | Estado |
|---|---|---|
| 1 | Datos OHLCV (con volumen) + web con gráficos | ✅ este repo |
| 2 | Señales (RSI, perfil de volumen anclado, Wyckoff) + backtesting | pendiente |
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

## Usarlo en tu PC (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python scripts/actualizar_datos.py          # descarga todo
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
