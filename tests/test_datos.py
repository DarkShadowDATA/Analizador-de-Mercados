import json

import numpy as np
import pandas as pd
import pytest

from analizador import almacen, fuentes
from analizador.mercados import MERCADOS, por_id


def velas_falsas(n=300, frec="1h", inicio="2025-01-01", precio=100.0, semilla=1):
    rng = np.random.default_rng(semilla)
    idx = pd.date_range(inicio, periods=n, freq=frec, tz="UTC", name="fecha")
    c = precio * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.005, n))
    l = np.minimum(o, c) * (1 - rng.uniform(0, 0.005, n))
    v = rng.uniform(100, 1000, n)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}, index=idx)


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(almacen, "DIR_DATOS", tmp_path / "data")
    monkeypatch.setattr(almacen, "DIR_WEB", tmp_path / "web")
    monkeypatch.setattr(almacen, "ARCHIVO_ESTADO", tmp_path / "data" / "estado.json")
    return tmp_path


def test_remuestreo_4h_alineado_a_utc():
    df = velas_falsas(48, inicio="2025-01-01 01:00")
    r = fuentes.remuestrear(df, "4h")
    assert all(ts.hour % 4 == 0 for ts in r.index)
    primera = r.iloc[1]  # 04:00-08:00 completa
    tramo = df.loc["2025-01-01 04:00":"2025-01-01 07:00"]
    assert primera["open"] == tramo["open"].iloc[0]
    assert primera["close"] == tramo["close"].iloc[-1]
    assert primera["high"] == tramo["high"].max()
    assert primera["volume"] == pytest.approx(tramo["volume"].sum())


def test_unir_pisa_la_ultima_vela():
    viejo = velas_falsas(10)
    nuevo = velas_falsas(3, inicio=str(viejo.index[-1].tz_localize(None)), semilla=9)
    unido = almacen.unir(viejo, nuevo)
    assert len(unido) == 12
    assert unido.loc[viejo.index[-1], "close"] == nuevo.iloc[0]["close"]
    assert unido.index.is_monotonic_increasing


def test_normalizar_descarta_velas_invalidas():
    df = velas_falsas(5)
    df.iloc[2, df.columns.get_loc("high")] = 0  # high < low
    df.iloc[3, df.columns.get_loc("close")] = np.nan
    assert len(fuentes.normalizar(df)) == 3


def test_guardar_y_cargar(carpeta):
    df = velas_falsas(50)
    almacen.guardar("btc", "1h", df)
    leido = almacen.cargar("btc", "1h")
    assert len(leido) == 50
    assert str(leido.index.tz) == "UTC"
    np.testing.assert_allclose(leido["close"].values, df["close"].values, rtol=1e-7)


def test_exportar_web(carpeta):
    for m in MERCADOS:
        almacen.guardar(m.id, "1d", velas_falsas(30, frec="1D"))
        almacen.guardar(m.id, "1h", velas_falsas(100))
    estado = {"btc": {"1d": {"fuente": "Bitget BTCUSDT"}}}
    indice = almacen.exportar_web(estado)
    assert len(indice["mercados"]) == len(MERCADOS)
    btc = next(m for m in indice["mercados"] if m["id"] == "btc")
    assert btc["series"]["1d"]["fuente"] == "Bitget BTCUSDT"
    assert "4h" not in btc["series"]
    assert "cambio_pct" in btc
    serie = json.loads((carpeta / "web" / "btc_1h.json").read_text())
    assert len(serie["t"]) == 100 and set(serie) == {"t", "o", "h", "l", "c", "v"}


class RespuestaFalsa:
    def __init__(self, datos):
        self._d = datos

    def raise_for_status(self):
        pass

    def json(self):
        return {"code": "00000", "msg": "success", "data": self._d}


def test_bitget_pagina_hacia_atras(monkeypatch):
    hora = 3600 * 1000
    fin = 1_760_000_000_000 // hora * hora
    todas = [[str(fin - i * hora), "1", "2", "0.5", "1.5", "10", "15", "15"] for i in range(450)]
    llamadas = []

    recientes = [[str(fin + i * hora), "1", "2", "0.5", "1.5", "10", "15", "15"] for i in (0, 1, 2)]

    def get(self, url, params, timeout):
        if url == fuentes.BITGET_URL_RECIENTES:
            return RespuestaFalsa(recientes)
        llamadas.append(params["endTime"])
        lote = [f for f in todas if int(f[0]) <= params["endTime"]][:200]
        return RespuestaFalsa(lote)

    monkeypatch.setattr(fuentes.requests.Session, "get", get)
    monkeypatch.setattr(fuentes.time, "time", lambda: fin / 1000)
    monkeypatch.setattr(fuentes.time, "sleep", lambda s: None)
    df = fuentes.bitget("BTCUSDT", "1h", desde=pd.Timestamp(fin - 300 * hora, unit="ms", tz="UTC"))
    assert len(df) == 303  # 301 del histórico + 2 recientes (la de `fin` está repetida)
    assert df.index[-1] == pd.Timestamp(fin + 2 * hora, unit="ms", tz="UTC")
    assert df.index.is_monotonic_increasing
    assert len(llamadas) == 2
    assert df["volume"].iloc[0] == 10.0


def test_yahoo_diario_fecha_a_medianoche_utc(monkeypatch):
    idx = pd.DatetimeIndex(["2025-03-03", "2025-03-04"]).tz_localize("America/New_York")
    raw = pd.DataFrame({"Open": [1, 2], "High": [2, 3], "Low": [0.5, 1], "Close": [1.5, 2.5],
                        "Volume": [100, 200]}, index=idx)

    class TickerFalso:
        def __init__(self, s):
            pass

        def history(self, **kw):
            return raw

    import yfinance
    monkeypatch.setattr(yfinance, "Ticker", TickerFalso)
    df = fuentes.yahoo("ES=F", "1d")
    assert list(df.index.strftime("%Y-%m-%d %H:%M")) == ["2025-03-03 00:00", "2025-03-04 00:00"]
    assert str(df.index.tz) == "UTC"


def test_cripto_cae_a_yahoo_si_bitget_falla(monkeypatch):
    def rompe(*a, **k):
        raise ConnectionError("sin red")

    monkeypatch.setattr(fuentes, "bitget", rompe)
    monkeypatch.setattr(fuentes, "yahoo", lambda s, tf: velas_falsas(5))
    df, fuente = fuentes.descargar(por_id("btc"), "1h")
    assert fuente == "Yahoo BTC-USD" and len(df) == 5
