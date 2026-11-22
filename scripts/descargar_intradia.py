"""Descarga velas de 5 minutos de Bitget (BTC, ETH) para el backtest intradía.

Guarda data/intradia/<mercado>_5m.csv.gz (comprimido; no entra en la actualización horaria).
Uso: python scripts/descargar_intradia.py [dias]
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from analizador import fuentes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
DIR = Path(__file__).resolve().parent.parent / "data" / "intradia"
MERCADOS = {"btc": "BTCUSDT", "eth": "ETHUSDT"}


# Criptos extra para ampliar la cartera de 4H (22-nov-2026)
EXTRA_4H = ["SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "DOTUSDT",
            "LTCUSDT", "BCHUSDT", "TRXUSDT", "SUIUSDT", "TONUSDT", "NEARUSDT", "APTUSDT", "ARBUSDT",
            "OPUSDT", "INJUSDT", "ATOMUSDT", "UNIUSDT"]


def extra_4h():
    for sym in EXTRA_4H:
        try:
            df = fuentes.bitget(sym, "4h")
        except Exception as ex:  # noqa: BLE001
            logging.error("%s: %s", sym, ex)
            continue
        out = df.copy()
        out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
        out.to_csv(DIR / f"{sym.lower()}_4h.csv.gz", float_format="%.8g", compression="gzip")
        logging.info("%s: %d velas de 4h desde %s", sym, len(df), df.index[0] if len(df) else "-")
    return 0


def main(args):
    if args and args[0] == "extra4h":
        DIR.mkdir(parents=True, exist_ok=True)
        return extra_4h()
    dias = int(args[0]) if args else 365
    DIR.mkdir(parents=True, exist_ok=True)
    for mid, sym in MERCADOS.items():
        desde = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=dias)
        df = fuentes.bitget(sym, "5m", desde=desde)
        out = df.copy()
        out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
        out.to_csv(DIR / f"{mid}_5m.csv.gz", float_format="%.8g", compression="gzip")
        logging.info("%s: %d velas de 5m desde %s", mid, len(df), df.index[0] if len(df) else "-")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
