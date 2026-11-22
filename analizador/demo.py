"""Operativa demo (paso 4).

Dos capas:
  1. Cartera simulada propia: aplica exactamente las reglas del backtest a las
     señales nuevas desde INICIO, en todos los gráficos de CARTERA. Así S&P 500,
     Nasdaq y oro también se siguen aunque la demo de Bitget no los tenga.
  2. Ejecución en la demo de Bitget: para los gráficos con contrato demo
     (ETH, BTC) copia la posición de la cartera simulada en la cuenta demo,
     con stop y objetivo puestos en Bitget.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

import pandas as pd

from . import backtest, indicadores, rango_asia, senales
from .almacen import DIR_DATOS, cargar, solo_cerradas
from .bitget_api import BitgetDemo, ErrorBitget
from .mercados import por_id

log = logging.getLogger(__name__)

INICIO = "2026-11-23T00:00:00Z"   # lunes: las señales anteriores no cuentan
CAPITAL_INICIAL = 10_000.0
DIR_DEMO = DIR_DATOS / "demo"
ARCHIVO_LOG = DIR_DEMO / "bitget_log.json"


@dataclass(frozen=True)
class Estrategia:
    mercado: str
    tf: str
    bitget: str | None = None   # contrato de la demo de Bitget, si existe
    estrategia: str = "wyckoff"  # "wyckoff" (4H, la que dio ventaja) o "asia" (experimento de 5m)

    @property
    def prioridad(self) -> int:
        # Con un solo contrato por moneda, la 4H manda: puede cerrar una posición del experimento
        return 1 if self.estrategia == "wyckoff" else 0


# 22-nov-2026: rango de 30 velas; 4H fue la única temporalidad positiva en el histórico
# antiguo y en el reciente (sobre todo por ETH). Todo en 4H.
CARTERA = [
    Estrategia("eth", "4h", bitget="SETHSUSDT"),
    Estrategia("btc", "4h", bitget="SBTCSUSDT"),
    Estrategia("oro", "4h"),
    Estrategia("sp500", "4h"),
    Estrategia("nasdaq100", "4h"),
    # 22-nov-2026: criptos extra de Bitget que ganaron en 4H en las dos mitades de su histórico
    # (scripts/backtest_extra_4h.py). DOGE quedó fuera: mejor R total pero 1ª mitad negativa. Ojo: de 19 criptos probadas el promedio fue ~0R, así que elegir las
    # mejores tiene algo de suerte; la demo dirá si se sostienen. Solo en papel (no hay demo en Bitget).
    Estrategia("op", "4h"),
    Estrategia("inj", "4h"),
    Estrategia("bch", "4h"),
    Estrategia("sui", "4h"),
    # 22-nov-2026, decisión de Alejandro: experimento de 5m para tener operaciones diarias.
    # El backtest de 1 año da -0,26 a -0,37R por operación: se mide en vivo, no se espera ganancia.
    Estrategia("eth", "5m", bitget="SETHSUSDT", estrategia="asia"),
    Estrategia("btc", "5m", bitget="SBTCSUSDT", estrategia="asia"),
]


def operaciones_papel(e: Estrategia, reglas: backtest.ReglasBT, params: senales.Parametros,
                      ahora: pd.Timestamp | None = None) -> list[backtest.Operacion]:
    m = por_id(e.mercado)
    df = cargar(e.mercado, e.tf)
    if df.empty:
        return []
    if e.estrategia == "asia":
        return rango_asia.simular(df, INICIO, ahora=ahora)
    x = indicadores.calcular(df)
    cerr = solo_cerradas(df, e.tf, ahora)
    lista = senales.detectar(cerr, params, x.loc[cerr.index])
    inicio = pd.Timestamp(INICIO)
    nuevas = [s for s in lista if s.fecha >= inicio]
    # Se simula sobre todas las velas (incluida la abierta) para entrar en cuanto abre la siguiente
    return backtest.simular(df, nuevas, m.tipo, reglas)


# ----------------------------------------------------------------------------
# Bitget
# ----------------------------------------------------------------------------

def _leer_log() -> list[dict]:
    if ARCHIVO_LOG.exists():
        return json.loads(ARCHIVO_LOG.read_text(encoding="utf-8"))
    return []


def _redondear(valor: float, paso: float) -> str:
    q = Decimal(str(paso))
    return str((Decimal(str(valor)) / q).to_integral_value(rounding=ROUND_DOWN) * q)


def id_cliente(e: Estrategia, op: backtest.Operacion) -> str:
    t = op.fecha_senal.replace("-", "").replace(":", "").replace("T", "").replace("Z", "")
    return f"an-{e.mercado}-{e.tf}-{t}"[:40]


def sincronizar_bitget(cli: BitgetDemo, e: Estrategia, ops: list[backtest.Operacion],
                       reglas: backtest.ReglasBT, registro: list[dict]) -> dict:
    """Hace que la cuenta demo refleje la posición de la cartera simulada."""
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    anotar = lambda accion, **kw: registro.append({"fecha": ahora, "mercado": e.mercado, "tf": e.tf,
                                                   "simbolo": e.bitget, "accion": accion, **kw})
    abierta = next((op for op in ops if op.motivo_salida == "abierta"), None)
    pos = cli.posicion(e.bitget)
    ya_enviadas = {r.get("id_cliente") for r in registro if r.get("accion") == "abrir"}
    omitidas = {r.get("id_cliente") for r in registro if r.get("accion") == "omitir"}

    # ¿Qué estrategia abrió la posición que hay en este contrato?
    aperturas = [r for r in registro if r.get("accion") == "abrir" and r.get("simbolo") == e.bitget]
    duena = aperturas[-1].get("tf") if aperturas else None
    if pos is not None and duena not in (None, e.tf):
        otra = next((x for x in CARTERA if x.bitget == e.bitget and x.tf == duena), None)
        nueva = abierta is not None and id_cliente(e, abierta) not in ya_enviadas
        if nueva and otra is not None and e.prioridad > otra.prioridad:
            cli.cerrar(e.bitget)
            anotar("cerrar", motivo=f"la señal de {e.tf} tiene prioridad sobre la operación de {duena}")
            pos = None
        else:
            if nueva and id_cliente(e, abierta) not in omitidas:
                anotar("omitir", id_cliente=id_cliente(e, abierta), motivo=f"contrato ocupado por {duena}")
            return {"posicion": f"contrato ocupado por la estrategia de {duena}"}

    if abierta is None:
        if pos is not None:
            cli.cerrar(e.bitget)
            anotar("cerrar", motivo="la cartera simulada ya cerró la operación")
        return {"posicion": None}

    oid = id_cliente(e, abierta)
    if pos is not None:
        lado = 1 if pos.get("holdSide") == "long" else -1
        if lado != abierta.direccion:
            cli.cerrar(e.bitget)
            anotar("cerrar", motivo="posición en sentido contrario a la señal")
            pos = None
        else:
            return {"posicion": pos}
    if oid in ya_enviadas or oid in omitidas:
        # Ya se abrió y Bitget la cerró con su stop/objetivo: no se repite
        return {"posicion": None}

    cli.preparar(e.bitget)
    c = cli.contrato(e.bitget)
    precio = cli.precio(e.bitget)
    capital = cli.capital(e.bitget)
    riesgo_unit = abs(precio - abierta.stop)
    if (precio - abierta.stop) * abierta.direccion <= 0 or (abierta.objetivo - precio) * abierta.direccion <= 0:
        anotar("omitir", id_cliente=oid, motivo="el precio ya pasó el stop o el objetivo")
        return {"posicion": None}
    paso = float(c.get("sizeMultiplier") or c.get("minTradeNum") or 0.001)
    minimo = float(c.get("minTradeNum") or paso)
    cantidad = capital * reglas.riesgo_pct / 100 / riesgo_unit
    cant_txt = _redondear(cantidad, paso)
    if float(cant_txt) < minimo:
        anotar("omitir", id_cliente=oid, motivo=f"cantidad {cantidad:.6f} menor al mínimo {minimo}")
        return {"posicion": None}
    decimales = int(c.get("pricePlace") or 2)
    fmt = lambda v: f"{v:.{decimales}f}"
    res = cli.abrir(e.bitget, abierta.direccion, cant_txt, fmt(abierta.stop), fmt(abierta.objetivo), oid)
    anotar("abrir", id_cliente=oid, direccion=abierta.direccion, cantidad=cant_txt, precio_aprox=precio,
           stop=round(abierta.stop, decimales), objetivo=round(abierta.objetivo, decimales),
           capital=round(capital, 2), orden=res.get("orderId"))
    return {"posicion": "enviada"}


# ----------------------------------------------------------------------------
# Corrida completa
# ----------------------------------------------------------------------------

def correr(cli: BitgetDemo | None) -> dict:
    reglas, params = backtest.ReglasBT(), senales.Parametros()
    DIR_DEMO.mkdir(parents=True, exist_ok=True)
    registro = _leer_log()
    salida = {
        "generado": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inicio": INICIO,
        "capital_inicial": CAPITAL_INICIAL,
        "riesgo_pct": reglas.riesgo_pct,
        "bitget": {"conectado": cli is not None},
        "estrategias": [],
    }
    todas: list[tuple[str, float]] = []
    experimento: list[tuple[str, float]] = []
    for e in CARTERA:
        m = por_id(e.mercado)
        fila = {"mercado": e.mercado, "nombre": m.nombre, "tf": e.tf, "decimales": m.decimales,
                "ejecucion": f"Bitget demo {e.bitget}" if e.bitget else "Simulada (Bitget demo no tiene este mercado)",
                "estrategia": e.estrategia, "experimento": e.estrategia != "wyckoff"}
        try:
            ops = operaciones_papel(e, reglas, params)
        except Exception as ex:  # noqa: BLE001
            log.exception("%s %s: error en la cartera simulada", e.mercado, e.tf)
            fila["error"] = str(ex)
            salida["estrategias"].append(fila)
            continue
        fila["operaciones"] = backtest.a_dicts(ops)
        fila["metricas"] = backtest.metricas(ops, reglas)
        destino = todas if e.estrategia == "wyckoff" else experimento
        destino += [(op.fecha_salida, op.r) for op in ops if op.motivo_salida != "abierta"]
        if e.bitget and cli is not None:
            try:
                fila["bitget"] = sincronizar_bitget(cli, e, ops, reglas, registro)
            except (ErrorBitget, Exception) as ex:  # noqa: BLE001
                log.error("%s: error con Bitget: %s", e.bitget, ex)
                previo = [r for r in registro if r.get("simbolo") == e.bitget and r.get("tf") == e.tf]
                if not previo or previo[-1].get("accion") != "error" or previo[-1].get("motivo") != str(ex)[:300]:
                    registro.append({"fecha": salida["generado"], "mercado": e.mercado, "tf": e.tf,
                                     "simbolo": e.bitget, "accion": "error", "motivo": str(ex)[:300]})
                fila["bitget"] = {"error": str(ex)[:300]}
        salida["estrategias"].append(fila)

    # Curva de capital de la cartera simulada (riesgo fijo por operación, compuesto)
    capital = CAPITAL_INICIAL
    curva = [[INICIO, capital]]
    for fecha, r in sorted(todas):
        capital *= 1 + reglas.riesgo_pct / 100 * r
        curva.append([fecha, round(capital, 2)])
    salida["capital"] = round(capital, 2)
    salida["curva"] = curva
    # El experimento de 5m lleva su propia cuenta para no mezclarse con la cartera de 4H
    cap_x = CAPITAL_INICIAL
    for _, r in sorted(experimento):
        cap_x *= 1 + reglas.riesgo_pct / 100 * r
    salida["capital_experimento"] = round(cap_x, 2)

    if cli is not None:
        simbolo = next((e.bitget for e in CARTERA if e.bitget), None)
        try:
            salida["bitget"]["capital"] = round(cli.capital(simbolo), 2)
        except Exception as ex:  # noqa: BLE001
            salida["bitget"]["error"] = str(ex)[:300]
    registro = registro[-500:]
    ARCHIVO_LOG.write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")
    salida["bitget"]["registro"] = registro[-30:]
    return salida

