"""Métricas estadísticas sobre los paths de la simulación. Numpy puro y vectorizado."""
from __future__ import annotations

import numpy as np

# Niveles de percentil estándar para el fan chart
PERCENTILE_LEVELS = (5, 25, 50, 75, 95)


def percentiles_by_month(paths: np.ndarray, levels: tuple[int, ...] = PERCENTILE_LEVELS) -> dict:
    """Percentiles del patrimonio en cada mes → dict {"P5": array(n_months+1), ...}."""
    values = np.percentile(paths, levels, axis=0)  # (len(levels), n_months+1)
    return {f"P{lvl}": values[i] for i, lvl in enumerate(levels)}


def prob_target(final_values: np.ndarray, target: float | None) -> float | None:
    """Fracción de simulaciones (0-1) cuyo valor final alcanza o supera la meta."""
    if target is None:
        return None
    return float(np.mean(final_values >= target))


def max_drawdown_typical(paths: np.ndarray) -> float:
    """Mediana del máximo drawdown por path (caída pico-a-valle típica)."""
    running_max = np.maximum.accumulate(paths, axis=1)
    # Evitar división por cero (running_max > 0 siempre con capital inicial > 0)
    safe_max = np.where(running_max > 0, running_max, np.nan)
    drawdowns = (running_max - paths) / safe_max
    max_dd_per_path = np.nanmax(drawdowns, axis=1)
    return float(np.median(max_dd_per_path))


def probability_of_ruin(paths: np.ndarray) -> float:
    """Fracción de paths que en algún momento tocan patrimonio ≤ 0.

    Con aportes positivos suele ser ~0; cobra sentido en modo retiro (Fase 3).
    """
    return float(np.mean(np.any(paths <= 0, axis=1)))


def expected_sharpe(mean_monthly: np.ndarray, cov_monthly: np.ndarray,
                    weights: np.ndarray, risk_free_annual: float = 0.0) -> float:
    """Sharpe esperado anualizado del portafolio (a partir de μ/Σ mensuales)."""
    port_mean_m = float(weights @ mean_monthly)
    port_var_m = float(weights @ cov_monthly @ weights)
    if port_var_m <= 0:
        return 0.0
    ann_mean = port_mean_m * 12.0
    ann_std = (port_var_m ** 0.5) * (12.0 ** 0.5)
    return (ann_mean - risk_free_annual) / ann_std


def percentiles_at_years(percentiles: dict, years: list[int]) -> dict:
    """Percentiles del patrimonio en años concretos → {year: {"P5": v, ...}}.

    `percentiles`: salida de percentiles_by_month (arrays indexados por mes).
    """
    any_band = next(iter(percentiles.values()))
    last_idx = len(any_band) - 1
    out: dict[int, dict] = {}
    for y in years:
        idx = min(y * 12, last_idx)
        out[y] = {k: float(v[idx]) for k, v in percentiles.items()}
    return out
