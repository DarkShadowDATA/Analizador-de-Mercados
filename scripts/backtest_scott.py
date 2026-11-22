"""Backtest de la estrategia de ScottFDX (analizador/scott.py) sobre 1 año de velas de 5m
de BTC y ETH (data/intradia/*.csv.gz, bajadas con scripts/descargar_intradia.py).

Uso:  python scripts/backtest_scott.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from analizador import scott  # noqa: E402

VARIANTES = {
    "base (k=5)": {},
    "sin costos": dict(comision_limite=0, comision_mercado=0, deslizamiento=0),
    "pivote k=3": dict(k=3),
    "pivote k=10": dict(k=10),
    "EMA en escalera 15m": dict(escalera="15min"),
    "stop >= 0,5 %": dict(riesgo_min_pct=0.5),
    "solo largos": dict(solo=1),
    "solo cortos": dict(solo=-1),
    # Reglas reales del indicador "EMA y Pivotes ZS" (niveles de 400 min, 22-nov-2026)
    "ZS bloque en curso": dict(niveles="acumulado"),
    "ZS bloque anterior": dict(niveles="anterior"),
    "ZS anterior, stop 0,5 ATR": dict(niveles="anterior", colchon_atr=0.5),
    "ZS anterior, sin costos": dict(niveles="anterior", colchon_atr=0.5,
                                    comision_limite=0, comision_mercado=0, deslizamiento=0),
}


def main() -> int:
    raiz = Path(__file__).resolve().parent.parent / "data" / "intradia"
    for mid in ("btc", "eth"):
        df = pd.read_csv(raiz / f"{mid}_5m.csv.gz", index_col="fecha")
        df.index = pd.to_datetime(df.index, utc=True)
        corte = df.index[len(df) // 2]
        for nombre, kw in VARIANTES.items():
            res = scott.resumen(scott.simular(df, scott.ParamsScott(**kw)), corte)
            print(f"{mid} {nombre:22} {res}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
