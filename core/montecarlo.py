"""Motor Montecarlo vectorizado.

Proyecta el patrimonio futuro de un portafolio corriendo N simulaciones de retornos
mensuales correlacionados (Cholesky), partiendo de media/covarianza de retornos
históricos. Es una PROYECCIÓN PROBABILÍSTICA, no una predicción: los retornos futuros
pueden diferir significativamente de los del pasado.

Diseño:
- `simulate_paths(...)` es matemática pura (numpy puro, sin Streamlit ni red) → testeable.
- `run_montecarlo(...)` es el orquestador con la firma del spec: obtiene μ/Σ desde la
  capa de datos (cacheada, con fallback) y arma el dict de resultados.
"""
from __future__ import annotations

import numpy as np

from core import statistics as st_metrics

TRADING_DAYS_PER_MONTH = 21  # aproximación estándar para mensualizar retornos diarios


def _safe_cholesky(cov: np.ndarray) -> np.ndarray:
    """Cholesky robusto: si Σ no es definida positiva (activos casi colineales o
    ventana corta), clipea autovalores a un mínimo positivo y reconstruye."""
    try:
        return np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        eigvals, eigvecs = np.linalg.eigh(cov)
        eigvals = np.clip(eigvals, 1e-12, None)
        cov_psd = (eigvecs * eigvals) @ eigvecs.T
        return np.linalg.cholesky(cov_psd)


def simulate_paths(
    mean_monthly: np.ndarray,
    cov_monthly: np.ndarray,
    weights: np.ndarray,
    initial_capital: float,
    monthly_contribution: float,
    n_months: int,
    n_simulations: int = 10_000,
    distribution: str = "normal",
    annual_fees_pct: float = 0.0,
    annual_tax_on_gains_pct: float = 0.0,
    absorb_at_zero: bool = False,
    random_seed: int | None = None,
) -> np.ndarray:
    """Genera la matriz de paths del patrimonio. Numpy puro, sin dependencias externas.

    Returns: array (n_simulations, n_months + 1). La columna 0 es el capital inicial.

    Modelo de impuestos (Fase 2): aproximación de cuenta gravable. Cada 12 meses se grava
    la GANANCIA neta de inversión del año (valor fin de año − valor inicio de año − aportes
    del año) solo si es positiva; las pérdidas no generan crédito.

    `absorb_at_zero` (Fase 3, modo retiro): una vez que el capital toca 0, queda absorbido
    en 0 (no se puede retirar de lo que no hay) → la ruina es permanente.
    `monthly_contribution` negativo modela retiros.
    """
    rng = np.random.default_rng(random_seed)
    n_assets = mean_monthly.shape[0]
    L = _safe_cholesky(cov_monthly)

    paths = np.empty((n_simulations, n_months + 1), dtype=np.float64)
    paths[:, 0] = initial_capital
    capital = np.full(n_simulations, float(initial_capital))

    fee_factor = 1.0 - (annual_fees_pct / 12.0 / 100.0)  # fees prorrateados al mes
    tax_rate = annual_tax_on_gains_pct / 100.0
    year_start = capital.copy()   # patrimonio al inicio del año fiscal en curso
    contrib_in_year = 0.0         # aportes acumulados en el año (no son ganancia gravable)
    use_t = distribution == "t-student"
    df = 4  # grados de libertad para fat tails

    for m in range(1, n_months + 1):
        z = rng.standard_normal((n_simulations, n_assets))
        if use_t:
            # Multivariate-t: escala los normales por chi-cuadrado y reescala para
            # preservar la covarianza objetivo (Var[t_df] = df/(df-2)).
            chi2 = rng.chisquare(df, size=(n_simulations, 1))
            z = z * np.sqrt(df / chi2) * np.sqrt((df - 2) / df)
        # Retornos correlacionados de cada activo y retorno del portafolio (rebal. mensual)
        asset_returns = mean_monthly + z @ L.T
        port_return = asset_returns @ weights
        # Cap físico: un portafolio long-only no puede perder >100% en un mes
        np.clip(port_return, -0.95, None, out=port_return)

        capital = capital * (1.0 + port_return) + monthly_contribution
        capital *= fee_factor
        contrib_in_year += monthly_contribution

        # Impuesto anual sobre la ganancia neta del año
        if tax_rate > 0 and m % 12 == 0:
            gain = capital - year_start - contrib_in_year
            capital = capital - np.where(gain > 0, gain * tax_rate, 0.0)
            year_start = capital.copy()
            contrib_in_year = 0.0

        # Modo retiro: ruina absorbente en 0
        if absorb_at_zero:
            np.maximum(capital, 0.0, out=capital)

        paths[:, m] = capital

    return paths


def run_montecarlo(
    initial_capital: float,
    monthly_contribution: float,
    horizon_years: int,
    tickers: list[str],
    weights: list[float],
    n_simulations: int = 10_000,
    distribution: str = "normal",            # "normal" o "t-student"
    rebalance_frequency_months: int = 12,    # reservado para Fase 2 (sleeve tracking)
    annual_fees_pct: float = 0.0,
    annual_tax_on_gains_pct: float = 0.0,     # reservado para Fase 2
    historical_window_years: int = 10,
    target: float | None = None,
    absorb_at_zero: bool = False,
    random_seed: int | None = None,
    market_stats: dict | None = None,
) -> dict:
    """Corre la proyección Montecarlo completa.

    Returns dict con:
    - final_values: array (n_sim,) de valores finales
    - percentiles: dict P5/P25/P50/P75/P95 → array por mes
    - prob_target: float 0-1 (None si no se pasó target)
    - max_drawdown_typical: float (mediana del max drawdown por path)
    - probability_of_ruin: float (fracción de paths que tocan ≤0)
    - is_sample: bool (True si se usaron datos de muestra por fallo de yfinance)
    - months: int

    `market_stats` se puede inyectar (μ/Σ ya calculados) para tests o para reusar caché;
    si es None, se obtiene de la capa de datos (cacheada, con fallback).
    """
    weights_arr = np.asarray(weights, dtype=np.float64)
    weights_arr = weights_arr / weights_arr.sum()  # normalizar por seguridad
    n_months = int(horizon_years) * 12

    if market_stats is None:
        # Import perezoso: mantiene la matemática de este módulo desacoplada de Streamlit.
        from data.market_data import get_market_stats

        market_stats = get_market_stats(tickers, historical_window_years)

    mean_daily = np.asarray(market_stats["mean_daily"], dtype=np.float64)
    cov_daily = np.asarray(market_stats["cov_daily"], dtype=np.float64)
    is_sample = bool(market_stats.get("is_sample", False))

    # Mensualizar: media escala lineal, covarianza también (retornos i.i.d.)
    mean_monthly = mean_daily * TRADING_DAYS_PER_MONTH
    cov_monthly = cov_daily * TRADING_DAYS_PER_MONTH

    paths = simulate_paths(
        mean_monthly=mean_monthly,
        cov_monthly=cov_monthly,
        weights=weights_arr,
        initial_capital=initial_capital,
        monthly_contribution=monthly_contribution,
        n_months=n_months,
        n_simulations=n_simulations,
        distribution=distribution,
        annual_fees_pct=annual_fees_pct,
        annual_tax_on_gains_pct=annual_tax_on_gains_pct,
        absorb_at_zero=absorb_at_zero or monthly_contribution < 0,
        random_seed=random_seed,
    )

    # Derivar todas las métricas ANTES de soltar la matriz grande de paths.
    final_values = paths[:, -1].copy()
    percentiles = st_metrics.percentiles_by_month(paths)
    max_drawdown = st_metrics.max_drawdown_typical(paths)
    prob_ruin = st_metrics.probability_of_ruin(paths)
    expected_sharpe = st_metrics.expected_sharpe(mean_monthly, cov_monthly, weights_arr)
    # `paths` (n_sim × meses, hasta ~40 MB) ya no se necesita: nada aguas abajo la
    # usa, solo estas métricas. La liberamos aquí para NO retenerla en session_state
    # (evita acumular varias matrices y quedarnos sin memoria en instancias chicas).
    del paths

    return {
        "final_values": final_values,
        "percentiles": percentiles,
        "prob_target": st_metrics.prob_target(final_values, target),
        "max_drawdown_typical": max_drawdown,
        "probability_of_ruin": prob_ruin,
        "expected_sharpe": expected_sharpe,
        "is_sample": is_sample,
        "months": n_months,
    }


def build_summary(result: dict, inputs: dict) -> dict:
    """Resumen liviano para persistir/cachear (sin las 10.000 paths completas).

    Guarda solo las bandas de percentiles por mes + percentiles del valor final +
    escalares. Es lo que va a `.history/` o Supabase.
    """
    fv = result["final_values"]
    pcts = result["percentiles"]
    return {
        "inputs": inputs,
        "months": result["months"],
        "bands": {k: np.asarray(v).tolist() for k, v in pcts.items()},
        "final_p5": float(np.percentile(fv, 5)),
        "final_p50": float(np.percentile(fv, 50)),
        "final_p95": float(np.percentile(fv, 95)),
        "final_mean": float(np.mean(fv)),
        "prob_target": result["prob_target"],
        "max_drawdown_typical": result["max_drawdown_typical"],
        "probability_of_ruin": result["probability_of_ruin"],
        "is_sample": result["is_sample"],
    }
