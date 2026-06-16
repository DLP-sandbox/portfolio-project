"""Portafolios predefinidos (presets).

STUB de Fase 2: las estructuras están definidas pero todavía NO se cablean en la UI.
En Fase 2 se exponen como selector ("S&P puro", "60/40", "All-Weather") y se usan para
la comparación de escenarios overlapping.
"""
from __future__ import annotations

# Cada preset: nombre legible → tickers + pesos (en %, suman 100).
PRESETS: dict[str, dict] = {
    "sp500": {
        "label": "S&P 500 puro",
        "tickers": ["SPY"],
        "weights": [100.0],
        "description": "100% renta variable EE.UU. (índice S&P 500).",
    },
    "classic_60_40": {
        "label": "Clásica 60/40",
        "tickers": ["SPY", "BND"],
        "weights": [60.0, 40.0],
        "description": "60% acciones + 40% bonos. El balance tradicional.",
    },
    "all_weather": {
        "label": "All-Weather (Ray Dalio)",
        "tickers": ["SPY", "TLT", "IEF", "GLD", "DBC"],
        "weights": [30.0, 40.0, 15.0, 7.5, 7.5],
        "description": "Portafolio resiliente a distintos regímenes económicos.",
    },
}


def get_preset(key: str) -> dict | None:
    return PRESETS.get(key)


def list_presets() -> list[tuple[str, str]]:
    """[(key, label), ...] para poblar un selector."""
    return [(k, v["label"]) for k, v in PRESETS.items()]
