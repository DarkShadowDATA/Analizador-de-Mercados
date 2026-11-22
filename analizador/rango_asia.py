"""Experimento intradía de 5 minutos: falsa ruptura del rango asiático (Wyckoff aplicado al día).

Reglas (BTC y ETH, velas de 5 min, horas UTC):
  1. Rango asiático = máximo y mínimo de 00:00 a 08:00.
  2. De 08:00 a 20:00, si el precio perfora el mínimo (o el máximo) y una vela CIERRA de vuelta
     dentro del rango, se entra en la apertura de la vela siguiente (spring / upthrust del día).
  3. La perforación no puede pasar del 50 % del ancho del rango (más es ruptura real).
  4. Stop: 0,1 ATR más allá del extremo de la perforación, y como mínimo a 0,4 % de la entrada
     (con stops más cortos la comisión se come la operación).
  5. Objetivo: el otro lado del rango asiático. Lo que siga abierto se cierra a las 23:55.
  6. Una operación por lado y por día; una a la vez.

Backtest de 1 año (22-nov-2026, scripts/ideas_5m.py): con comisiones de mercado -0,2 a -0,3R
por operación. Se corre en la demo como EXPERIMENTO para tener operaciones diarias, no porque gane.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .backtest import Operacion
from .indicadores import atr as calc_atr

SEG_VELA = 300


@dataclass
class ParamsAsia:
    fin_asia: int = 8          # hora UTC en que termina el rango
    desde: int = 8             # ventana de señales [desde, hasta)
    hasta: int = 20
    perf_max: float = 0.5      # perforación máxima en fracción del rango
    colchon_atr: float = 0.1
    stop_min_pct: float = 0.4
    costo_lado: float = 0.0008  # Bitget taker + deslizamiento (stop y objetivo salen a mercado)


def cerradas(df: pd.DataFrame, ahora: pd.Timestamp | None = None) -> pd.DataFrame:
    ahora = ahora if ahora is not None else pd.Timestamp.now(tz="UTC")
    return df[df.index + pd.Timedelta(seconds=SEG_VELA) <= ahora]


def senales(df: pd.DataFrame, p: ParamsAsia | None = None) -> list[tuple[int, int, float, float]]:
    """(posición de la vela de señal, dirección, extremo de la perforación, objetivo). Solo velas dadas."""
    p = p or ParamsAsia()
    h, l, c = (df[k].to_numpy() for k in ("high", "low", "close"))
    hora = df.index.hour.to_numpy()
    dia = df.index.floor("D")
    out = []
    for _, pos in pd.Series(np.arange(len(df)), index=df.index).groupby(dia):
        pos = pos.to_numpy()
        asia = pos[hora[pos] < p.fin_asia]
        if len(asia) < p.fin_asia * 12 * 0.9:   # faltan velas del rango
            continue
        H, L = h[asia].max(), l[asia].min()
        ancho = H - L
        hechos: set[int] = set()
        ext: dict[int, float | None] = {1: None, -1: None}
        for t in pos[(hora[pos] >= p.desde) & (hora[pos] < p.hasta)]:
            for d in (1, -1):
                if d in hechos:
                    continue
                if d == 1 and l[t] < L:
                    ext[1] = l[t] if ext[1] is None else min(ext[1], l[t])
                if d == -1 and h[t] > H:
                    ext[-1] = h[t] if ext[-1] is None else max(ext[-1], h[t])
                e = ext[d]
                if e is None:
                    continue
                if abs(e - (L if d == 1 else H)) > p.perf_max * ancho:
                    hechos.add(d)
                    continue
                if (c[t] > L) if d == 1 else (c[t] < H):
                    out.append((int(t), d, float(e), float(H if d == 1 else L)))
                    hechos.add(d)
    return sorted(out)


def simular(df: pd.DataFrame, desde: str | pd.Timestamp | None = None, p: ParamsAsia | None = None,
            ahora: pd.Timestamp | None = None) -> list[Operacion]:
    """Operaciones en papel. `df` puede traer la vela abierta (se usa su apertura para entrar)."""
    p = p or ParamsAsia()
    if df.empty:
        return []
    cerr = cerradas(df, ahora)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = calc_atr(df).to_numpy()
    n, n_cerr = len(df), len(cerr)
    fmt = lambda i: df.index[i].strftime("%Y-%m-%dT%H:%M:%SZ")
    dia = df.index.floor("D")
    inicio = pd.Timestamp(desde) if desde is not None else None
    ops: list[Operacion] = []
    libre = 0
    for t, d, ext, obj in senales(cerr, p):
        if t < libre or t + 1 >= n or (inicio is not None and df.index[t] < inicio):
            continue
        e = o[t + 1]
        colchon = p.colchon_atr * (a[t] if np.isfinite(a[t]) else 0)
        stop = ext - colchon if d == 1 else ext + colchon
        if (e - stop) * d < e * p.stop_min_pct / 100:
            stop = e - d * e * p.stop_min_pct / 100
        riesgo = (e - stop) * d
        if riesgo <= 0 or (obj - e) * d <= 0:
            continue
        fin_dia = int(np.flatnonzero(dia == dia[t])[-1])
        salida, motivo, i = None, "abierta", n_cerr - 1
        for i in range(t + 1, n_cerr):
            toca_stop = l[i] <= stop if d == 1 else h[i] >= stop
            if toca_stop:
                hueco = o[i] < stop if d == 1 else o[i] > stop
                salida, motivo = (o[i] if hueco else stop), "stop"
                break
            if (h[i] >= obj) if d == 1 else (l[i] <= obj):
                salida, motivo = obj, "objetivo"
                break
            if i >= fin_dia:
                salida, motivo = c[i], "tiempo"
                break
        if salida is None:
            i = n - 1
            salida, r = c[i], 0.0   # abierta: precio actual, sin resultado todavía
        else:
            r = (salida - e) * d / riesgo - p.costo_lado * (e + salida) / riesgo
        ops.append(Operacion(
            tipo="spring_asia" if d == 1 else "upthrust_asia", direccion=d, puntos=0,
            fecha_senal=fmt(t), fecha_entrada=fmt(t + 1), fecha_salida=fmt(min(i, n - 1)),
            entrada=float(e), stop=float(stop), objetivo=float(obj), salida=float(salida),
            motivo_salida=motivo, r=float(r), barras=int(i - t),
        ))
        if motivo == "abierta":
            break
        libre = i + 1
    return ops
