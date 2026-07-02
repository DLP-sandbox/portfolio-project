"""Capa de datos de mercado: yfinance con caché + fallback de muestra.

Patrón 3 del spec: sanitizar y validar tickers ANTES de gastar llamadas de red.
Si yfinance falla o rate-limitea, se usa un set de datos de muestra empaquetado
en `data/sample_data/` y se marca `is_sample=True` para que la UI avise.

IMPORTANTE: los datos de muestra son ILUSTRATIVOS, no cotizaciones reales en vivo.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import streamlit as st

    # max_entries acota la caché: evita que el historial de precios de muchas
    # combinaciones de tickers se acumule sin límite en instancias con poca RAM.
    _cache = st.cache_data(ttl=3600, show_spinner=False, max_entries=64)
except Exception:  # pragma: no cover - permite usar el módulo fuera de Streamlit
    def _cache(func):
        return func

SAMPLE_DIR = Path(__file__).parent / "sample_data"
_TICKER_RE = re.compile(r"[^A-Za-z0-9.\-]")
TRADING_DAYS_PER_YEAR = 252


# ── Validación / sanitización (Patrón 3) ─────────────────────────────────────
def sanitize_ticker(raw: str) -> str:
    """strip + uppercase + solo letras/dígitos/./-  (acepta BRK-B, BRK.B, etc)."""
    return _TICKER_RE.sub("", (raw or "").strip()).upper()


def validate_tickers(tickers: list[str]) -> tuple[list[str], list[str]]:
    """Verifica existencia rápida con yfinance fast_info (≤1s, costo casi nulo).

    Returns (válidos, inválidos). Si la red falla para TODOS (no podemos verificar),
    asumimos problema de conectividad y devolvemos todos como válidos → el fallback
    de muestra se encarga después.
    """
    valid: list[str] = []
    invalid: list[str] = []
    try:
        import yfinance as yf
    except Exception:
        return list(tickers), []  # sin yfinance, dejamos pasar al fallback

    for sym in tickers:
        try:
            fi = yf.Ticker(sym).fast_info
            price = None
            for key in ("last_price", "lastPrice", "previous_close", "previousClose"):
                try:
                    price = fi[key] if not hasattr(fi, key) else getattr(fi, key)
                except Exception:
                    price = None
                if price:
                    break
            (valid if price and price > 0 else invalid).append(sym)
        except Exception:
            invalid.append(sym)

    # Si nada validó, casi seguro es la red caída → no bloqueamos al usuario.
    if not valid and invalid:
        return list(tickers), []
    return valid, invalid


# ── Descarga de precios + fallback ───────────────────────────────────────────
def _download_prices_live(tickers: tuple[str, ...], window_years: int) -> pd.DataFrame:
    """Descarga precios de cierre de yfinance. Puede lanzar excepción si falla la red."""
    import yfinance as yf

    raw = yf.download(
        list(tickers),
        period=f"{window_years}y",
        auto_adjust=True,
        progress=False,
    )
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance devolvió datos vacíos")
    close = raw["Close"] if "Close" in raw else raw
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    # Reordenar columnas al orden pedido y limpiar
    cols = [t for t in tickers if t in close.columns]
    close = close[cols].dropna(how="all").ffill().dropna()
    if close.empty:
        raise RuntimeError("Series de precios vacía tras limpieza")
    return close


def _load_sample_prices(tickers: tuple[str, ...], window_years: int) -> pd.DataFrame:
    """Carga precios de muestra empaquetados. Para tickers sin archivo, sintetiza una
    serie determinística (semilla por ticker) claramente etiquetada como muestra."""
    series: dict[str, pd.Series] = {}
    for sym in tickers:
        f = SAMPLE_DIR / f"{sym}.csv"
        if f.exists():
            df = pd.read_csv(f, parse_dates=["Date"]).set_index("Date")
            series[sym] = df["Close"]
        else:
            series[sym] = _synthesize_series(sym, window_years)
    prices = pd.DataFrame(series).dropna(how="all").ffill().dropna()
    if window_years and not prices.empty:
        cutoff = prices.index.max() - pd.Timedelta(days=365 * window_years)
        prices = prices[prices.index >= cutoff]
    return prices


def _synthesize_series(sym: str, window_years: int) -> pd.Series:
    """Serie de precios SINTÉTICA (no real) para que la demo no se rompa con tickers
    sin datos de muestra. Parámetros plausibles por hash del ticker."""
    seed = abs(hash(sym)) % (2**32)
    rng = np.random.default_rng(seed)
    n = TRADING_DAYS_PER_YEAR * max(window_years, 1)
    mu = 0.0003 + (seed % 5) * 0.00005      # drift diario plausible
    sigma = 0.009 + (seed % 7) * 0.001       # vol diaria plausible
    rets = rng.normal(mu, sigma, n)
    prices = 100.0 * np.cumprod(1.0 + rets)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.Series(prices, index=idx, name=sym)


@_cache
def get_price_history(tickers: tuple[str, ...], window_years: int = 10) -> tuple[pd.DataFrame, bool]:
    """Devuelve (precios_close, is_sample). Cacheado 1h. Cae a muestra si yfinance falla."""
    try:
        return _download_prices_live(tickers, window_years), False
    except Exception:
        return _load_sample_prices(tickers, window_years), True


def get_returns_frame(tickers: list[str], window_years: int = 10) -> tuple["pd.DataFrame", bool]:
    """DataFrame de retornos diarios alineados + flag is_sample (para regresiones de beta)."""
    tkrs = tuple(sanitize_ticker(t) for t in tickers if sanitize_ticker(t))
    prices, is_sample = get_price_history(tkrs, window_years)
    return prices.pct_change().dropna(), is_sample


def get_market_stats(tickers: list[str], window_years: int = 10) -> dict:
    """μ (media diaria), Σ (covarianza diaria) y orden de tickers para el motor.

    Returns dict: {mean_daily, cov_daily, tickers, is_sample, n_days}.
    """
    tkrs = tuple(sanitize_ticker(t) for t in tickers if sanitize_ticker(t))
    prices, is_sample = get_price_history(tkrs, window_years)
    returns = prices.pct_change().dropna()
    return {
        "tickers": list(prices.columns),
        "mean_daily": returns.mean().to_numpy(),
        "cov_daily": returns.cov().to_numpy(),
        "is_sample": is_sample,
        "n_days": int(len(returns)),
    }
