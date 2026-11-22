"""Detección de falsas rupturas al estilo Wyckoff, confirmadas con RSI y perfil de volumen.

Eventos:
  - spring   (alcista): el precio perfora el soporte del rango y cierra de vuelta dentro.
  - upthrust (bajista): perfora la resistencia del rango y cierra de vuelta dentro.
  - test     : después de un spring/upthrust, el precio vuelve cerca del extremo
               con MENOS volumen y lo respeta (confirma que no hay oferta/demanda).

Confirmaciones (cada una suma un punto):
  - RSI: sobreventa/sobrecompra (<=35 / >=65) o divergencia contra el extremo anterior.
  - Perfil de volumen anclado: la falsa ruptura ocurre fuera del área de valor
    (por debajo del VAL en un spring, por encima del VAH en un upthrust).
  - Volumen: el cierre de vuelta dentro del rango sale con volumen alto (absorción)
    o la perforación sale con volumen bajo (no hay oferta/demanda real).

Una señal se conoce al CIERRE de la vela t; se opera en la apertura de t+1.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from . import indicadores


@dataclass
class Parametros:
    rango_barras: int = 30        # velas que definen el rango (soporte/resistencia); 30 fue lo mejor en 4H (22-nov-2026)
    rango_min_atr: float = 3.0    # ancho mínimo del rango en ATR
    rango_max_atr: float = 12.0   # ancho máximo (más que esto es tendencia, no rango)
    lateralidad: float = 0.5      # |cambio neto en el rango| / ancho del rango (menos = más lateral)
    cerca_nivel_atr: float = 0.75 # distancia máx. del nivel al VAL/VAH/POC para contar confluencia
    perforacion_min_atr: float = 0.05
    perforacion_max_atr: float = 1.5   # más profundo = ruptura real, no falsa
    barras_recuperacion: int = 2  # velas para volver a cerrar dentro del rango
    rsi_bajo: float = 35.0
    rsi_alto: float = 65.0
    test_barras: int = 12         # ventana para buscar el test
    test_distancia_atr: float = 0.6
    vol_alto: float = 1.3         # x media de 20 velas
    vol_bajo: float = 0.8


@dataclass
class Senal:
    fecha: pd.Timestamp
    tipo: str                 # spring, upthrust, test_spring, test_upthrust
    direccion: int            # 1 largo, -1 corto
    cierre: float
    nivel: float              # soporte o resistencia perforada
    extremo: float            # mínimo del spring / máximo del upthrust (referencia del stop)
    poc: float
    vah: float
    val: float
    rsi: float
    vol_rel: float
    atr: float
    puntos: int               # 1 a 4
    motivos: list[str] = field(default_factory=list)

    def a_dict(self) -> dict:
        d = asdict(self)
        d["fecha"] = self.fecha.strftime("%Y-%m-%dT%H:%M:%SZ")
        for k in ("cierre", "nivel", "extremo", "poc", "vah", "val", "rsi", "vol_rel", "atr"):
            d[k] = None if d[k] is None or not np.isfinite(d[k]) else round(float(d[k]), 6)
        return d


def detectar(df: pd.DataFrame, p: Parametros | None = None, x: pd.DataFrame | None = None) -> list[Senal]:
    """Recorre las velas y devuelve las señales en orden cronológico."""
    p = p or Parametros()
    x = indicadores.calcular(df) if x is None else x
    o, h, l, c = (x[k].to_numpy() for k in ("open", "high", "low", "close"))
    v, vm, r, a = (x[k].to_numpy() for k in ("volume", "vol_media", "rsi", "atr"))
    poc, vah, val = (x[k].to_numpy() for k in ("poc", "vah", "val"))
    idx = x.index
    N = p.rango_barras

    # Soporte/resistencia de cada vela = extremos de las N velas anteriores (sin incluirla)
    soporte = pd.Series(l).rolling(N).min().shift(1).to_numpy()
    resistencia = pd.Series(h).rolling(N).max().shift(1).to_numpy()
    # Posición del mínimo/máximo anterior para la divergencia de RSI
    pos_min = pd.Series(l).rolling(N).apply(np.argmin, raw=True).shift(1).to_numpy()
    pos_max = pd.Series(h).rolling(N).apply(np.argmax, raw=True).shift(1).to_numpy()

    senales: list[Senal] = []
    ultimo_evento: dict[int, tuple[int, float, float]] = {}  # dir -> (t, extremo, volumen)
    usado: set[tuple[int, int]] = set()

    def vol_rel(i):
        return v[i] / vm[i] if vm[i] and np.isfinite(vm[i]) and vm[i] > 0 else np.nan

    for t in range(N + 20, len(x)):
        if not np.isfinite(a[t]) or not np.isfinite(poc[t - 1]):
            continue
        for d in (1, -1):
            # ---------------- spring / upthrust ----------------
            for j in range(p.barras_recuperacion + 1):
                b = t - j  # vela que perforó
                nivel = soporte[b] if d == 1 else resistencia[b]
                otro = resistencia[b] if d == 1 else soporte[b]
                if not np.isfinite(nivel) or (d, b) in usado:
                    continue
                ancho = abs(otro - nivel) / a[b]
                if not (p.rango_min_atr <= ancho <= p.rango_max_atr):
                    continue
                neto = abs(c[b - 1] - c[b - N]) / abs(otro - nivel)
                if neto > p.lateralidad:
                    continue  # el tramo previo es tendencia, no un rango
                tramo = slice(b, t + 1)
                ext = l[tramo].min() if d == 1 else h[tramo].max()
                perf = (nivel - ext) / a[b] if d == 1 else (ext - nivel) / a[b]
                if not (p.perforacion_min_atr <= perf <= p.perforacion_max_atr):
                    continue
                # Debe cerrar de vuelta dentro en t, y no antes (primera recuperación)
                dentro = (lambda i: c[i] > nivel) if d == 1 else (lambda i: c[i] < nivel)
                if not dentro(t) or any(dentro(i) for i in range(b, t)):
                    continue
                if d == 1 and l[b] >= nivel or d == -1 and h[b] <= nivel:
                    continue

                motivos, puntos = [], 1
                rmin = np.nanmin(r[tramo]) if d == 1 else np.nanmax(r[tramo])
                ref = int(b - N + pos_min[b]) if d == 1 else int(b - N + pos_max[b])
                if d == 1 and rmin <= p.rsi_bajo or d == -1 and rmin >= p.rsi_alto:
                    puntos += 1
                    motivos.append(f"RSI {'sobreventa' if d == 1 else 'sobrecompra'} ({rmin:.0f})")
                elif 0 <= ref < len(r) and np.isfinite(r[ref]):
                    if d == 1 and rmin > r[ref] + 2 or d == -1 and rmin < r[ref] - 2:
                        puntos += 1
                        motivos.append("divergencia de RSI")
                borde = val[b - 1] if d == 1 else vah[b - 1]
                cerca = [nombre for nombre, ref_p in (("VAL" if d == 1 else "VAH", borde), ("POC", poc[b - 1]))
                         if abs(nivel - ref_p) <= p.cerca_nivel_atr * a[b]]
                if cerca:
                    puntos += 1
                    motivos.append(f"nivel en zona de volumen ({cerca[0]} del perfil anclado)")
                vr_rec, vr_perf = vol_rel(t), vol_rel(b)
                if np.isfinite(vr_rec) and vr_rec >= p.vol_alto and j > 0:
                    puntos += 1
                    motivos.append(f"absorción: vuelta con volumen alto ({vr_rec:.1f}x)")
                elif np.isfinite(vr_perf) and vr_perf <= p.vol_bajo:
                    puntos += 1
                    motivos.append(f"perforación sin volumen ({vr_perf:.1f}x)")
                elif np.isfinite(vr_perf) and vr_perf >= p.vol_alto:
                    motivos.append(f"sacudida con volumen alto ({vr_perf:.1f}x): esperar test")

                senales.append(Senal(
                    fecha=idx[t], tipo="spring" if d == 1 else "upthrust", direccion=d,
                    cierre=c[t], nivel=nivel, extremo=ext, poc=poc[t], vah=vah[t], val=val[t],
                    rsi=r[t], vol_rel=vol_rel(t), atr=a[t], puntos=puntos, motivos=motivos,
                ))
                usado.update((d, i) for i in range(b, t + 1))
                ultimo_evento[d] = (t, ext, float(np.nanmax(v[tramo])))
                break

            # ---------------- test ----------------
            ev = ultimo_evento.get(d)
            if ev and 2 <= t - ev[0] <= p.test_barras:
                t0, ext, vol_ev = ev
                cerca = (l[t] - ext) if d == 1 else (ext - h[t])
                respeta = 0 <= cerca <= p.test_distancia_atr * a[t]
                if d == 1:
                    vela_ok = c[t] > o[t] or c[t] > (h[t] + l[t]) / 2
                else:
                    vela_ok = c[t] < o[t] or c[t] < (h[t] + l[t]) / 2
                if respeta and vela_ok and v[t] < vol_ev:
                    motivos = [f"retesteo del {'mínimo' if d == 1 else 'máximo'} con menos volumen"]
                    puntos = 2
                    if np.isfinite(vol_rel(t)) and vol_rel(t) <= p.vol_bajo:
                        puntos += 1
                        motivos.append(f"volumen seco ({vol_rel(t):.1f}x)")
                    senales.append(Senal(
                        fecha=idx[t], tipo="test_spring" if d == 1 else "test_upthrust", direccion=d,
                        cierre=c[t], nivel=ext, extremo=min(ext, l[t]) if d == 1 else max(ext, h[t]),
                        poc=poc[t], vah=vah[t], val=val[t], rsi=r[t], vol_rel=vol_rel(t), atr=a[t],
                        puntos=puntos, motivos=motivos,
                    ))
                    ultimo_evento.pop(d)
    return senales


def a_dataframe(senales: list[Senal]) -> pd.DataFrame:
    if not senales:
        return pd.DataFrame(columns=[f for f in Senal.__dataclass_fields__])
    return pd.DataFrame([asdict(s) for s in senales]).set_index("fecha")
