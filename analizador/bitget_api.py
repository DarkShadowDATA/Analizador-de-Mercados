"""Cliente mínimo de la API v2 de Bitget para futuros en la CUENTA DEMO.

Las claves se leen de variables de entorno (en GitHub van como secrets):
  BITGET_API_KEY, BITGET_API_SECRET, BITGET_PASSPHRASE

Siempre manda la cabecera `paptrading: 1` (trading simulado). Este cliente no
sabe operar en la cuenta real a propósito.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

import requests

BASE = "https://api.bitget.com"
PRODUCTO_DEMO = "SUSDT-FUTURES"
MONEDA_DEMO = "SUSDT"


class ErrorBitget(RuntimeError):
    pass


class BitgetDemo:
    def __init__(self, clave: str, secreto: str, frase: str, sesion: requests.Session | None = None):
        self.clave, self.secreto, self.frase = clave, secreto, frase
        self.s = sesion or requests.Session()

    @classmethod
    def desde_entorno(cls) -> "BitgetDemo | None":
        c, s, f = (os.environ.get(k, "").strip() for k in ("BITGET_API_KEY", "BITGET_API_SECRET", "BITGET_PASSPHRASE"))
        return cls(c, s, f) if c and s and f else None

    # ------------------------------------------------------------------ base
    def _firmar(self, ts: str, metodo: str, ruta: str, cuerpo: str) -> str:
        msg = ts + metodo + ruta + cuerpo
        return base64.b64encode(hmac.new(self.secreto.encode(), msg.encode(), hashlib.sha256).digest()).decode()

    def _pedir(self, metodo: str, ruta: str, params: dict | None = None, cuerpo: dict | None = None):
        consulta = ("?" + urlencode(params)) if params else ""
        texto = json.dumps(cuerpo, separators=(",", ":")) if cuerpo is not None else ""
        ts = str(int(time.time() * 1000))
        cab = {
            "ACCESS-KEY": self.clave,
            "ACCESS-SIGN": self._firmar(ts, metodo, ruta + consulta, texto),
            "ACCESS-TIMESTAMP": ts,
            "ACCESS-PASSPHRASE": self.frase,
            "Content-Type": "application/json",
            "locale": "en-US",
            "paptrading": "1",
        }
        r = self.s.request(metodo, BASE + ruta + consulta, data=texto or None, headers=cab, timeout=20)
        try:
            datos = r.json()
        except ValueError:
            raise ErrorBitget(f"{metodo} {ruta}: HTTP {r.status_code} {r.text[:200]}")
        if str(datos.get("code")) != "00000":
            raise ErrorBitget(f"{metodo} {ruta}: {datos.get('code')} {datos.get('msg')}")
        return datos.get("data")

    def _base(self, simbolo: str) -> dict:
        return {"symbol": simbolo, "productType": PRODUCTO_DEMO, "marginCoin": MONEDA_DEMO}

    # ------------------------------------------------------------------ consultas
    def cuenta(self, simbolo: str) -> dict:
        return self._pedir("GET", "/api/v2/mix/account/account", self._base(simbolo)) or {}

    def capital(self, simbolo: str) -> float:
        c = self.cuenta(simbolo)
        for k in ("accountEquity", "usdtEquity", "equity", "available"):
            if c.get(k) not in (None, ""):
                return float(c[k])
        raise ErrorBitget(f"No encuentro el capital en la respuesta: {list(c)}")

    def posicion(self, simbolo: str) -> dict | None:
        datos = self._pedir("GET", "/api/v2/mix/position/single-position", self._base(simbolo)) or []
        for p in datos:
            if float(p.get("total") or 0) > 0:
                return p
        return None

    def precio(self, simbolo: str) -> float:
        d = self._pedir("GET", "/api/v2/mix/market/ticker", {"symbol": simbolo, "productType": PRODUCTO_DEMO})
        d = d[0] if isinstance(d, list) else d
        return float(d["lastPr"])

    def contrato(self, simbolo: str) -> dict:
        d = self._pedir("GET", "/api/v2/mix/market/contracts", {"symbol": simbolo, "productType": PRODUCTO_DEMO})
        return d[0] if isinstance(d, list) else d

    # ------------------------------------------------------------------ órdenes
    def preparar(self, simbolo: str, apalancamiento: int = 5) -> None:
        """Modo de una sola dirección, margen aislado y apalancamiento bajo (errores no fatales)."""
        for metodo, ruta, cuerpo in (
            ("POST", "/api/v2/mix/account/set-position-mode", {"productType": PRODUCTO_DEMO, "posMode": "one_way_mode"}),
            ("POST", "/api/v2/mix/account/set-margin-mode", self._base(simbolo) | {"marginMode": "isolated"}),
            ("POST", "/api/v2/mix/account/set-leverage", self._base(simbolo) | {"leverage": str(apalancamiento)}),
        ):
            try:
                self._pedir(metodo, ruta, cuerpo=cuerpo)
            except ErrorBitget:
                pass  # ya estaba así, o hay una posición abierta

    def abrir(self, simbolo: str, direccion: int, cantidad: str, stop: str, objetivo: str, id_cliente: str) -> dict:
        cuerpo = self._base(simbolo) | {
            "marginMode": "isolated",
            "size": cantidad,
            "side": "buy" if direccion > 0 else "sell",
            "orderType": "market",
            "clientOid": id_cliente,
            "presetStopLossPrice": stop,
            "presetStopSurplusPrice": objetivo,
        }
        return self._pedir("POST", "/api/v2/mix/order/place-order", cuerpo=cuerpo) or {}

    def cerrar(self, simbolo: str) -> dict:
        return self._pedir("POST", "/api/v2/mix/order/close-positions",
                           cuerpo={"symbol": simbolo, "productType": PRODUCTO_DEMO}) or {}
