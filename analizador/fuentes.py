"""Descarga de velas OHLCV desde fuentes gratuitas.

Todas las funciones devuelven un DataFrame con:
  - índice: DatetimeIndex en UTC llamado "fecha" (inicio de la vela)
  - columnas: open, high, low, close, volume (float)
Las velas diarias se fechan a las 00:00 UTC del día de la sesión.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from .mercados import Mercado

log = logging.getLogger(__name__)

COLUMNAS = ["open", "high", "low", "close", "volume"]


def vacio() -> pd.DataFrame:
    df = pd.DataFrame(columns=COLUMNAS, dtype="float64")
    df.index = pd.DatetimeIndex([], tz="UTC", name="fecha")
    return df


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Ordena, quita duplicados y velas inválidas."""
    if df.empty:
        return vacio()
    df = df[COLUMNAS].astype("float64")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df["high"] >= df["low"]) & (df["close"] > 0)]
    df["volume"] = df["volume"].fillna(0.0)
    df.index.name = "fecha"
    return df


def remuestrear(df: pd.DataFrame, regla: str) -> pd.DataFrame:
    """Agrupa velas (p. ej. 1h -> 4h), alineadas a las 00:00 UTC."""
    if df.empty:
        return vacio()
    r = df.resample(regla, origin="epoch", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return normalizar(r.dropna(subset=["open"]))


# --------------------------------------------------------------------------
# Yahoo Finance (índices, oro y respaldo de cripto)
# --------------------------------------------------------------------------

_YAHOO_INTERVALO = {"1h": ("1h", "730d"), "1d": ("1d", "max")}


def yahoo(simbolo: str, temporalidad: str) -> pd.DataFrame:
    import yfinance as yf

    if temporalidad == "4h":
        return remuestrear(yahoo(simbolo, "1h"), "4h")

    intervalo, periodo = _YAHOO_INTERVALO[temporalidad]
    raw = yf.Ticker(simbolo).history(
        period=periodo, interval=intervalo, auto_adjust=False, actions=False
    )
    if raw is None or raw.empty:
        log.warning("Yahoo no devolvió datos para %s %s", simbolo, temporalidad)
        return vacio()

    raw = raw.rename(columns=str.lower)
    idx = pd.DatetimeIndex(raw.index)
    if temporalidad == "1d":
        # Fecha de la sesión (en la zona del mercado) -> 00:00 UTC de ese día
        fechas = idx if idx.tz is None else idx.tz_localize(None)
        idx = pd.DatetimeIndex(fechas.normalize()).tz_localize("UTC")
    else:
        idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    raw.index = idx
    return normalizar(raw)


# --------------------------------------------------------------------------
# Bitget (cripto) - API pública v2, no necesita clave
# --------------------------------------------------------------------------

BITGET_URL = "https://api.bitget.com/api/v2/spot/market/history-candles"
_BITGET_GRANULARIDAD = {"1h": "1h", "4h": "4h", "1d": "1Dutc"}
# Hasta dónde ir hacia atrás en la primera descarga (días)
_BITGET_DIAS_ATRAS = {"1h": 730, "4h": 2200, "1d": 3000}


def bitget(simbolo: str, temporalidad: str, desde: pd.Timestamp | None = None) -> pd.DataFrame:
    """Descarga velas hacia atrás paginando de 200 en 200.

    Si se da `desde`, solo baja lo posterior (actualización incremental).
    """
    gran = _BITGET_GRANULARIDAD[temporalidad]
    ahora_ms = int(time.time() * 1000)
    if desde is None:
        limite_ms = ahora_ms - _BITGET_DIAS_ATRAS[temporalidad] * 86400 * 1000
    else:
        limite_ms = int(pd.Timestamp(desde).timestamp() * 1000)

    filas: list[list] = []
    fin_ms = ahora_ms
    sesion = requests.Session()
    for _ in range(400):  # tope de seguridad
        resp = sesion.get(
            BITGET_URL,
            params={"symbol": simbolo, "granularity": gran, "endTime": fin_ms, "limit": 200},
            timeout=20,
        )
        resp.raise_for_status()
        cuerpo = resp.json()
        if str(cuerpo.get("code")) != "00000":
            raise RuntimeError(f"Bitget respondió {cuerpo.get('code')}: {cuerpo.get('msg')}")
        datos = cuerpo.get("data") or []
        if not datos:
            break
        filas.extend(datos)
        mas_antigua = min(int(d[0]) for d in datos)
        if mas_antigua <= limite_ms or mas_antigua >= fin_ms:
            break
        fin_ms = mas_antigua - 1
        time.sleep(0.12)  # respetar el límite de peticiones

    if not filas:
        return vacio()
    # Formato: [ts, open, high, low, close, volumen_base, volumen_usdt, volumen_cotizado]
    df = pd.DataFrame([f[:6] for f in filas], columns=["ts"] + COLUMNAS)
    df.index = pd.to_datetime(df.pop("ts").astype("int64"), unit="ms", utc=True)
    df = normalizar(df)
    return df[df.index >= pd.Timestamp(limite_ms, unit="ms", tz="UTC")]


# --------------------------------------------------------------------------
# Selección de fuente
# --------------------------------------------------------------------------

def descargar(mercado: Mercado, temporalidad: str, desde: pd.Timestamp | None = None) -> tuple[pd.DataFrame, str]:
    """Devuelve (velas, nombre_de_fuente). Cripto usa Bitget y cae a Yahoo si falla."""
    if mercado.bitget:
        try:
            df = bitget(mercado.bitget, temporalidad, desde)
            if not df.empty:
                return df, f"Bitget {mercado.bitget}"
            log.warning("Bitget vacío para %s %s, uso Yahoo", mercado.id, temporalidad)
        except Exception as e:  # red, límite, cambio de API...
            log.warning("Bitget falló para %s %s (%s), uso Yahoo", mercado.id, temporalidad, e)
    return yahoo(mercado.yahoo, temporalidad), f"Yahoo {mercado.yahoo}"
