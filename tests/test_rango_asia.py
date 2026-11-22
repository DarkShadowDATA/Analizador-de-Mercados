import numpy as np
import pandas as pd

from analizador import rango_asia


def dia_con_spring():
    idx = pd.date_range("2026-11-23", periods=288, freq="5min", tz="UTC")
    c = np.full(288, 100.0)
    c[:96] = 100 + np.sin(np.arange(96) / 5)          # rango asiático ~99-101
    df = pd.DataFrame({"open": c, "high": c + 0.2, "low": c - 0.2, "close": c, "volume": 1.0}, index=idx)
    t = 120                                            # 10:00 UTC perfora el mínimo
    df.iloc[t, [1, 2, 3]] = [99.0, 98.4, 98.6]
    df.iloc[t + 1, [0, 1, 2, 3]] = [98.6, 99.6, 98.5, 99.5]   # cierra de vuelta dentro
    df.iloc[t + 2:, [0, 1, 2, 3]] = [99.5, 101.5, 99.4, 101.4]  # sube al otro lado
    return df


def test_spring_del_rango_asiatico_llega_al_objetivo():
    df = dia_con_spring()
    ops = rango_asia.simular(df, ahora=df.index[-1] + pd.Timedelta(minutes=5))
    assert len(ops) == 1
    o = ops[0]
    assert o.direccion == 1 and o.fecha_senal == "2026-11-23T10:05:00Z"
    assert o.motivo_salida == "objetivo" and o.r > 0
    assert (o.entrada - o.stop) / o.entrada >= 0.004 - 1e-9


def test_en_vivo_queda_abierta():
    df = dia_con_spring().iloc[:123]
    ops = rango_asia.simular(df, ahora=df.index[-1] + pd.Timedelta(minutes=2))
    assert ops and ops[-1].motivo_salida == "abierta"
