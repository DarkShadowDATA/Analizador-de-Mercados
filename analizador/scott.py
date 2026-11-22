"""Estrategia de ScottFDX ("estrategia del reto"), versión agresiva, según su video
"Estrategia GANADORA de SCALPIN/INTRADÍA en Bitcoin" (jul-2023).

Reglas (venta; la compra es simétrica):
  1. Se confirma un pivote de resistencia (máximo de giro).
  2. Una vela de 5 min cierra por debajo de la EMA 12 (vela de ruptura).
  3. Orden límite de venta en el valor de la EMA al cierre de esa vela.
  4. Stop ligeramente por encima del pivote.
  5. TP1: cierra el 75 % a 1,7R y mueve el stop a la entrada.
  6. TP2: el 25 % restante sale con una divergencia precio-RSI (o al final del día).

Supuestos propios (el indicador "pupú" no es público):
  - pivote de fuerza `k` velas a cada lado (se conoce k velas después);
  - "EMA en escalera" opcional = EMA 12 calculada en 15 min y mantenida en escalones;
  - la orden límite caduca si no se llena en `caduca` velas;
  - una operación por pivote y una a la vez.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .indicadores import atr as calc_atr
from .indicadores import rsi as calc_rsi


@dataclass
class ParamsScott:
    k: int = 5                    # fuerza del pivote
    ema: int = 12
    escalera: str | None = None   # None = EMA normal en 5m; "15min" = EMA de 15m en escalones
    caduca: int = 12              # velas que vive la orden límite (12 = 1 hora)
    colchon_atr: float = 0.1      # "ligeramente" por encima/debajo del pivote
    tp1_r: float = 1.7
    tp1_parte: float = 0.75
    max_velas: int = 288          # salida forzada del resto (288 = 1 día)
    riesgo_min_pct: float = 0.0   # descarta operaciones con stop demasiado corto (% del precio)
    comision_limite: float = 0.0002   # Bitget futuros, maker
    comision_mercado: float = 0.0006  # taker
    deslizamiento: float = 0.0002     # en salidas a mercado (stop, salida final)
    solo: int = 0                 # 1 solo largos, -1 solo cortos, 0 ambos
    # Niveles del indicador real "EMA y Pivotes ZS" (400 min, bloques desde 00:00 UTC):
    #   None = pivotes de k velas (aproximación inicial)
    #   "acumulado" = máx/mín del bloque de 400 min en curso hasta la vela anterior
    #   "anterior"  = máx/mín del bloque de 400 min anterior (ya cerrado)
    niveles: str | None = None
    bloque_min: int = 400


@dataclass
class OpScott:
    direccion: int
    fecha_senal: pd.Timestamp
    fecha_entrada: pd.Timestamp
    fecha_salida: pd.Timestamp
    entrada: float
    stop: float
    tp1: float
    pivote: float
    tp1_alcanzado: bool
    r: float
    motivo: str


def _ema_escalera(close: pd.Series, n: int, regla: str | None) -> np.ndarray:
    if not regla:
        return close.ewm(span=n, adjust=False).mean().to_numpy()
    # EMA sobre el cierre de velas mayores; cada valor vale a partir del cierre de esa vela mayor
    mayor = close.resample(regla, label="right", closed="left").last().dropna()
    e = mayor.ewm(span=n, adjust=False).mean()
    return e.reindex(close.index, method="ffill").to_numpy()


def niveles_zs(df: pd.DataFrame, modo: str, minutos: int = 400) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Resistencia/soporte del indicador ZS sin mirar al futuro.

    Los bloques de `minutos` reinician cada día a 00:00 UTC (00:00, 06:40, 13:20, 20:00-24:00).
    """
    idx = df.index
    dia = idx.floor("D")
    num = ((idx - dia) // pd.Timedelta(minutes=minutos)).astype(int)
    clave = pd.Series(dia.strftime("%Y%m%d"), index=idx) + "-" + pd.Series(num, index=idx).astype(str)
    h, l = df["high"], df["low"]
    if modo == "acumulado":
        res = h.groupby(clave.values).cummax().groupby(clave.values).shift(1)
        sop = l.groupby(clave.values).cummin().groupby(clave.values).shift(1)
    elif modo == "anterior":
        g = pd.DataFrame({"k": clave.values, "h": h.values, "l": l.values})
        ext = g.groupby("k", sort=False).agg(h=("h", "max"), l=("l", "min"))
        prev = ext.shift(1)
        res = pd.Series(prev["h"].reindex(clave.values).to_numpy(), index=idx)
        sop = pd.Series(prev["l"].reindex(clave.values).to_numpy(), index=idx)
    else:
        raise ValueError(modo)
    return res.to_numpy(dtype=float), sop.to_numpy(dtype=float), clave.to_numpy()


def simular(df: pd.DataFrame, p: ParamsScott | None = None) -> list[OpScott]:
    p = p or ParamsScott()
    o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
    idx = df.index
    n = len(df)
    ema = _ema_escalera(df["close"], p.ema, p.escalera)
    r = calc_rsi(df["close"]).to_numpy()
    a = calc_atr(df).to_numpy()
    k = p.k

    # Pivotes: posición del pivote y vela en que se confirma
    ventana = 2 * k + 1
    max_c = pd.Series(h).rolling(ventana, center=True).max().to_numpy()
    min_c = pd.Series(l).rolling(ventana, center=True).min().to_numpy()
    es_alto = (h == max_c)
    es_bajo = (l == min_c)

    if p.niveles:
        res_zs, sop_zs, bloque = niveles_zs(df, p.niveles, p.bloque_min)
    usados_zs: set = set()

    ops: list[OpScott] = []
    ultimo_alto = ultimo_bajo = None    # (posición, precio) del último pivote confirmado
    usado_alto = usado_bajo = -1        # pivote ya operado
    orden = None                        # orden límite pendiente
    pos = None                          # posición abierta
    bajos_piv: list[tuple[int, float, float]] = []  # para divergencias: (pos, precio, rsi)
    altos_piv: list[tuple[int, float, float]] = []

    def costo_r(precio_e, precio_s, riesgo, salida_mercado):
        com_s = p.comision_mercado + p.deslizamiento if salida_mercado else p.comision_limite
        return (p.comision_limite * precio_e + com_s * precio_s) / riesgo

    for t in range(n):
        # 1) Confirmar pivotes (el pivote en t-k se conoce al cierre de t)
        j = t - k
        if j >= k:
            if es_alto[j]:
                ultimo_alto = (j, h[j])
                altos_piv.append((j, h[j], r[j]))
            if es_bajo[j]:
                ultimo_bajo = (j, l[j])
                bajos_piv.append((j, l[j], r[j]))

        # 2) Gestionar posición abierta con la vela t
        if pos is not None and t > pos["t_e"]:
            d = pos["d"]
            fin = None
            if not pos["tp1"]:
                toca_stop = (h[t] >= pos["stop"]) if d < 0 else (l[t] <= pos["stop"])
                toca_tp1 = (l[t] <= pos["tp1_p"]) if d < 0 else (h[t] >= pos["tp1_p"])
                if toca_stop:  # pesimista: si toca ambos, cuenta el stop
                    salida = max(o[t], pos["stop"]) if d < 0 else min(o[t], pos["stop"])
                    res = (salida - pos["e"]) * d
                    fin = (res / pos["riesgo"] - costo_r(pos["e"], salida, pos["riesgo"], True), "stop")
                elif toca_tp1:
                    pos["tp1"] = True
                    pos["r_parcial"] = p.tp1_parte * (p.tp1_r - costo_r(pos["e"], pos["tp1_p"], pos["riesgo"], False))
                    pos["stop"] = pos["e"]  # break even
            else:
                toca_be = (h[t] >= pos["stop"]) if d < 0 else (l[t] <= pos["stop"])
                salida = None
                if toca_be:
                    salida, motivo = pos["stop"], "tp1 + break even"
                else:
                    # Divergencia precio-RSI a favor del cierre (pivote recién confirmado)
                    lista = bajos_piv if d < 0 else altos_piv
                    if len(lista) >= 2 and lista[-1][0] == t - k and lista[-1][0] > pos["t_e"]:
                        (p1, x1, r1), (p2, x2, r2) = lista[-2], lista[-1]
                        if d < 0 and x2 < x1 and r2 > r1 or d > 0 and x2 > x1 and r2 < r1:
                            salida, motivo = c[t], "tp1 + divergencia RSI"
                    if salida is None and t - pos["t_e"] >= p.max_velas:
                        salida, motivo = c[t], "tp1 + tiempo"
                if salida is not None:
                    resto = (1 - p.tp1_parte) * ((salida - pos["e"]) * d / pos["riesgo"]
                                                  - costo_r(pos["e"], salida, pos["riesgo"], True))
                    fin = (pos["r_parcial"] + resto, motivo)
            if fin is None and not pos["tp1"] and t - pos["t_e"] >= p.max_velas:
                res = (c[t] - pos["e"]) * pos["d"] / pos["riesgo"]
                fin = (res - costo_r(pos["e"], c[t], pos["riesgo"], True), "tiempo")
            if fin is not None:
                ops.append(OpScott(pos["d"], idx[pos["t_s"]], idx[pos["t_e"]], idx[t], pos["e"], pos["stop0"],
                                   pos["tp1_p"], pos["piv"], pos["tp1"], float(fin[0]), fin[1]))
                pos = None

        # 3) Orden límite pendiente: ¿se llena en t?
        if orden is not None and pos is None and t > orden["t_s"]:
            d = orden["d"]
            invalida = (h[t] >= orden["stop"]) if d < 0 else (l[t] <= orden["stop"])
            llena = (h[t] >= orden["precio"]) if d < 0 else (l[t] <= orden["precio"])
            if llena:
                e = orden["precio"]
                riesgo = (orden["stop"] - e) * -d
                pos = dict(d=d, e=e, stop=orden["stop"], stop0=orden["stop"], riesgo=riesgo,
                           tp1_p=e + d * p.tp1_r * riesgo, tp1=False, t_e=t, t_s=orden["t_s"], piv=orden["piv"])
                orden = None
                # Misma vela: si también toca el stop, sale (pesimista)
                if invalida:
                    ops.append(OpScott(d, idx[pos["t_s"]], idx[t], idx[t], e, pos["stop"], pos["tp1_p"],
                                       pos["piv"], False, -1 - costo_r(e, pos["stop"], riesgo, True), "stop"))
                    pos = None
            elif invalida or t - orden["t_s"] > p.caduca:
                orden = None

        # 4) Nueva señal al cierre de t
        if p.niveles and pos is None and orden is None and t > 0 and np.isfinite(a[t]):
            # Alertas del indicador: SELL si tocó resistencia y cerró bajo la EMA; BUY simétrico
            for d in (-1, 1):
                if p.solo and d != p.solo or (bloque[t], d) in usados_zs:
                    continue
                nivel = res_zs[t] if d < 0 else sop_zs[t]
                if not np.isfinite(nivel):
                    continue
                toca = h[t] >= nivel if d < 0 else l[t] <= nivel
                cierra = c[t] < ema[t] if d < 0 else c[t] > ema[t]
                if not (toca and cierra):
                    continue
                precio = ema[t]
                extremo = h[t] if d < 0 else l[t]
                stop = extremo + p.colchon_atr * a[t] if d < 0 else extremo - p.colchon_atr * a[t]
                riesgo = (stop - precio) * -d
                if riesgo <= 0 or riesgo / precio * 100 < p.riesgo_min_pct:
                    continue
                orden = dict(d=d, precio=precio, stop=stop, t_s=t, piv=extremo)
                usados_zs.add((bloque[t], d))
                break
        elif pos is None and orden is None and t > 0 and np.isfinite(a[t]):
            for d, piv, usado in ((-1, ultimo_alto, usado_alto), (1, ultimo_bajo, usado_bajo)):
                if p.solo and d != p.solo:
                    continue
                if piv is None or piv[0] == usado:
                    continue
                # el pivote debe ser el más reciente de los dos (estructura: giro y ruptura de la EMA)
                otro = ultimo_bajo if d < 0 else ultimo_alto
                if otro is not None and otro[0] > piv[0]:
                    continue
                cruza = (c[t] < ema[t] and c[t - 1] >= ema[t - 1]) if d < 0 else (c[t] > ema[t] and c[t - 1] <= ema[t - 1])
                if not cruza:
                    continue
                precio = ema[t]
                stop = piv[1] + p.colchon_atr * a[t] if d < 0 else piv[1] - p.colchon_atr * a[t]
                riesgo = (stop - precio) * -d
                if riesgo <= 0 or riesgo / precio * 100 < p.riesgo_min_pct:
                    continue
                orden = dict(d=d, precio=precio, stop=stop, t_s=t, piv=piv[1])
                if d < 0:
                    usado_alto = piv[0]
                else:
                    usado_bajo = piv[0]
                break
    return ops


def resumen(ops: list[OpScott], corte: pd.Timestamp | None = None) -> dict:
    def m(lista):
        if not lista:
            return {"n": 0}
        rr = np.array([x.r for x in lista])
        return {
            "n": len(lista),
            "tp1_pct": round(100 * np.mean([x.tp1_alcanzado for x in lista]), 1),
            "gana_pct": round(100 * float((rr > 0).mean()), 1),
            "r_medio": round(float(rr.mean()), 3),
            "r_total": round(float(rr.sum()), 1),
        }
    out = {"todo": m(ops)}
    if corte is not None:
        out["1a_mitad"] = m([x for x in ops if x.fecha_entrada < corte])
        out["2a_mitad"] = m([x for x in ops if x.fecha_entrada >= corte])
    return out
