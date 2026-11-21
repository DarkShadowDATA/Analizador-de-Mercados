"""Calcula indicadores, señales Wyckoff y backtest de todos los mercados y
escribe los JSON que usa la web:

  docs/data/analisis_<mercado>_<tf>.json  : RSI, niveles del perfil, señales y operaciones
  docs/data/resumen_senales.json          : tabla resumen (métricas y última señal)

Uso:  python scripts/generar_senales.py
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analizador import backtest, indicadores, senales  # noqa: E402
from analizador.almacen import DIR_WEB, cargar, solo_cerradas  # noqa: E402
from analizador.mercados import MAX_VELAS_WEB, MERCADOS, TEMPORALIDADES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("senales")

PARAMS = senales.Parametros()
REGLAS = backtest.ReglasBT()
VELAS_ACTIVA = 3  # una señal es "activa" si salió en las últimas N velas


def redondear(serie, dec=2):
    return [None if not np.isfinite(x) else round(float(x), dec) for x in serie]


def analizar(m, tf: str) -> dict | None:
    df = cargar(m.id, tf)
    if len(df) < 300:
        return None
    x = indicadores.calcular(df)
    # Señales y backtest solo con velas cerradas: la vela en curso puede cambiar
    cerr = solo_cerradas(df, tf)
    lista = senales.detectar(cerr, PARAMS, x.loc[cerr.index])
    ops = backtest.simular(cerr, lista, m.tipo, REGLAS)

    vis = x.tail(MAX_VELAS_WEB[tf])
    desde_vis = vis.index[0]
    ts = [int(t.timestamp()) for t in vis.index]
    dec = m.decimales + 2

    # Perfil actual (anclado en la última vela)
    ancla = x["ancla"].iloc[-1]
    tramo = df.loc[ancla:]
    perfil = indicadores.perfil_volumen(tramo["high"], tramo["low"], tramo["close"], tramo["volume"], 40)

    hace_2_anios = (df.index[-1] - pd.Timedelta(days=730)).strftime("%Y-%m-%d")
    ultima = lista[-1] if lista else None
    activa = None
    if ultima is not None:
        velas_desde = len(cerr.loc[ultima.fecha:]) - 1
        if velas_desde < VELAS_ACTIVA and ultima.puntos >= REGLAS.puntos_min:
            activa = ultima.a_dict() | {"velas_desde": velas_desde}

    media = df["close"].rolling(REGLAS.filtro_tendencia).mean()
    return {
        "mercado": m.id,
        "tf": tf,
        "rsi": {"t": ts, "v": redondear(vis["rsi"], 1)},
        "niveles": {"t": ts, "poc": redondear(vis["poc"], dec), "vah": redondear(vis["vah"], dec),
                    "val": redondear(vis["val"], dec)},
        "media": {"t": ts, "v": redondear(media.loc[vis.index], dec), "periodo": REGLAS.filtro_tendencia},
        "perfil": None if perfil is None else {
            "ancla": ancla.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "precios": redondear(perfil.precios, dec),
            "volumen": redondear(perfil.volumen, 2),
            "poc": round(perfil.poc, dec), "vah": round(perfil.vah, dec), "val": round(perfil.val, dec),
        },
        "senales": [s.a_dict() for s in lista if s.fecha >= desde_vis],
        "operaciones": backtest.a_dicts([o for o in ops if o.fecha_entrada >= desde_vis.strftime("%Y-%m-%d")]),
        "metricas": {
            "total": backtest.metricas(ops, REGLAS),
            "ultimos_2_anios": backtest.metricas(ops, REGLAS, desde=hace_2_anios),
        },
        "ultima_senal": ultima.a_dict() if ultima else None,
        "senal_activa": activa,
        "tendencia": "alcista" if df["close"].iloc[-1] > media.iloc[-1] else "bajista",
    }


def main() -> int:
    DIR_WEB.mkdir(parents=True, exist_ok=True)
    resumen = {
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "parametros": PARAMS.__dict__,
        "reglas": REGLAS.__dict__,
        "filas": [],
    }
    for m in MERCADOS:
        for tf in TEMPORALIDADES:
            try:
                a = analizar(m, tf)
            except Exception:
                log.exception("%s %s: error", m.id, tf)
                continue
            if a is None:
                continue
            (DIR_WEB / f"analisis_{m.id}_{tf}.json").write_text(
                json.dumps(a, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
            resumen["filas"].append({
                "mercado": m.id, "nombre": m.nombre, "tf": tf, "tendencia": a["tendencia"],
                "total": a["metricas"]["total"], "ultimos_2_anios": a["metricas"]["ultimos_2_anios"],
                "ultima_senal": a["ultima_senal"], "senal_activa": a["senal_activa"],
            })
            t = a["metricas"]["total"]
            log.info("%s %s: %d señales, %d operaciones, R medio %s", m.id, tf, len(a["senales"]),
                     t.get("operaciones", 0), t.get("r_medio"))
    (DIR_WEB / "resumen_senales.json").write_text(
        json.dumps(resumen, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0 if resumen["filas"] else 1


if __name__ == "__main__":
    sys.exit(main())
