"""Sequence-of-returns risk (Fase 3).

Demuestra que, con flujos de caja (aportes o retiros), el ORDEN de los retornos cambia
el resultado final aunque el conjunto de retornos sea idéntico:

- En ACUMULACIÓN (aportes +): tener los peores años primero termina MEJOR (comprás barato).
- En RETIRO (retiros −): tener los peores años primero termina PEOR (riesgo de secuencia).

Todo determinístico y local — costo $0.
"""
from __future__ import annotations

import numpy as np

TRADING_DAYS_PER_YEAR = 252


def portfolio_annual_moments(market_stats: dict, weights: list[float]) -> tuple[float, float]:
    """(media anual, desvío anual) del portafolio a partir de μ/Σ diarios."""
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    mean_daily = np.asarray(market_stats["mean_daily"], dtype=np.float64)
    cov_daily = np.asarray(market_stats["cov_daily"], dtype=np.float64)
    ann_mean = float(w @ mean_daily) * TRADING_DAYS_PER_YEAR
    ann_std = float(np.sqrt(max(w @ cov_daily @ w, 0.0))) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return ann_mean, ann_std


def sequence_demo(initial_capital: float, monthly_flow: float, horizon_years: int,
                  ann_mean: float, ann_std: float, random_seed: int | None = None) -> dict:
    """Genera un set fijo de retornos anuales y lo aplica en 3 órdenes distintos.

    `monthly_flow`: positivo = aporte, negativo = retiro.
    Returns: {"orderings": {nombre: {"path": [...], "terminal": float}}, "annual_flow": float,
              "mode": "acumulación"|"retiro"}.
    """
    rng = np.random.default_rng(random_seed)
    annual_returns = rng.normal(ann_mean, ann_std, horizon_years)
    annual_flow = monthly_flow * 12.0

    orderings = {
        "Peores años primero": np.sort(annual_returns),
        "Orden aleatorio": annual_returns.copy(),
        "Mejores años primero": np.sort(annual_returns)[::-1],
    }
    out: dict[str, dict] = {}
    for name, rets in orderings.items():
        cap = float(initial_capital)
        path = [cap]
        for r in rets:
            cap = max(cap * (1.0 + r) + annual_flow, 0.0)
            path.append(cap)
        out[name] = {"path": path, "terminal": cap}

    return {
        "orderings": out,
        "annual_flow": annual_flow,
        "mode": "retiro" if monthly_flow < 0 else "acumulación",
    }
