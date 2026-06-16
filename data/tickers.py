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


def get_name(symbol: str) -> str:
    """Nombre legible de un símbolo (o el símbolo si no se encuentra)."""
    df = load_directory()
    hit = df[df["_sym_l"] == str(symbol).lower()]
    return hit.iloc[0]["display"] if len(hit) else str(symbol)
