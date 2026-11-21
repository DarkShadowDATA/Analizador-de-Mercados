import numpy as np
import pandas as pd

from analizador import backtest, indicadores, senales


def rango_con_spring(n_rango=80, semilla=3):
    """Rango lateral entre 95 y 105, luego una falsa ruptura bajista y subida."""
    rng = np.random.default_rng(semilla)
    c = 100 + 4 * np.sin(np.linspace(0, 8 * np.pi, n_rango)) + rng.normal(0, 0.3, n_rango)
    c = np.r_[c, [94.0, 97.5, 99, 101, 103, 104, 105, 106, 107, 108]]
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.4
    l = np.minimum(o, c) - 0.4
    l[n_rango] = 93.0  # perforación del soporte
    v = np.full(len(c), 1000.0)
    v[n_rango] = 400.0  # perforación sin volumen
    idx = pd.date_range("2025-01-01", periods=len(c), freq="4h", tz="UTC", name="fecha")
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": v}, index=idx)


def test_rsi_extremos():
    sube = pd.Series(np.arange(1, 60, dtype=float))
    assert indicadores.rsi(sube).iloc[-1] == 100
    baja = pd.Series(np.arange(60, 1, -1, dtype=float))
    assert indicadores.rsi(baja).iloc[-1] < 1


def test_perfil_poc_y_area_de_valor():
    # Mucho volumen en 100-101 y poco en el resto
    high = np.array([101, 101, 101, 110, 92.0])
    low = np.array([100, 100, 100, 108, 90.0])
    vol = np.array([1000, 1000, 1000, 10, 10.0])
    p = indicadores.perfil_volumen(high, low, (high + low) / 2, vol, franjas=20)
    assert 100 <= p.poc <= 101
    assert p.val <= 100 and p.vah >= 101
    assert p.val >= 90 and p.vah <= 110


def test_niveles_no_miran_al_futuro():
    df = rango_con_spring()
    completo = indicadores.niveles_anclados(df)
    recortado = indicadores.niveles_anclados(df.iloc[:70])
    pd.testing.assert_frame_equal(completo.iloc[:70], recortado)


def test_detecta_spring():
    df = rango_con_spring()
    p = senales.Parametros(rango_barras=30, rango_min_atr=2, rango_max_atr=30, lateralidad=1.0)
    lista = senales.detectar(df, p)
    springs = [s for s in lista if s.tipo == "spring"]
    assert springs, "debería detectar el spring"
    s = springs[-1]
    assert s.direccion == 1 and s.extremo <= 93.0 and s.cierre > s.nivel
    assert any("sin volumen" in m for m in s.motivos)


def test_backtest_entra_en_la_vela_siguiente_y_respeta_stop():
    df = rango_con_spring()
    p = senales.Parametros(rango_barras=30, rango_min_atr=2, rango_max_atr=30, lateralidad=1.0)
    lista = [s for s in senales.detectar(df, p) if s.tipo == "spring"][-1:]
    reglas = backtest.ReglasBT(puntos_min=1, filtro_tendencia=0)
    ops = backtest.simular(df, lista, "indice", reglas)
    assert len(ops) == 1
    op = ops[0]
    i = df.index.get_loc(pd.Timestamp(op.fecha_senal))
    assert op.entrada == df["open"].iloc[i + 1]
    assert op.stop < lista[0].extremo
    assert op.motivo_salida == "objetivo" and op.r > 0
    m = backtest.metricas(ops, reglas)
    assert m["operaciones"] == 1 and m["aciertos_pct"] == 100.0
