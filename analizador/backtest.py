"""Backtesting de las señales.

Reglas (iguales para todos los mercados, sin optimizar por mercado):
  - Entrada: apertura de la vela siguiente a la señal. Una operación a la vez.
  - Filtro de tendencia: solo largos sobre la media de 200 velas y cortos bajo ella.
  - Stop: detrás del extremo de la falsa ruptura + colchón de 1 ATR.
  - Objetivo: el otro lado del área de valor (VAH en largos, VAL en cortos),
    acotado entre 1R y 3R.
  - Salida por tiempo: si en `max_barras` no tocó stop ni objetivo, se cierra.
  - Si en la misma vela se tocan stop y objetivo, se asume el stop (pesimista).
  - Costos: comisión + deslizamiento por lado, descontados del resultado.
Resultados en R (múltiplos del riesgo) y en % con riesgo fijo del 1 % por operación.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .senales import Senal

COSTO_POR_LADO = {"cripto": 0.0008, "indice": 0.0002, "materia_prima": 0.0003}


@dataclass
class ReglasBT:
    puntos_min: int = 3
    filtro_tendencia: int = 200   # 0 = sin filtro
    colchon_atr: float = 1.0
    r_min: float = 1.0
    r_max: float = 3.0
    max_barras: int = 30
    riesgo_pct: float = 1.0
    solo_largos: bool = False


@dataclass
class Operacion:
    tipo: str
    direccion: int
    puntos: int
    fecha_senal: str
    fecha_entrada: str
    fecha_salida: str
    entrada: float
    stop: float
    objetivo: float
    salida: float
    motivo_salida: str   # objetivo, stop, tiempo, abierta
    r: float             # resultado neto en R
    barras: int


def simular(df: pd.DataFrame, senales: list[Senal], tipo_mercado: str, reglas: ReglasBT | None = None) -> list[Operacion]:
    reglas = reglas or ReglasBT()
    costo = COSTO_POR_LADO.get(tipo_mercado, 0.0005)
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    pos = {ts: i for i, ts in enumerate(df.index)}
    media = df["close"].rolling(reglas.filtro_tendencia).mean().to_numpy() if reglas.filtro_tendencia else None
    fmt = lambda i: df.index[i].strftime("%Y-%m-%dT%H:%M:%SZ")
    ops: list[Operacion] = []
    libre_desde = 0

    for s in senales:
        if s.puntos < reglas.puntos_min or (reglas.solo_largos and s.direccion < 0):
            continue
        i_sen = pos.get(s.fecha)
        if i_sen is None or i_sen + 1 >= len(df) or i_sen + 1 < libre_desde:
            continue
        e = i_sen + 1
        d = s.direccion
        if media is not None and not (np.isfinite(media[i_sen]) and (c[i_sen] - media[i_sen]) * d > 0):
            continue
        entrada = o[e]
        stop = s.extremo - d * reglas.colchon_atr * s.atr
        riesgo = (entrada - stop) * d
        if not np.isfinite(riesgo) or riesgo <= 0:
            continue
        borde = s.vah if d == 1 else s.val
        dist = (borde - entrada) * d if np.isfinite(borde) else 0
        dist = float(np.clip(dist, reglas.r_min * riesgo, reglas.r_max * riesgo))
        objetivo = entrada + d * dist

        salida, motivo, k = c[-1], "abierta", len(df) - 1
        for k in range(e, min(len(df), e + reglas.max_barras)):
            toca_stop = l[k] <= stop if d == 1 else h[k] >= stop
            toca_obj = h[k] >= objetivo if d == 1 else l[k] <= objetivo
            if toca_stop:
                # Si abre más allá del stop (hueco), se sale a la apertura
                salida = min(o[k], stop) if d == 1 else max(o[k], stop)
                motivo = "stop"
                break
            if toca_obj:
                salida, motivo = objetivo, "objetivo"
                break
        else:
            if e + reglas.max_barras <= len(df):
                k = e + reglas.max_barras - 1
                salida, motivo = c[k], "tiempo"

        bruto = (salida - entrada) * d
        costos = costo * (entrada + salida)
        ops.append(Operacion(
            tipo=s.tipo, direccion=d, puntos=s.puntos, fecha_senal=fmt(i_sen), fecha_entrada=fmt(e),
            fecha_salida=fmt(k), entrada=float(entrada), stop=float(stop), objetivo=float(objetivo),
            salida=float(salida), motivo_salida=motivo, r=float((bruto - costos) / riesgo), barras=k - e + 1,
        ))
        libre_desde = k + 1
    return ops


def metricas(ops: list[Operacion], reglas: ReglasBT | None = None, desde: str | None = None) -> dict:
    reglas = reglas or ReglasBT()
    cerradas = [op for op in ops if op.motivo_salida != "abierta" and (desde is None or op.fecha_entrada >= desde)]
    if not cerradas:
        return {"operaciones": 0}
    r = np.array([op.r for op in cerradas])
    ganan, pierden = r[r > 0], r[r <= 0]
    acumulado = np.cumsum(r)
    caida_r = float((np.maximum.accumulate(np.r_[0, acumulado]) - np.r_[0, acumulado]).max())
    capital = np.cumprod(1 + reglas.riesgo_pct / 100 * r)
    pico = np.maximum.accumulate(np.r_[1, capital])
    caida_pct = float(((pico - np.r_[1, capital]) / pico).max() * 100)
    return {
        "operaciones": int(len(r)),
        "aciertos_pct": round(float((r > 0).mean() * 100), 1),
        "r_medio": round(float(r.mean()), 3),
        "r_total": round(float(r.sum()), 2),
        "factor_beneficio": round(float(ganan.sum() / -pierden.sum()), 2) if pierden.sum() < 0 else None,
        "max_caida_r": round(caida_r, 2),
        "rentabilidad_pct": round(float((capital[-1] - 1) * 100), 1),
        "max_caida_pct": round(caida_pct, 1),
        "largos": int(sum(op.direccion > 0 for op in cerradas)),
        "cortos": int(sum(op.direccion < 0 for op in cerradas)),
        "desde": cerradas[0].fecha_entrada[:10],
        "hasta": cerradas[-1].fecha_salida[:10],
    }


def a_dicts(ops: list[Operacion]) -> list[dict]:
    out = []
    for op in ops:
        d = asdict(op)
        for k in ("entrada", "stop", "objetivo", "salida"):
            d[k] = round(d[k], 6)
        d["r"] = round(d["r"], 3)
        out.append(d)
    return out
