"""Construye el directorio de tickers de NYSE + NASDAQ para el autocompletado.

Descarga los archivos públicos de NASDAQ Trader (símbolo + nombre + exchange) y arma un
CSV compacto en `data/ticker_directory.csv`. Si la red falla, no pasa nada: la app usa una
lista curada de respaldo (ver data/tickers.py).

Uso:
    python scripts/build_ticker_directory.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "ticker_directory.csv"
NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
EXCHANGE_MAP = {"N": "NYSE", "A": "NYSE American", "P": "NYSE Arca"}  # familia NYSE


def _fetch(url: str) -> list[str]:
    import requests

    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.text.splitlines()


def main() -> int:
    rows = []
    try:
        # NASDAQ: Symbol|Security Name|Market Category|Test Issue|...|ETF|...
        for line in _fetch(NASDAQ_URL)[1:]:
            p = line.split("|")
            if len(p) < 7 or p[0] == "" or line.startswith("File Creation"):
                continue
            if p[3] == "Y":  # test issue
                continue
            rows.append((p[0].strip(), p[1].strip(), "NASDAQ", "Y" if p[6] == "Y" else "N"))

        # OTHER: ACT Symbol|Security Name|Exchange|CQS|ETF|RoundLot|Test Issue|NASDAQ Symbol
        for line in _fetch(OTHER_URL)[1:]:
            p = line.split("|")
            if len(p) < 7 or p[0] == "" or line.startswith("File Creation"):
                continue
            if p[6] == "Y" or p[2] not in EXCHANGE_MAP:
                continue
            rows.append((p[0].strip(), p[1].strip(), EXCHANGE_MAP[p[2]], "Y" if p[4] == "Y" else "N"))
    except Exception as e:  # noqa: BLE001
        print(f"No se pudo descargar el directorio ({e}). La app usará la lista curada.")
        return 0

    df = pd.DataFrame(rows, columns=["symbol", "name", "exchange", "is_etf"])
    # yfinance usa '-' para clases (BRK-B); estos archivos usan '.'/' '
    df["symbol"] = df["symbol"].str.replace(".", "-", regex=False).str.replace(" ", "-", regex=False)
    df = df[~df["symbol"].str.contains(r"[$^]", regex=True)]
    df = df.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"✓ {len(df):,} tickers (NYSE+NASDAQ) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
