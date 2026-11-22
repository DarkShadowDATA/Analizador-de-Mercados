"""Actualiza las velas de 5 minutos de BTC y ETH (Bitget) para el experimento intradía.

Guarda data/<mercado>/5m.csv solo desde un día antes del inicio de la demo (archivo pequeño).
Uso: python scripts/velas_5m.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from analizador import almacen, demo, fuentes  # noqa: E402
from analizador.mercados import por_id  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    ok = 0
    desde_min = pd.Timestamp(demo.INICIO) - pd.Timedelta(days=1)
    for mid in sorted({e.mercado for e in demo.CARTERA if e.tf == "5m"}):
        m = por_id(mid)
        viejo = almacen.cargar(mid, "5m")
        desde = viejo.index[-1] - pd.Timedelta(minutes=15) if not viejo.empty else desde_min
        try:
            nuevo = fuentes.bitget(m.bitget, "5m", desde=max(desde, desde_min))
        except Exception as ex:  # noqa: BLE001
            logging.error("%s 5m: %s", mid, ex)
            continue
        unido = almacen.unir(viejo, nuevo)
        unido = unido[unido.index >= desde_min]
        almacen.guardar(mid, "5m", unido)
        logging.info("%s 5m: %d velas, última %s", mid, len(unido), unido.index[-1] if len(unido) else "-")
        ok += 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
