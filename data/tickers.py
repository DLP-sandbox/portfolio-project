"""Directorio de tickers + búsqueda con autocompletado (NYSE / NASDAQ).

Carga `data/ticker_directory.csv` (generado por scripts/build_ticker_directory.py).
Si no existe, usa una lista curada de respaldo. `search_tickers` matchea por símbolo y
por nombre, priorizando coincidencias de símbolo.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

DIRECTORY_CSV = Path(__file__).parent / "ticker_directory.csv"

# Respaldo curado (si falta el CSV completo): populares de EE.UU. + ETFs.
_CURATED = [
    ("AAPL", "Apple Inc.", "NASDAQ", "N"), ("MSFT", "Microsoft Corporation", "NASDAQ", "N"),
    ("NVDA", "NVIDIA Corporation", "NASDAQ", "N"), ("AMZN", "Amazon.com Inc.", "NASDAQ", "N"),
    ("GOOGL", "Alphabet Inc. Class A", "NASDAQ", "N"), ("META", "Meta Platforms Inc.", "NASDAQ", "N"),
    ("TSLA", "Tesla Inc.", "NASDAQ", "N"), ("BRK-B", "Berkshire Hathaway Inc. Class B", "NYSE", "N"),
    ("JPM", "JPMorgan Chase & Co.", "NYSE", "N"), ("V", "Visa Inc.", "NYSE", "N"),
    ("JNJ", "Johnson & Johnson", "NYSE", "N"), ("WMT", "Walmart Inc.", "NYSE", "N"),
    ("PG", "Procter & Gamble Co.", "NYSE", "N"), ("KO", "Coca-Cola Company", "NYSE", "N"),
    ("MA", "Mastercard Inc.", "NYSE", "N"), ("HD", "Home Depot Inc.", "NYSE", "N"),
    ("COST", "Costco Wholesale Corporation", "NASDAQ", "N"), ("AMD", "Advanced Micro Devices", "NASDAQ", "N"),
    ("SPY", "SPDR S&P 500 ETF Trust", "NYSE Arca", "Y"), ("VOO", "Vanguard S&P 500 ETF", "NYSE Arca", "Y"),
    ("VTI", "Vanguard Total Stock Market ETF", "NYSE Arca", "Y"), ("QQQ", "Invesco QQQ Trust", "NASDAQ", "Y"),
    ("BND", "Vanguard Total Bond Market ETF", "NASDAQ", "Y"), ("TLT", "iShares 20+ Year Treasury", "NASDAQ", "Y"),
    ("IEF", "iShares 7-10 Year Treasury", "NASDAQ", "Y"), ("GLD", "SPDR Gold Shares", "NYSE Arca", "Y"),
    ("DBC", "Invesco DB Commodity Index", "NYSE Arca", "Y"), ("SCHD", "Schwab US Dividend Equity ETF", "NYSE Arca", "Y"),
    ("VYM", "Vanguard High Dividend Yield ETF", "NYSE Arca", "Y"), ("VXUS", "Vanguard Total Intl Stock ETF", "NASDAQ", "Y"),
]

_NAME_SUFFIX = re.compile(r"\s*-?\s*(New\s+)?(Class\s+[A-Z]\s+)?Common\stock.*$", re.IGNORECASE)


def clean_name(name: str) -> str:
    """Acorta el nombre para mostrar (saca 'Common Stock', etc)."""
    n = _NAME_SUFFIX.sub("", str(name)).strip(" -")
    return n or str(name)


def _load() -> pd.DataFrame:
    if DIRECTORY_CSV.exists():
        try:
            df = pd.read_csv(DIRECTORY_CSV)
        except Exception:
            df = pd.DataFrame(_CURATED, columns=["symbol", "name", "exchange", "is_etf"])
    else:
        df = pd.DataFrame(_CURATED, columns=["symbol", "name", "exchange", "is_etf"])
    df["symbol"] = df["symbol"].astype(str)
    df["name"] = df["name"].astype(str)
    df["display"] = df["name"].map(clean_name)
    df["_sym_l"] = df["symbol"].str.lower()
    df["_name_l"] = df["display"].str.lower()
    return df


def load_directory():
    """DataFrame del directorio (cacheado vía Streamlit si está disponible)."""
    try:
        import streamlit as st

        return st.cache_data(show_spinner=False)(_load)()
    except Exception:
        return _load()


def search_tickers(query: str, limit: int = 8) -> list[dict]:
    """Busca por símbolo o nombre. Prioriza: símbolo exacto > símbolo empieza con > nombre contiene."""
    q = (query or "").strip().lower()
    if not q:
        return []
    df = load_directory()
    sym_exact = df[df["_sym_l"] == q]
    sym_pref = df[df["_sym_l"].str.startswith(q) & (df["_sym_l"] != q)]
    name_match = df[df["_name_l"].str.contains(re.escape(q)) & ~df["_sym_l"].str.startswith(q)]
    out = pd.concat([sym_exact, sym_pref, name_match]).head(limit)
    return [{"symbol": r.symbol, "name": r.display, "exchange": r.exchange,
             "is_etf": r.is_etf == "Y"} for r in out.itertuples()]


def get_name_local(symbol: str) -> str:
    """Nombre desde el directorio local (solo EE.UU.). Nunca toca la red."""
    df = load_directory()
    hit = df[df["_sym_l"] == str(symbol).lower()]
    return hit.iloc[0]["display"] if len(hit) else str(symbol)


# ── Búsqueda global (mercados fuera de EE.UU.) ───────────────────────────────
# El directorio local solo cubre NYSE/NASDAQ. Para ETFs UCITS europeos y acciones
# de Asia/LatAm se consulta el buscador de Yahoo en vivo, que sí devuelve símbolos
# con sufijo de mercado (IWDA.AS, 7203.T, PETR4.SA…). Todo va cacheado y dentro de
# try/except: si no hay red, la búsqueda local sigue funcionando igual que siempre.
_GLOBAL_TYPES = {"EQUITY", "ETF", "MUTUALFUND", "CRYPTOCURRENCY"}
_REMOTE_NAMES: dict[str, str] = {}


def _clean_remote_name(name: str) -> str:
    """Los nombres de Yahoo llegan con relleno ('SAP SE            I'). Se colapsan
    los espacios y se recorta. Solo se aplica a resultados remotos: el directorio
    local sigue usando `clean_name` tal cual."""
    return re.sub(r"\s{2,}", " ", str(name or "")).strip(" -")


def _search_global(query: str, limit: int = 6) -> list[dict]:
    try:
        import yfinance as yf

        quotes = yf.Search(query, max_results=max(limit * 2, 10)).quotes or []
    except Exception:
        return []
    out: list[dict] = []
    for q in quotes:
        if len(out) >= limit:
            break
        try:
            sym = str(q.get("symbol") or "").strip()
            qt = str(q.get("quoteType") or "").upper()
            if not sym or qt not in _GLOBAL_TYPES:
                continue
            # En algunos fondos Yahoo repite el símbolo en `shortname` y deja el
            # nombre real en `longname`; hay que quedarse con el útil.
            short = str(q.get("shortname") or "").strip()
            name = short if short and short.upper() != sym.upper() else q.get("longname")
            if not name:
                continue  # sin nombre aprovechable: no sirve para elegir
            out.append({"symbol": sym, "name": _clean_remote_name(clean_name(name)),
                        "exchange": str(q.get("exchDisp") or q.get("exchange") or ""),
                        "is_etf": qt in ("ETF", "MUTUALFUND")})
        except Exception:
            continue
    return out


def search_global(query: str, limit: int = 6) -> list[dict]:
    """Resultados de mercados internacionales (cacheados 1 h). [] si no hay red."""
    q = (query or "").strip()
    if len(q) < 2:  # evita una llamada de red en la primera pulsación
        return []
    try:
        import streamlit as st

        res = st.cache_data(show_spinner=False, ttl=3600)(_search_global)(q, limit)
    except Exception:
        res = _search_global(q, limit)
    for r in res or []:
        _REMOTE_NAMES.setdefault(str(r["symbol"]).upper(), r["name"])
    return list(res or [])


def search_tickers_all(query: str, limit: int = 8) -> list[dict]:
    """Búsqueda completa: primero el directorio local (instantáneo), después los
    mercados internacionales. Reserva hasta 3 huecos para que los resultados de
    fuera de EE.UU. nunca queden desplazados por los locales."""
    local = search_tickers(query, limit=limit)
    glob = search_global(query, limit=limit)
    if not glob:
        return local
    reserve = min(3, len(glob))
    out = list(local[: max(limit - reserve, 1)])
    seen = {str(r["symbol"]).upper() for r in out}
    for r in glob:
        if len(out) >= limit:
            break
        if str(r["symbol"]).upper() in seen:
            continue
        seen.add(str(r["symbol"]).upper())
        out.append(r)
    return out


def _remote_name(symbol: str) -> str:
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        # longName primero: es el nombre limpio y completo ("iShares Core MSCI World
        # UCITS ETF USD (Acc)"); shortName viene truncado y con relleno.
        return _clean_remote_name(clean_name(info.get("longName") or info.get("shortName") or ""))
    except Exception:
        return ""


def get_name(symbol: str) -> str:
    """Nombre legible de un símbolo. Para los que no están en el directorio de
    EE.UU. (internacionales) resuelve el nombre en vivo y lo cachea."""
    df = load_directory()
    hit = df[df["_sym_l"] == str(symbol).lower()]
    if len(hit):
        return hit.iloc[0]["display"]
    s = str(symbol).upper()
    if s in _REMOTE_NAMES:
        return _REMOTE_NAMES[s]
    try:
        import streamlit as st

        name = st.cache_data(show_spinner=False, ttl=86400)(_remote_name)(s)
    except Exception:
        name = _remote_name(s)
    if name:
        _REMOTE_NAMES[s] = name
        return name
    return str(symbol)


# Sets conocidos para clasificar el tipo de activo (para el buscador).
_CRYPTO = {"IBIT", "GBTC", "FBTC", "ETHE", "BITO", "ETHA", "ARKB", "BITB", "HODL", "EZBC"}
_BOND_HINTS = ("bond", "treasury", "aggregate", "fixed income", "municipal", "tips", "corporate bond")


def classify_type(symbol: str, name: str, is_etf: bool) -> str:
    """Tipo legible del activo: Crypto / Bono / ETF / Acción (heurística simple)."""
    s = str(symbol).upper()
    n = (name or "").lower()
    if s in _CRYPTO or "bitcoin" in n or "ethereum" in n or "crypto" in n:
        return "Crypto"
    if is_etf and any(h in n for h in _BOND_HINTS):
        return "Bono"
    return "ETF" if is_etf else "Acción"


def _build_option_index() -> tuple[list[str], dict[str, str]]:
    """(símbolos, {símbolo: etiqueta rica}) para el buscador tipo dropdown."""
    df = load_directory()
    syms: list[str] = []
    labels: dict[str, str] = {}
    for r in df.itertuples():
        t = classify_type(r.symbol, r.display, r.is_etf == "Y")
        name = (r.display or "")[:36]
        syms.append(r.symbol)
        labels[r.symbol] = f"{r.symbol}   ·   {name}   ·   {r.exchange} · {t}"
    return syms, labels


def option_index() -> tuple[list[str], dict[str, str]]:
    """Versión cacheada de `_build_option_index` (si Streamlit está disponible)."""
    try:
        import streamlit as st

        return st.cache_data(show_spinner=False)(_build_option_index)()
    except Exception:
        return _build_option_index()
