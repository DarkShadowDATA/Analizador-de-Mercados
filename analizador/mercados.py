"""Catálogo de mercados y temporalidades.

Para añadir un mercado nuevo basta con agregar una entrada a MERCADOS.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mercado:
    id: str                 # identificador corto, se usa en nombres de archivo
    nombre: str             # nombre que se muestra en la web
    descripcion: str        # qué instrumento se usa exactamente
    tipo: str               # "indice", "materia_prima", "cripto"
    yahoo: str              # símbolo en Yahoo Finance (fuente principal o respaldo)
    bitget: str | None = None   # símbolo spot en Bitget (fuente principal para cripto)
    decimales: int = 2
    alternativas: tuple = field(default_factory=tuple)  # otros símbolos de referencia


MERCADOS: list[Mercado] = [
    Mercado(
        id="sp500",
        nombre="S&P 500",
        descripcion="Futuro E-mini S&P 500 (ES=F). Se usa el futuro porque trae volumen real negociado.",
        tipo="indice",
        yahoo="ES=F",
        alternativas=("^GSPC", "SPY"),
    ),
    Mercado(
        id="nasdaq100",
        nombre="Nasdaq 100",
        descripcion="Futuro E-mini Nasdaq 100 (NQ=F), con volumen real negociado.",
        tipo="indice",
        yahoo="NQ=F",
        alternativas=("^NDX", "QQQ"),
    ),
    Mercado(
        id="oro",
        nombre="Oro",
        descripcion="Futuro de oro COMEX (GC=F), con volumen real negociado.",
        tipo="materia_prima",
        yahoo="GC=F",
        alternativas=("XAUUSD", "GLD"),
    ),
    Mercado(
        id="btc",
        nombre="Bitcoin",
        descripcion="BTC/USDT spot de Bitget (respaldo: BTC-USD de Yahoo).",
        tipo="cripto",
        yahoo="BTC-USD",
        bitget="BTCUSDT",
    ),
    Mercado(
        id="eth",
        nombre="Ethereum",
        descripcion="ETH/USDT spot de Bitget (respaldo: ETH-USD de Yahoo).",
        tipo="cripto",
        yahoo="ETH-USD",
        bitget="ETHUSDT",
    ),
    Mercado(
        id="op",
        nombre="Optimism",
        descripcion="OP/USDT spot de Bitget (respaldo: OP-USD de Yahoo). Añadido el 22-nov-2026 para la cartera de 4H.",
        tipo="cripto",
        yahoo="OP-USD",
        bitget="OPUSDT",
        decimales=4,
    ),
    Mercado(
        id="inj",
        nombre="Injective",
        descripcion="INJ/USDT spot de Bitget (respaldo: INJ-USD de Yahoo). Añadido el 22-nov-2026 para la cartera de 4H.",
        tipo="cripto",
        yahoo="INJ-USD",
        bitget="INJUSDT",
        decimales=3,
    ),
    Mercado(
        id="bch",
        nombre="Bitcoin Cash",
        descripcion="BCH/USDT spot de Bitget (respaldo: BCH-USD de Yahoo). Añadido el 22-nov-2026 para la cartera de 4H.",
        tipo="cripto",
        yahoo="BCH-USD",
        bitget="BCHUSDT",
        decimales=2,
    ),
    Mercado(
        id="sui",
        nombre="Sui",
        descripcion="SUI/USDT spot de Bitget (respaldo: SUI20947-USD de Yahoo). Añadido el 22-nov-2026 para la cartera de 4H.",
        tipo="cripto",
        yahoo="SUI20947-USD",
        bitget="SUIUSDT",
        decimales=4,
    ),
]

# Temporalidades disponibles. "segundos" es la duración de cada vela.
TEMPORALIDADES: dict[str, int] = {
    "1h": 3600,
    "4h": 4 * 3600,
    "1d": 86400,
}

# Cuántas velas como máximo se mandan a la web por temporalidad
# (el histórico completo se guarda igual en data/*.csv).
MAX_VELAS_WEB: dict[str, int] = {
    "1h": 6000,
    "4h": 4000,
    "1d": 7000,
}


def por_id(mercado_id: str) -> Mercado:
    for m in MERCADOS:
        if m.id == mercado_id:
            return m
    raise KeyError(f"Mercado desconocido: {mercado_id}")
