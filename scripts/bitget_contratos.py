"""Lista los contratos de futuros de Bitget (reales y demo) que interesan al analizador.

Uso: python scripts/bitget_contratos.py
"""
import requests

URL = "https://api.bitget.com/api/v2/mix/market/contracts"
BUSCAR = ("BTC", "ETH", "XAU", "GOLD", "PAXG", "SPX", "US500", "SP500", "NAS", "NDX", "US100", "QQQ", "SPY")

for tipo in ("USDT-FUTURES", "SUSDT-FUTURES", "USDC-FUTURES", "SUSDC-FUTURES"):
    try:
        r = requests.get(URL, params={"productType": tipo}, timeout=20).json()
    except Exception as e:  # noqa: BLE001
        print(tipo, "error", e)
        continue
    datos = r.get("data") or []
    print(f"\n== {tipo}: {len(datos)} contratos (code {r.get('code')})")
    for c in datos:
        s = c.get("symbol", "")
        if any(b in s.upper() for b in BUSCAR):
            print(f"  {s:18} estado={c.get('symbolStatus')} minQty={c.get('minTradeNum')} "
                  f"paso={c.get('sizeMultiplier')} decimales={c.get('pricePlace')} apalancMax={c.get('maxLever')}")
