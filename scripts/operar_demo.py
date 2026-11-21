"""Corre la operativa demo: cartera simulada + sincronización con la demo de Bitget.

Escribe docs/data/demo.json (para la web) y data/demo/bitget_log.json (registro).
Sin claves de Bitget, solo actualiza la cartera simulada.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analizador import demo  # noqa: E402
from analizador.almacen import DIR_WEB  # noqa: E402
from analizador.bitget_api import BitgetDemo  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    cli = BitgetDemo.desde_entorno()
    logging.info("Bitget demo: %s", "conectado" if cli else "sin claves (solo cartera simulada)")
    res = demo.correr(cli)
    DIR_WEB.mkdir(parents=True, exist_ok=True)
    (DIR_WEB / "demo.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for e in res["estrategias"]:
        logging.info("%s %s: %s operaciones, bitget=%s", e["mercado"], e["tf"],
                     len(e.get("operaciones", [])), e.get("bitget"))
    logging.info("Capital simulado: %s", res["capital"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
