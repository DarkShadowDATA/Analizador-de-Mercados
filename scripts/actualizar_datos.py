"""Descarga/actualiza todos los mercados y regenera los datos de la web.

Uso:
    python scripts/actualizar_datos.py              # todos los mercados
    python scripts/actualizar_datos.py btc oro      # solo algunos
    python scripts/actualizar_datos.py --solo-web   # solo regenerar docs/data
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from analizador import almacen, fuentes  # noqa: E402
from analizador.mercados import MERCADOS, TEMPORALIDADES  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("actualizar")


def actualizar_serie(mercado, tf: str, estado: dict) -> bool:
    viejo = almacen.cargar(mercado.id, tf)
    est = estado.setdefault(mercado.id, {}).setdefault(tf, {})
    # Incremental: volver unas velas atrás para corregir la última (que estaba abierta)
    desde = None
    if not viejo.empty:
        desde = viejo.index[-1] - pd.Timedelta(seconds=TEMPORALIDADES[tf] * 3)

    nuevo, fuente = fuentes.descargar(mercado, tf, desde)
    if nuevo.empty:
        log.error("%s %s: sin datos", mercado.id, tf)
        return False

    fuente_previa = est.get("fuente")
    if fuente_previa and fuente_previa != fuente and not viejo.empty:
        # No mezclar fuentes distintas (el volumen no es comparable).
        log.warning("%s %s: hoy vino de %s pero el histórico es de %s; no se mezcla",
                    mercado.id, tf, fuente, fuente_previa)
        return False

    unido = almacen.unir(viejo, nuevo)
    almacen.guardar(mercado.id, tf, unido)
    est.update({
        "fuente": fuente,
        "velas": len(unido),
        "ultima_vela": unido.index[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actualizado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    log.info("%s %s: %d velas (%s), +%d nuevas", mercado.id, tf, len(unido), fuente,
             len(unido) - len(viejo))
    return True


def main(args: list[str]) -> int:
    solo_web = "--solo-web" in args
    ids = [a for a in args if not a.startswith("--")]
    estado = almacen.leer_estado()
    fallos = 0
    if not solo_web:
        for m in MERCADOS:
            if ids and m.id not in ids:
                continue
            for tf in TEMPORALIDADES:
                try:
                    if not actualizar_serie(m, tf, estado):
                        fallos += 1
                except Exception:
                    log.exception("%s %s: error", m.id, tf)
                    fallos += 1
        almacen.escribir_estado(estado)
    indice = almacen.exportar_web(estado)
    log.info("Web regenerada: %d mercados. Fallos: %d", len(indice["mercados"]), fallos)
    # Falla solo si no hay nada que mostrar; un mercado caído no tumba el resto.
    hay_datos = any(m["series"] for m in indice["mercados"])
    return 0 if hay_datos else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
