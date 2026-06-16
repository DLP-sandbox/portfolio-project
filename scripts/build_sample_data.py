"""Construye/actualiza el set de datos de muestra (`data/sample_data/*.csv`).

Intenta un snapshot REAL de yfinance. Si la red falla, genera series sintéticas
claramente etiquetadas como muestra (la app las usa solo como fallback, con aviso).

Uso:
    python scripts/build_sample_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DIR = ROOT / "data" / "sample_data"
# Incluye los tickers de los presets (all-weather: TLT, IEF, GLD, DBC) para que el
# fallback de muestra cubra las carteras predefinidas de Fase 2.
TICKERS = ["SPY", "AAPL", "NVDA", "BRK-B", "BND", "TLT", "IEF", "GLD", "DBC"]
WINDOW_YEARS = 12
TRADING_DAYS_PER_YEAR = 252


def _synthesize(sym: str) -> pd.Series:
    seed = abs(hash(sym)) % (2**32)
    rng = np.random.default_rng(seed)
    n = TRADING_DAYS_PER_YEAR * WINDOW_YEARS
    mu = 0.0003 + (seed % 5) * 0.00005
    sigma = 0.009 + (seed % 7) * 0.001
    rets = rng.normal(mu, sigma, n)
    prices = 100.0 * np.cumprod(1.0 + rets)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.Series(prices, index=idx, name=sym)


def _save(sym: str, close: pd.Series, source: str) -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    df = close.rename("Close").to_frame()
    df.index.name = "Date"
    df.to_csv(SAMPLE_DIR / f"{sym}.csv")
    print(f"  ✓ {sym}: {len(df)} filas ({source})")


def main() -> int:
    print(f"Construyendo datos de muestra en {SAMPLE_DIR} …")
    try:
        import yfinance as yf

        raw = yf.download(TICKERS, period=f"{WINDOW_YEARS}y", auto_adjust=True, progress=False)
        close = raw["Close"] if "Close" in raw else raw
        if close is None or len(close) == 0:
            raise RuntimeError("yfinance vacío")
        for sym in TICKERS:
            if sym in close.columns and close[sym].notna().sum() > 100:
                _save(sym, close[sym].dropna(), "yfinance real")
            else:
                _save(sym, _synthesize(sym), "SINTÉTICO (yfinance no devolvió este ticker)")
        print("Listo (snapshot real donde fue posible).")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"  yfinance no disponible ({e}). Generando series SINTÉTICAS de muestra…")
        for sym in TICKERS:
            _save(sym, _synthesize(sym), "SINTÉTICO")
        print("Listo (datos sintéticos de muestra — no son cotizaciones reales).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
