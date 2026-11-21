"""Guardado de velas y exportación para la web.

- data/<mercado>/<temporalidad>.csv : histórico completo (fuente de verdad).
- data/estado.json                  : de qué fuente viene cada serie y cuándo se actualizó.
- docs/data/<mercado>_<tf>.json     : últimas velas en formato compacto para la web.
- docs/data/indice.json             : resumen de todos los mercados para la portada.

Los pasos siguientes (señales, backtesting, reportes) leen con `cargar()`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .fuentes import COLUMNAS, normalizar, vacio
from .mercados import MAX_VELAS_WEB, MERCADOS, TEMPORALIDADES, por_id

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATOS = RAIZ / "data"
DIR_WEB = RAIZ / "docs" / "data"
ARCHIVO_ESTADO = DIR_DATOS / "estado.json"


def ruta_csv(mercado_id: str, tf: str) -> Path:
    return DIR_DATOS / mercado_id / f"{tf}.csv"


def cargar(mercado_id: str, tf: str = "1d") -> pd.DataFrame:
    """Velas guardadas de un mercado. Índice UTC, columnas open/high/low/close/volume."""
    ruta = ruta_csv(mercado_id, tf)
    if not ruta.exists():
        return vacio()
    df = pd.read_csv(ruta, index_col="fecha")
    df.index = pd.to_datetime(df.index, utc=True)
    return normalizar(df)


def solo_cerradas(df: pd.DataFrame, tf: str, ahora: pd.Timestamp | None = None,
                  margen: pd.Timedelta = pd.Timedelta(minutes=15)) -> pd.DataFrame:
    """Quita la vela que sigue abierta (y da un margen por el retraso de los datos)."""
    ahora = ahora if ahora is not None else pd.Timestamp.now(tz="UTC")
    fin = df.index + pd.Timedelta(seconds=TEMPORALIDADES[tf])
    return df[fin + margen <= ahora]


def guardar(mercado_id: str, tf: str, df: pd.DataFrame) -> None:
    ruta = ruta_csv(mercado_id, tf)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    salida = df[COLUMNAS].copy()
    salida.index = salida.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    salida.index.name = "fecha"
    salida.to_csv(ruta, float_format="%.8g")


def unir(viejo: pd.DataFrame, nuevo: pd.DataFrame) -> pd.DataFrame:
    """Une histórico con velas nuevas; las nuevas pisan a las viejas (la última vela se corrige)."""
    if viejo.empty:
        return normalizar(nuevo)
    if nuevo.empty:
        return viejo
    return normalizar(pd.concat([viejo, nuevo]))


def leer_estado() -> dict:
    if ARCHIVO_ESTADO.exists():
        return json.loads(ARCHIVO_ESTADO.read_text(encoding="utf-8"))
    return {}


def escribir_estado(estado: dict) -> None:
    ARCHIVO_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------
# Exportación para la web
# --------------------------------------------------------------------------

def _serie_web(df: pd.DataFrame, tf: str, decimales: int) -> dict:
    df = df.tail(MAX_VELAS_WEB[tf])
    r = lambda col: [round(float(x), decimales + 2) for x in df[col]]
    return {
        "t": [int(ts.timestamp()) for ts in df.index],
        "o": r("open"), "h": r("high"), "l": r("low"), "c": r("close"),
        "v": [round(float(x), 4) for x in df["volume"]],
    }


def exportar_web(estado: dict) -> dict:
    DIR_WEB.mkdir(parents=True, exist_ok=True)
    indice = {
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temporalidades": list(TEMPORALIDADES),
        "mercados": [],
    }
    for m in MERCADOS:
        info = {
            "id": m.id, "nombre": m.nombre, "descripcion": m.descripcion,
            "tipo": m.tipo, "decimales": m.decimales, "bitget": m.bitget,
            "series": {},
        }
        for tf in TEMPORALIDADES:
            df = cargar(m.id, tf)
            if df.empty:
                continue
            (DIR_WEB / f"{m.id}_{tf}.json").write_text(
                json.dumps(_serie_web(df, tf, m.decimales), separators=(",", ":")), encoding="utf-8"
            )
            est = estado.get(m.id, {}).get(tf, {})
            info["series"][tf] = {
                "velas": len(df),
                "desde": df.index[0].strftime("%Y-%m-%d"),
                "hasta": df.index[-1].strftime("%Y-%m-%dT%H:%MZ"),
                "fuente": est.get("fuente", "?"),
            }
        diario = cargar(m.id, "1d")
        if len(diario) >= 2:
            ultimo, previo = diario["close"].iloc[-1], diario["close"].iloc[-2]
            info["ultimo"] = round(float(ultimo), m.decimales)
            info["cambio_pct"] = round(float((ultimo / previo - 1) * 100), 2)
        indice["mercados"].append(info)

    (DIR_WEB / "indice.json").write_text(
        json.dumps(indice, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    return indice


__all__ = ["cargar", "solo_cerradas", "guardar", "unir", "exportar_web", "leer_estado", "escribir_estado", "por_id"]
