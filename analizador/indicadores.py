"""Indicadores: RSI, ATR, pivotes y perfil de volumen anclado.

Todo se calcula sin mirar al futuro: el valor en la vela t solo usa velas <= t.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# RSI y ATR (suavizado de Wilder)
# --------------------------------------------------------------------------

def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    subida = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    bajada = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = subida / bajada.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    out = out.where(bajada != 0, 100.0)
    return out.where(subida.notna())


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


# --------------------------------------------------------------------------
# Pivotes (máximos y mínimos de giro)
# --------------------------------------------------------------------------

def pivotes(df: pd.DataFrame, k: int = 10) -> tuple[np.ndarray, np.ndarray]:
    """Posiciones de pivotes altos y bajos de fuerza k (k velas a cada lado).

    Un pivote en la posición i solo se conoce en la vela i + k (confirmación).
    """
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    ventana = 2 * k + 1
    max_c = pd.Series(h).rolling(ventana, center=True).max().to_numpy()
    min_c = pd.Series(l).rolling(ventana, center=True).min().to_numpy()
    altos = np.flatnonzero(h == max_c)
    bajos = np.flatnonzero(l == min_c)
    return altos, bajos


# --------------------------------------------------------------------------
# Perfil de volumen
# --------------------------------------------------------------------------

@dataclass
class Perfil:
    precios: np.ndarray   # centro de cada franja de precio
    volumen: np.ndarray   # volumen acumulado por franja
    poc: float            # precio con más volumen (Point of Control)
    vah: float            # techo del área de valor (70 % del volumen)
    val: float            # piso del área de valor


def perfil_volumen(high, low, close, volume, franjas: int = 40, area: float = 0.70) -> Perfil | None:
    """Reparte el volumen de cada vela uniformemente entre su mínimo y su máximo."""
    high, low = np.asarray(high, float), np.asarray(low, float)
    close, volume = np.asarray(close, float), np.asarray(volume, float)
    if len(high) == 0:
        return None
    lo, hi = float(low.min()), float(high.max())
    if not np.isfinite(lo) or hi <= lo:
        return None
    bordes = np.linspace(lo, hi, franjas + 1)
    b_lo, b_hi = bordes[:-1], bordes[1:]
    rango = high - low
    solape = np.clip(np.minimum(high[:, None], b_hi) - np.maximum(low[:, None], b_lo), 0, None)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(rango[:, None] > 0, solape / rango[:, None], 0.0)
    # Velas sin rango (máximo == mínimo): todo el volumen a la franja del cierre
    planas = rango <= 0
    if planas.any():
        idx = np.clip(np.searchsorted(bordes, close[planas], side="right") - 1, 0, franjas - 1)
        frac[np.flatnonzero(planas), idx] = 1.0
    vol = (frac * volume[:, None]).sum(axis=0)
    total = vol.sum()
    centros = (b_lo + b_hi) / 2
    if total <= 0:
        return Perfil(centros, vol, float(centros[franjas // 2]), hi, lo)

    i_poc = int(vol.argmax())
    a, b = i_poc, i_poc
    acumulado = vol[i_poc]
    while acumulado < area * total and (a > 0 or b < franjas - 1):
        abajo = vol[a - 1] if a > 0 else -1
        arriba = vol[b + 1] if b < franjas - 1 else -1
        if arriba >= abajo:
            b += 1
            acumulado += vol[b]
        else:
            a -= 1
            acumulado += vol[a]
    return Perfil(centros, vol, float(centros[i_poc]), float(b_hi[b]), float(b_lo[a]))


def anclas(df: pd.DataFrame, k: int = 10, min_barras: int = 30, max_barras: int = 300) -> np.ndarray:
    """Para cada vela t, la posición donde se ancla el perfil.

    Se usa el último pivote mayor (alto o bajo) ya confirmado en t que esté al menos
    `min_barras` atrás. Si no hay, o está a más de `max_barras`, se ancla en t - max_barras.
    """
    n = len(df)
    altos, bajos = pivotes(df, k)
    piv = np.unique(np.concatenate([altos, bajos]))
    conocido = piv + k  # vela en la que se confirma cada pivote
    out = np.empty(n, dtype=int)
    j = -1
    validos: list[int] = []
    for t in range(n):
        while j + 1 < len(piv) and conocido[j + 1] <= t:
            j += 1
            validos.append(int(piv[j]))
        ancla = max(0, t - max_barras)
        for p in reversed(validos):
            if t - p >= min_barras:
                if p > ancla:
                    ancla = p
                break
        out[t] = ancla
    return out


def niveles_anclados(df: pd.DataFrame, franjas: int = 40, k: int = 10,
                     min_barras: int = 30, max_barras: int = 300) -> pd.DataFrame:
    """POC, VAH y VAL del perfil anclado, vela a vela (usa velas ancla..t inclusive)."""
    a = anclas(df, k, min_barras, max_barras)
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    c, v = df["close"].to_numpy(), df["volume"].to_numpy()
    res = np.full((len(df), 3), np.nan)
    for t in range(len(df)):
        if t - a[t] + 1 < min_barras // 2:
            continue
        p = perfil_volumen(h[a[t]:t + 1], l[a[t]:t + 1], c[a[t]:t + 1], v[a[t]:t + 1], franjas)
        if p is not None:
            res[t] = (p.poc, p.vah, p.val)
    out = pd.DataFrame(res, index=df.index, columns=["poc", "vah", "val"])
    out["ancla"] = df.index[a]
    return out


def calcular(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve df con columnas extra: rsi, atr, vol_media, poc, vah, val, ancla."""
    out = df.copy()
    out["rsi"] = rsi(df["close"])
    out["atr"] = atr(df)
    out["vol_media"] = df["volume"].rolling(20, min_periods=10).mean()
    return out.join(niveles_anclados(df))
