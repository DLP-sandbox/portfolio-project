"""Stress test con eventos históricos reales (Fase 3).

Estima cómo impactaría a TU portafolio un evento tipo 1929/1973/2000/2008/2020, escalando
la caída histórica del S&P 500 por la sensibilidad (beta) de tu portafolio al mercado.

IMPORTANTE: es una ESTIMACIÓN de magnitud basada en la beta histórica, no una predicción.
Las magnitudes de cada evento son cifras documentadas de caída pico-a-valle del S&P 500
(o equivalente para 1929). El comportamiento real puede diferir.
"""
from __future__ import annotations

import numpy as np

# Caída pico-a-valle del S&P 500 (equivalente para 1929) y recuperación aproximada.
HISTORICAL_EVENTS = [
    {"key": "1929", "name": "Crack de 1929", "equity_drawdown": 0.86, "recovery_months": 300,
     "desc": "Gran Depresión: el índice tardó ~25 años en recuperar el pico previo."},
    {"key": "1973", "name": "Bear 1973-74", "equity_drawdown": 0.48, "recovery_months": 90,
     "desc": "Crisis del petróleo y estanflación."},
    {"key": "2000", "name": "Burbuja .com", "equity_drawdown": 0.49, "recovery_months": 86,
     "desc": "Estallido de las puntocom (2000-2002)."},
    {"key": "2008", "name": "Crisis financiera 2008", "equity_drawdown": 0.57, "recovery_months": 49,
     "desc": "Gran Recesión / colapso subprime (2007-2009)."},
    {"key": "2020", "name": "Crash COVID 2020", "equity_drawdown": 0.34, "recovery_months": 5,
     "desc": "Caída relámpago por la pandemia; recuperación inusualmente rápida."},
]


def estimate_equity_beta(returns_frame, tickers: list[str], weights: list[float],
                         benchmark: str = "SPY") -> float:
    """Beta del portafolio respecto al benchmark, por regresión de retornos diarios.

    `returns_frame` debe incluir el benchmark y (idealmente) los tickers del portafolio.
    """
    if benchmark not in returns_frame.columns:
        return 1.0
    present = [(t, w) for t, w in zip(tickers, weights) if t in returns_frame.columns]
    if not present:
        return 1.0
    tks, ws = zip(*present)
    ws = np.asarray(ws, dtype=np.float64)
    ws = ws / ws.sum()
    port = returns_frame[list(tks)].to_numpy() @ ws
    spy = returns_frame[benchmark].to_numpy()
    var = float(np.var(spy))
    if var <= 0:
        return 1.0
    beta = float(np.cov(port, spy)[0, 1] / var)
    return max(beta, 0.0)


def compute_stress(tickers: list[str], weights: list[float], reference_value: float,
                   window_years: int = 10) -> dict:
    """Aplica cada evento histórico a `reference_value` (p.ej. la mediana proyectada).

    Returns dict: {beta, is_sample, events:[{name, equity_drawdown, portfolio_drawdown,
    value_after, loss, recovery_months, desc}]}.
    """
    from data.market_data import get_returns_frame

    bench = "SPY"
    rf, is_sample = get_returns_frame(list(dict.fromkeys(list(tickers) + [bench])), window_years)
    beta = estimate_equity_beta(rf, tickers, weights, bench)

    events = []
    for ev in HISTORICAL_EVENTS:
        port_dd = min(beta * ev["equity_drawdown"], 0.95)
        value_after = reference_value * (1.0 - port_dd)
        events.append({
            "name": ev["name"],
            "equity_drawdown": ev["equity_drawdown"],
            "portfolio_drawdown": port_dd,
            "value_after": value_after,
            "loss": reference_value - value_after,
            "recovery_months": ev["recovery_months"],
            "desc": ev["desc"],
        })
    return {"beta": beta, "is_sample": is_sample, "reference_value": reference_value,
            "events": events}
