"""Backtest de la estrategia Wyckoff de 4H (mismas reglas que la demo) en criptos extra de Bitget.

Lee data/intradia/<simbolo>_4h.csv.gz (workflow "Descargar velas intradía" con dias=extra4h).
Uso: python scripts/backtest_extra_4h.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from analizador import backtest, indicadores, senales  # noqa: E402

DIR = Path(__file__).resolve().parent.parent / "data" / "intradia"


def evaluar(df: pd.DataFrame) -> dict:
    x = indicadores.calcular(df)
    lista = senales.detectar(df, senales.Parametros(), x)
    ops = [o for o in backtest.simular(df, lista, "cripto", backtest.ReglasBT()) if o.motivo_salida != "abierta"]
    corte = df.index[len(df) // 2].strftime("%Y-%m-%d")
    m = lambda xs: backtest.metricas(xs, backtest.ReglasBT())
    anios = (df.index[-1] - df.index[0]).days / 365
    return {"anios": round(anios, 1), "total": m(ops),
            "1a": m([o for o in ops if o.fecha_entrada < corte]), "2a": m([o for o in ops if o.fecha_entrada >= corte])}


def main() -> int:
    filas = []
    for ruta in sorted(DIR.glob("*_4h.csv.gz")):
        df = pd.read_csv(ruta, index_col="fecha")
        df.index = pd.to_datetime(df.index, utc=True)
        if len(df) < 1000:
            continue
        r = evaluar(df)
        t, a, b = r["total"], r["1a"], r["2a"]
        filas.append((ruta.name.split("_")[0].upper(), r["anios"], t.get("operaciones", 0), t.get("aciertos_pct"),
                      t.get("r_medio"), a.get("r_medio"), b.get("r_medio")))
    print(f"{'símbolo':10} años  ops  acierto  R medio  1ª mitad  2ª mitad")
    for f in sorted(filas, key=lambda f: -(f[4] or -9)):
        print(f"{f[0]:10} {f[1]:4} {f[2]:4}  {f[3]}%  {f[4]}  {f[5]}  {f[6]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
