"""Clasificación de activos: clase (Acciones/ETF/Bonos/Materias primas/Cripto) y sector.

Fuente principal: yfinance `.info` — para acciones trae `sector` (GICS) y para ETFs trae
`category` de Morningstar ("Intermediate Core Bond", "Commodities Focused", "Digital
Assets"…), que resuelve muy bien la clase de activo.

Diseñado para NO romper nunca la app: cada consulta va en `try/except`, cacheada 24 h, y
si la red falla cae a un mapa curado local y luego a la heurística del directorio. En el
peor caso devuelve "Sin clasificar" — nunca lanza.
"""
from __future__ import annotations

from data import tickers as tdir

# ── Clases de activo (etiquetas visibles) ───────────────────────────────────
CLS_STOCK = "Acciones"
CLS_ETF = "ETF"
CLS_BOND = "Bonos"
CLS_COMMOD = "Materias primas"
CLS_CRYPTO = "Cripto"
UNKNOWN = "Sin clasificar"

# GICS (inglés → español)
_SECTOR_ES = {
    "technology": "Tecnología", "information technology": "Tecnología",
    "financial services": "Finanzas", "financials": "Finanzas",
    "healthcare": "Salud", "health care": "Salud",
    "consumer cyclical": "Consumo discrecional", "consumer discretionary": "Consumo discrecional",
    "consumer defensive": "Consumo básico", "consumer staples": "Consumo básico",
    "energy": "Energía", "industrials": "Industria",
    "basic materials": "Materiales", "materials": "Materiales",
    "utilities": "Servicios públicos", "real estate": "Inmobiliario",
    "communication services": "Comunicaciones",
}


# Claves de `funds_data.sector_weightings` (snake_case) → español
_MIX_ES = {
    "technology": "Tecnología", "financial_services": "Finanzas", "healthcare": "Salud",
    "consumer_cyclical": "Consumo discrecional", "consumer_defensive": "Consumo básico",
    "energy": "Energía", "industrials": "Industria", "basic_materials": "Materiales",
    "utilities": "Servicios públicos", "real_estate": "Inmobiliario", "realestate": "Inmobiliario",
    "communication_services": "Comunicaciones",
}

# Pistas sobre la `category` de un ETF → (clase, sector)
_CAT_RULES = [
    (("bond", "treasury", "fixed income", "municipal", "tips", "government"), (CLS_BOND, "Renta fija")),
    (("commodit", "gold", "silver", "precious", "energy limited", "natural resources"), (CLS_COMMOD, "Materias primas")),
    (("digital asset", "crypto", "bitcoin", "blockchain"), (CLS_CRYPTO, "Cripto")),
    (("technology", "semiconductor"), (CLS_ETF, "Tecnología")),
    (("health",), (CLS_ETF, "Salud")),
    (("financial",), (CLS_ETF, "Finanzas")),
    (("energy",), (CLS_ETF, "Energía")),
    (("real estate",), (CLS_ETF, "Inmobiliario")),
    (("utilities",), (CLS_ETF, "Servicios públicos")),
    (("consumer",), (CLS_ETF, "Consumo")),
    (("industrial",), (CLS_ETF, "Industria")),
    (("communication",), (CLS_ETF, "Comunicaciones")),
]

# Respaldo curado para los tickers más habituales (si no hay red)
_CURATED = {
    "SPY": (CLS_ETF, "Mercado completo"), "VOO": (CLS_ETF, "Mercado completo"),
    "VTI": (CLS_ETF, "Mercado completo"), "IVV": (CLS_ETF, "Mercado completo"),
    "QQQ": (CLS_ETF, "Tecnología"), "VGT": (CLS_ETF, "Tecnología"),
    # ETFs sectoriales conocidos: aseguran una clasificación correcta incluso sin red
    "XLK": (CLS_ETF, "Tecnología"), "XLE": (CLS_ETF, "Energía"),
    "XLI": (CLS_ETF, "Industria"), "XLF": (CLS_ETF, "Finanzas"),
    "XLV": (CLS_ETF, "Salud"), "XLY": (CLS_ETF, "Consumo discrecional"),
    "XLP": (CLS_ETF, "Consumo básico"), "XLU": (CLS_ETF, "Servicios públicos"),
    "XLB": (CLS_ETF, "Materiales"), "XLRE": (CLS_ETF, "Inmobiliario"),
    "XLC": (CLS_ETF, "Comunicaciones"), "VNQ": (CLS_ETF, "Inmobiliario"),
    "GRID": (CLS_ETF, "Industria"), "ICLN": (CLS_ETF, "Servicios públicos"),
    "TAN": (CLS_ETF, "Tecnología"), "TIP": (CLS_BOND, "Renta fija"),
    "SOXX": (CLS_ETF, "Tecnología"), "SMH": (CLS_ETF, "Tecnología"),
    "VXUS": (CLS_ETF, "Mercado completo"), "VEA": (CLS_ETF, "Mercado completo"),
    "BND": (CLS_BOND, "Renta fija"), "AGG": (CLS_BOND, "Renta fija"),
    "TLT": (CLS_BOND, "Renta fija"), "IEF": (CLS_BOND, "Renta fija"),
    "GLD": (CLS_COMMOD, "Materias primas"), "SLV": (CLS_COMMOD, "Materias primas"),
    "DBC": (CLS_COMMOD, "Materias primas"), "USO": (CLS_COMMOD, "Materias primas"),
    "IBIT": (CLS_CRYPTO, "Cripto"), "GBTC": (CLS_CRYPTO, "Cripto"), "FBTC": (CLS_CRYPTO, "Cripto"),
    "AAPL": (CLS_STOCK, "Tecnología"), "MSFT": (CLS_STOCK, "Tecnología"),
    "NVDA": (CLS_STOCK, "Tecnología"), "GOOGL": (CLS_STOCK, "Comunicaciones"),
    "META": (CLS_STOCK, "Comunicaciones"), "AMZN": (CLS_STOCK, "Consumo discrecional"),
    "TSLA": (CLS_STOCK, "Consumo discrecional"), "AVGO": (CLS_STOCK, "Tecnología"),
    "AMD": (CLS_STOCK, "Tecnología"), "PLTR": (CLS_STOCK, "Tecnología"),
    "CRWD": (CLS_STOCK, "Tecnología"), "JPM": (CLS_STOCK, "Finanzas"),
    "V": (CLS_STOCK, "Finanzas"), "MA": (CLS_STOCK, "Finanzas"),
    "XOM": (CLS_STOCK, "Energía"), "CVX": (CLS_STOCK, "Energía"),
    "JNJ": (CLS_STOCK, "Salud"), "UNH": (CLS_STOCK, "Salud"),
    "WMT": (CLS_STOCK, "Consumo básico"), "PG": (CLS_STOCK, "Consumo básico"),
    "KO": (CLS_STOCK, "Consumo básico"), "COST": (CLS_STOCK, "Consumo básico"),
    "HD": (CLS_STOCK, "Consumo discrecional"), "BRK-B": (CLS_STOCK, "Finanzas"),
}


def _match_category(cat: str) -> tuple[str, str] | None:
    c = (cat or "").lower()
    if not c:
        return None
    for keys, out in _CAT_RULES:
        if any(k in c for k in keys):
            return out
    return (CLS_ETF, "Mercado completo")   # ETF de índice amplio


def _fallback(symbol: str) -> tuple[str, str]:
    """Sin red: mapa curado → heurística del directorio → sin clasificar."""
    s = str(symbol).upper()
    if s in _CURATED:
        return _CURATED[s]
    try:
        name = tdir.get_name(s)
        df = tdir.load_directory()
        hit = df[df["_sym_l"] == s.lower()]
        is_etf = bool(len(hit)) and hit.iloc[0]["is_etf"] == "Y"
        t = tdir.classify_type(s, name, is_etf)
        if t == "Crypto":
            return (CLS_CRYPTO, "Cripto")
        if t == "Bono":
            return (CLS_BOND, "Renta fija")
        if t == "ETF":
            return (CLS_ETF, "Mercado completo")
        return (CLS_STOCK, UNKNOWN)
    except Exception:
        return (CLS_STOCK, UNKNOWN)


def _sector_mix(ticker) -> dict:
    """Reparto real por sectores de un ETF (`funds_data.sector_weightings`), en español.

    Devuelve {sector: peso} normalizado a 1, o {} si el fondo no expone el dato (bonos,
    materias primas, cripto) o si falla la consulta.
    """
    try:
        raw = ticker.funds_data.sector_weightings or {}
    except Exception:
        return {}
    mix: dict[str, float] = {}
    for k, v in raw.items():
        try:
            w = float(v)
        except (TypeError, ValueError):
            continue
        if w <= 0:
            continue
        mix[_MIX_ES.get(str(k).lower(), str(k).title())] = mix.get(
            _MIX_ES.get(str(k).lower(), str(k).title()), 0.0) + w
    total = sum(mix.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in mix.items()}


def _fetch_profile(symbol: str) -> dict:
    """Perfil de un símbolo desde yfinance, con caída elegante al respaldo local."""
    s = str(symbol).upper()
    try:
        import yfinance as yf

        t = yf.Ticker(s)
        info = t.info or {}
        qt = (info.get("quoteType") or "").upper()
        sector = info.get("sector")
        category = info.get("category")

        if qt == "CRYPTOCURRENCY":
            return {"symbol": s, "class": CLS_CRYPTO, "sector": "Cripto", "mix": {"Cripto": 1.0}}
        if qt == "EQUITY" and sector:
            sec_es = _SECTOR_ES.get(str(sector).lower(), str(sector))
            return {"symbol": s, "class": CLS_STOCK, "sector": sec_es, "mix": {sec_es: 1.0}}
        if category:
            cls, sec = _match_category(category)
            # Para ETFs de renta variable, el reparto REAL por sectores de sus posiciones
            # (`funds_data.sector_weightings`) es la fuente exacta: un ETF de infraestructura
            # o sectorial deja de caer en el cajón genérico de "Mercado completo".
            if cls == CLS_ETF:
                mix = _sector_mix(t)
                if mix:
                    top = max(mix.items(), key=lambda x: x[1])[0]
                    return {"symbol": s, "class": cls, "sector": top, "mix": mix}
            return {"symbol": s, "class": cls, "sector": sec, "mix": {sec: 1.0}}
        if qt == "EQUITY":
            return {"symbol": s, "class": CLS_STOCK, "sector": UNKNOWN, "mix": {UNKNOWN: 1.0}}
    except Exception:
        pass
    cls, sec = _fallback(s)
    return {"symbol": s, "class": cls, "sector": sec, "mix": {sec: 1.0}}


def get_asset_profile(symbol: str) -> dict:
    """Perfil cacheado 24 h: {'symbol', 'class', 'sector'}. Nunca lanza."""
    try:
        import streamlit as st

        return st.cache_data(ttl=86400, max_entries=512, show_spinner=False)(_fetch_profile)(symbol)
    except Exception:
        return _fetch_profile(symbol)


def portfolio_exposure(items: list[dict]) -> dict:
    """Exposición del portafolio ponderada por el capital de cada activo.

    `items`: [{"symbol", "weight" (= monto invertido)}, ...]
    Returns {"by_sector": [{"name", "pct"}...], "by_class": [...]} ordenado desc y en %.
    """
    total = sum(max(float(it.get("weight", 0)), 0.0) for it in items) or 1.0
    sec: dict[str, float] = {}
    cls: dict[str, float] = {}
    for it in items:
        amt = max(float(it.get("weight", 0)), 0.0)
        if amt <= 0:
            continue
        p = get_asset_profile(it["symbol"])
        share = amt / total * 100.0
        # El dinero de cada activo se reparte entre SUS sectores reales (un ETF sectorial
        # o de infraestructura aporta a varios), no a una sola etiqueta aproximada.
        mix = p.get("mix") or {p.get("sector", UNKNOWN): 1.0}
        for sname, sw in mix.items():
            sec[sname] = sec.get(sname, 0.0) + share * float(sw)
        cls[p["class"]] = cls.get(p["class"], 0.0) + share

    def _rows(d: dict) -> list[dict]:
        return [{"name": k, "pct": v} for k, v in sorted(d.items(), key=lambda x: -x[1])]

    return {"by_sector": _rows(sec), "by_class": _rows(cls)}


def top_sectors(rows: list[dict], n: int = 6) -> list[dict]:
    """Top n-1 sectores + 'Otros' con el resto, para que el gráfico SIEMPRE sume 100%."""
    if len(rows) <= n:
        return rows
    head = rows[:n - 1]
    resto = sum(r["pct"] for r in rows[n - 1:])
    return head + [{"name": "Otros", "pct": resto}]
