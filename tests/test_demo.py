import base64
import hashlib
import hmac

import pandas as pd

from analizador import backtest, demo
from analizador.bitget_api import BitgetDemo


def op(motivo="abierta", d=1, fecha="2026-11-23T04:00:00Z"):
    return backtest.Operacion(tipo="spring", direccion=d, puntos=3, fecha_senal=fecha,
                              fecha_entrada=fecha, fecha_salida=fecha, entrada=3000.0, stop=2900.0,
                              objetivo=3200.0, salida=3000.0, motivo_salida=motivo, r=0.0, barras=1)


class ClienteFalso:
    def __init__(self, pos=None, precio=3010.0):
        self.pos, self._precio, self.llamadas = pos, precio, []

    def posicion(self, s): return self.pos
    def preparar(self, s): self.llamadas.append("preparar")
    def contrato(self, s): return {"sizeMultiplier": "0.001", "minTradeNum": "0.001", "pricePlace": "2"}
    def precio(self, s): return self._precio
    def capital(self, s): return 5000.0

    def abrir(self, s, d, cant, stop, obj, oid):
        self.llamadas.append(("abrir", d, cant, stop, obj, oid))
        return {"orderId": "1"}

    def cerrar(self, s):
        self.llamadas.append("cerrar")
        return {}


E = demo.Estrategia("eth", "4h", "SETHSUSDT")


def test_abre_con_riesgo_del_1_por_ciento():
    cli, reg = ClienteFalso(), []
    demo.sincronizar_bitget(cli, E, [op()], backtest.ReglasBT(), reg)
    _, d, cant, stop, obj, oid = cli.llamadas[-1]
    assert d == 1 and stop == "2900.00" and obj == "3200.00"
    # 1 % de 5000 = 50 USDT; riesgo por unidad 3010-2900 = 110 -> 0.454
    assert cant == "0.454"
    assert reg[-1]["accion"] == "abrir" and reg[-1]["id_cliente"] == oid


def test_no_repite_si_bitget_ya_la_cerro():
    cli, reg = ClienteFalso(), []
    demo.sincronizar_bitget(cli, E, [op()], backtest.ReglasBT(), reg)
    cli2 = ClienteFalso()
    demo.sincronizar_bitget(cli2, E, [op()], backtest.ReglasBT(), reg)
    assert not any(isinstance(x, tuple) for x in cli2.llamadas)


def test_cierra_si_la_cartera_ya_cerro():
    cli, reg = ClienteFalso(pos={"holdSide": "long", "total": "0.4"}), []
    demo.sincronizar_bitget(cli, E, [op("tiempo")], backtest.ReglasBT(), reg)
    assert cli.llamadas == ["cerrar"]


def test_no_abre_si_el_precio_ya_paso_el_objetivo():
    cli, reg = ClienteFalso(precio=3250.0), []
    demo.sincronizar_bitget(cli, E, [op()], backtest.ReglasBT(), reg)
    assert reg[-1]["accion"] == "omitir"


def test_firma_bitget():
    cli = BitgetDemo("k", "secreto", "f")
    esperado = base64.b64encode(hmac.new(b"secreto", b"1GET/api?x=1", hashlib.sha256).digest()).decode()
    assert cli._firmar("1", "GET", "/api?x=1", "") == esperado


def test_cartera_simulada_solo_desde_inicio(monkeypatch):
    # Con el inicio en el pasado aparecen operaciones; con el inicio futuro, ninguna
    from analizador.almacen import cargar
    if cargar("eth", "4h").empty:
        return
    monkeypatch.setattr(demo, "INICIO", "2025-01-01T00:00:00Z")
    ops = demo.operaciones_papel(demo.Estrategia("eth", "4h"), backtest.ReglasBT(), demo.senales.Parametros())
    assert ops and all(o.fecha_senal >= "2025-01-01" for o in ops)
    monkeypatch.setattr(demo, "INICIO", "2100-01-01T00:00:00Z")
    assert demo.operaciones_papel(demo.Estrategia("eth", "4h"), backtest.ReglasBT(), demo.senales.Parametros()) == []


E5 = demo.Estrategia("eth", "5m", "SETHSUSDT", estrategia="asia")


def test_5m_no_toca_posicion_de_4h():
    reg = [{"accion": "abrir", "simbolo": "SETHSUSDT", "tf": "4h", "id_cliente": "x"}]
    cli = ClienteFalso(pos={"holdSide": "long", "total": "0.4"})
    res = demo.sincronizar_bitget(cli, E5, [op(d=-1)], backtest.ReglasBT(), reg)
    assert cli.llamadas == [] and "ocupado" in res["posicion"]
    # y no repite el aviso en la siguiente corrida
    n = len(reg)
    demo.sincronizar_bitget(cli, E5, [op(d=-1)], backtest.ReglasBT(), reg)
    assert len(reg) == n
    # sin señal abierta tampoco cierra la posición de 4H
    demo.sincronizar_bitget(cli, E5, [op("stop")], backtest.ReglasBT(), reg)
    assert cli.llamadas == []


def test_4h_tiene_prioridad_sobre_5m():
    reg = [{"accion": "abrir", "simbolo": "SETHSUSDT", "tf": "5m", "id_cliente": "x"}]
    cli = ClienteFalso(pos={"holdSide": "short", "total": "0.4"})
    demo.sincronizar_bitget(cli, E, [op()], backtest.ReglasBT(), reg)
    assert cli.llamadas[0] == "cerrar" and cli.llamadas[-1][0] == "abrir"
