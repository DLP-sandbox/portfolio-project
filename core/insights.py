"""Motor de análisis de portafolio → hallazgos en lenguaje natural (100% por reglas).

Sin API de IA, sin red, sin Streamlit: numpy puro y determinista (costo $0). A partir de
lo que la app YA calcula (μ/Σ diarios, pesos y los valores finales de la simulación) extrae
métricas de alto valor para un inversionista principiante/intermedio y las traduce a
hallazgos claros, rankeados por importancia. Nunca recomienda comprar/vender: solo describe.

Diseño de memoria: todas las métricas salen de matrices n×n (n = nº de activos ≤ ~20) y del
array `final_values` (n_sim,) que la app ya retiene. NO usa la matriz `paths` (se libera tras
simular), así que no añade presión de memoria.
"""
from __future__ import annotations

import math

import numpy as np

TRADING_DAYS_PER_YEAR = 252
INFLATION = 0.03      # supuesto de inflación anual para el valor "en dinero de hoy"
SAFE_RATE = 0.04      # rendimiento de una alternativa "segura" (ahorro/plazo fijo) anual


# ── Formateadores en español ─────────────────────────────────────────────────
def _money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.0f}"


def _pct(x: float | None, decimals: int = 0) -> str:
    return "—" if x is None else f"{x * 100:.{decimals}f}%"


# ── Alineación de pesos con el orden de μ/Σ ──────────────────────────────────
def _aligned_weights(stats_tickers: list[str], tickers: list[str], weights) -> np.ndarray:
    """Pesos alineados al orden de `stats_tickers` (por símbolo), normalizados a 1.

    Robustez: si algún activo pedido no tiene datos (no está en μ/Σ) o el orden difiere,
    igual queda consistente con la matriz de covarianza.
    """
    wmap: dict[str, float] = {}
    for t, w in zip(tickers, weights):
        wmap[t] = wmap.get(t, 0.0) + float(w)
    w = np.array([wmap.get(t, 0.0) for t in stats_tickers], dtype=np.float64)
    s = w.sum()
    if s <= 0:
        n = max(len(stats_tickers), 1)
        return np.full(len(stats_tickers), 1.0 / n)
    return w / s


# ── Estructura del portafolio (de Σ, μ, w) ───────────────────────────────────
def portfolio_structure(market_stats: dict, tickers: list[str], weights) -> dict:
    """Riesgo por activo, diversificación, concentración y momentos anualizados."""
    st_tk = list(market_stats["tickers"])
    mu = np.asarray(market_stats["mean_daily"], dtype=np.float64)
    cov = np.asarray(market_stats["cov_daily"], dtype=np.float64)
    w = _aligned_weights(st_tk, tickers, weights)
    n = len(st_tk)

    port_var_d = max(float(w @ cov @ w), 0.0)
    ann_vol = math.sqrt(port_var_d) * math.sqrt(TRADING_DAYS_PER_YEAR)
    ann_return = float(w @ mu) * TRADING_DAYS_PER_YEAR

    var_i = np.clip(np.diag(cov), 0.0, None)
    sd_i = np.sqrt(var_i)
    vol_i_ann = sd_i * math.sqrt(TRADING_DAYS_PER_YEAR)
    ret_i_ann = mu * TRADING_DAYS_PER_YEAR

    # Contribución al riesgo (varianza): RC_i = w_i·(Σw)_i / (wᵀΣw), suma 1
    if port_var_d > 0:
        rc = w * (cov @ w) / port_var_d
    else:
        rc = w.copy()

    # Correlación media (ponderada por pesos) + ratio de diversificación
    denom = np.outer(sd_i, sd_i)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.where(denom > 0, cov / denom, 0.0)
    if n >= 2:
        iu = np.triu_indices(n, k=1)
        wpair = np.outer(w, w)[iu]
        wsum = float(wpair.sum())
        wavg_corr = float((corr[iu] * wpair).sum() / wsum) if wsum > 0 else float(np.mean(corr[iu]))
        avg_corr = float(np.mean(corr[iu]))
    else:
        wavg_corr = avg_corr = 1.0
    weighted_avg_vol = float(w @ vol_i_ann)
    div_ratio = weighted_avg_vol / ann_vol if ann_vol > 0 else 1.0
    # Nº de "apuestas independientes" (fórmula equicorrelación): n/(1+(n-1)·ρ)
    rho = max(wavg_corr, 0.0)
    eff_bets = n / (1.0 + (n - 1) * rho) if n >= 1 and (1.0 + (n - 1) * rho) > 0 else float(n)

    # Concentración
    hhi = float(np.sum(w ** 2))
    eff_holdings = 1.0 / hhi if hhi > 0 else float(n)
    order = np.argsort(-w)
    max_w = float(w[order[0]]) if n else 0.0
    max_w_sym = st_tk[order[0]] if n else ""
    top3_w = float(np.sum(w[order[:3]]))

    assets = [{
        "symbol": st_tk[i], "weight": float(w[i]), "risk_contrib": float(rc[i]),
        "vol_annual": float(vol_i_ann[i]), "ret_annual": float(ret_i_ann[i]),
    } for i in range(n)]
    assets.sort(key=lambda a: -a["risk_contrib"])

    return {
        "n_assets": n, "ann_return": ann_return, "ann_vol": ann_vol,
        "assets": assets, "avg_corr": avg_corr, "wavg_corr": wavg_corr,
        "diversification_ratio": div_ratio, "eff_bets": eff_bets,
        "hhi": hhi, "effective_holdings": eff_holdings,
        "max_weight": max_w, "max_weight_symbol": max_w_sym, "top3_weight": top3_w,
    }


# ── Métricas de la distribución de resultados (de final_values) ──────────────
def _savings_future_value(cap: float, monthly: float, years: int, annual_rate: float) -> float:
    """Valor futuro de una alternativa 'segura': capital + aportes mensuales a tasa fija."""
    months = years * 12
    rm = (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0
    fv_cap = cap * (1.0 + annual_rate) ** years
    fv_contrib = monthly * (((1.0 + rm) ** months - 1.0) / rm) if rm > 0 else monthly * months
    return fv_cap + fv_contrib


def outcome_metrics(final_values, inputs: dict) -> dict:
    """Pérdida probable, peor 5%, mercado-vs-bolsillo, valor real y vs alternativas."""
    fv = np.asarray(final_values, dtype=np.float64)
    years = int(inputs["horizon_years"])
    cap = float(inputs["initial_capital"])
    flow = float(inputs.get("monthly_contribution", 0.0))
    retirement = flow < 0

    invested = cap + max(flow, 0.0) * 12.0 * years
    median = float(np.median(fv))
    p5 = float(np.percentile(fv, 5))
    tail = fv[fv <= p5]
    cvar5 = float(np.mean(tail)) if tail.size else p5

    real_factor = (1.0 + INFLATION) ** years
    median_real = median / real_factor

    prob_loss = float(np.mean(fv < invested)) if (invested > 0 and not retirement) else None
    market_gain = (median - invested) if not retirement else None
    market_share = (market_gain / median) if (market_gain is not None and median > 0) else None

    if not retirement:
        savings_fv = _savings_future_value(cap, max(flow, 0.0), years, SAFE_RATE)
        prob_beat_savings = float(np.mean(fv > savings_fv))
        prob_keep_power = float(np.mean(fv > invested * real_factor)) if invested > 0 else None
    else:
        savings_fv = prob_beat_savings = prob_keep_power = None

    return {
        "invested": invested, "median": median, "median_real": median_real,
        "p5": p5, "cvar5": cvar5, "prob_loss": prob_loss,
        "market_gain": market_gain, "market_share": market_share,
        "savings_fv": savings_fv, "prob_beat_savings": prob_beat_savings,
        "prob_keep_power": prob_keep_power, "retirement": retirement,
        "inflation": INFLATION, "safe_rate": SAFE_RATE,
    }


# ── Generación de hallazgos (rankeados por importancia) ──────────────────────
def _finding(key, category, sentiment, title, text, value=None, importance=50.0) -> dict:
    return {"key": key, "category": category, "sentiment": sentiment,
            "title": title, "text": text, "value": value, "importance": importance}


def build_findings(structure: dict, outcomes: dict, result: dict, inputs: dict) -> list[dict]:
    """Lista de hallazgos en lenguaje natural, ordenada de más a menos importante."""
    f: list[dict] = []
    years = int(inputs["horizon_years"])
    n = structure["n_assets"]
    assets = structure["assets"]

    # 1) Retorno y vaivén esperados
    f.append(_finding(
        "retorno_vol", "Retorno esperado", "neutral", "Retorno y vaivén esperados",
        f"Este portafolio apunta a un rendimiento de ~{_pct(structure['ann_return'])} al año "
        f"en promedio, con vaivenes típicos de ±{_pct(structure['ann_vol'])} anual. Más "
        f"rendimiento casi siempre viene con más vaivén: son dos caras de la misma moneda.",
        value=structure["ann_return"], importance=50.0))

    # 2) De dónde viene el riesgo (flagship). El titular es la cuota ABSOLUTA de riesgo
    #    del activo que más aporta; la desproporción riesgo/peso refuerza el mensaje.
    if assets and n >= 2:
        top = assets[0]
        rc, wt = top["risk_contrib"], top["weight"]
        ratio = (rc / wt) if wt > 0 else 1.0
        if rc >= 0.40 or (ratio >= 1.5 and rc >= 0.25):
            if ratio >= 1.3:
                text = (f"{top['symbol']} es el {_pct(wt)} de tu dinero pero genera el {_pct(rc)} "
                        f"de tu riesgo: pesa en tus altibajos mucho más de lo que su tamaño sugiere. "
                        f"Si tropieza, lo sientes casi todo.")
            else:
                text = (f"{top['symbol']} genera el {_pct(rc)} de TODO el riesgo del portafolio "
                        f"(y es el {_pct(wt)} de tu dinero): tus altibajos dependen sobre todo de "
                        f"este activo, no del conjunto.")
            f.append(_finding("risk_source", "De dónde viene tu riesgo", "alerta",
                              "Una posición domina tu riesgo", text,
                              value=rc, importance=100.0))
        elif rc >= 0.28:
            f.append(_finding(
                "risk_source", "De dónde viene tu riesgo", "neutral",
                "Un activo lidera tu riesgo",
                f"El que más aporta ({top['symbol']}) genera el {_pct(rc)} del riesgo, frente al "
                f"{_pct(wt)} que pesa. Está algo cargado hacia ese activo, pero sin dominar del todo.",
                value=rc, importance=64.0))
        else:
            f.append(_finding(
                "risk_source", "De dónde viene tu riesgo", "positivo",
                "Tu riesgo está repartido",
                f"Ningún activo acapara el riesgo: el que más aporta ({top['symbol']}) genera solo el "
                f"{_pct(rc)}. Un riesgo repartido hace el camino menos brusco.",
                value=rc, importance=58.0))

    # 3) Diversificación real (correlación)
    corr = structure["wavg_corr"]
    if n >= 2:
        if corr >= 0.7:
            f.append(_finding(
                "diversification", "Diversificación real", "alerta",
                "Diversificas menos de lo que parece",
                f"Tus activos se mueven muy juntos (correlación media {corr:.2f}): cuando uno cae, "
                f"casi todos caen a la vez. Tus {n} activos se comportan como ~{structure['eff_bets']:.1f} "
                f"apuestas realmente independientes. Tener muchos nombres no es lo mismo que diversificar.",
                value=corr, importance=95.0))
        elif corr >= 0.4:
            f.append(_finding(
                "diversification", "Diversificación real", "neutral",
                "Diversificación intermedia",
                f"Tus activos se mueven bastante juntos (correlación media {corr:.2f}) — equivale a "
                f"~{structure['eff_bets']:.1f} apuestas independientes. Hay margen para diversificar más "
                f"combinando activos que no suban y bajen al mismo tiempo.",
                value=corr, importance=68.0))
        else:
            f.append(_finding(
                "diversification", "Diversificación real", "positivo",
                "Buena diversificación real",
                f"Tus activos no se mueven todos juntos (correlación media {corr:.2f}), lo que suaviza "
                f"los golpes: se comportan como ~{structure['eff_bets']:.1f} apuestas independientes.",
                value=corr, importance=58.0))

    # 4) Concentración por peso
    mw, sym = structure["max_weight"], structure["max_weight_symbol"]
    if mw >= 0.35:
        f.append(_finding(
            "concentration", "Concentración", "alerta", "Muy concentrado en un activo",
            f"El {_pct(mw)} de tu portafolio está en un solo activo ({sym}). Una mala racha de ese "
            f"activo te pega fuerte; repartir un poco reduce ese golpe sin renunciar a crecer.",
            value=mw, importance=90.0))
    elif mw >= 0.22:
        f.append(_finding(
            "concentration", "Concentración", "neutral", "Concentración moderada",
            f"Tu mayor posición ({sym}) es el {_pct(mw)} del portafolio y tus 3 mayores suman "
            f"{_pct(structure['top3_weight'])}. Es manejable, pero conviene tenerlo presente.",
            value=mw, importance=60.0))

    # 5) Probabilidad de pérdida (acumulación)
    if outcomes["prob_loss"] is not None:
        pl = outcomes["prob_loss"]
        if pl >= 0.30:
            sent, imp = "alerta", 85.0
        elif pl >= 0.10:
            sent, imp = "neutral", 66.0
        else:
            sent, imp = "positivo", 54.0
        f.append(_finding(
            "prob_loss", "Lo que puedes perder", sent, "Probabilidad de terminar en pérdida",
            f"En {_pct(pl)} de los escenarios terminas con menos de lo que aportaste "
            f"({_money(outcomes['invested'])} de tu bolsillo a lo largo de {years} años). "
            f"Es el precio de la incertidumbre: aguantar sin vender en los malos años es clave.",
            value=pl, importance=imp))

    # 6) Peor 5% (CVaR)
    f.append(_finding(
        "cvar", "Lo que puedes perder", "neutral", "El peor 5% de los casos",
        f"En el peor 5% de los escenarios terminas, en promedio, con {_money(outcomes['cvar5'])}. "
        f"Ese es el tramo malo para el que conviene estar preparado mentalmente antes de invertir.",
        value=outcomes["cvar5"], importance=57.0))

    # 7) Poder adquisitivo (inflación) — cambio de perspectiva
    f.append(_finding(
        "real_value", "Poder adquisitivo", "neutral", "Cuánto vale en dinero de hoy",
        f"Ojo con la inflación: tu mediana de {_money(outcomes['median'])} equivale a solo "
        f"~{_money(outcomes['median_real'])} en poder de compra de hoy (a {_pct(INFLATION)}/año "
        f"durante {years} años). El número grande engaña — lo que importa es qué podrás comprar.",
        value=outcomes["median_real"], importance=80.0))

    # 8) Caída típica en dólares — framing conductual
    dd = result.get("max_drawdown_typical", 0.0)
    after = outcomes["median"] * (1.0 - dd)
    f.append(_finding(
        "drawdown_dollars", "Prepárate para los baches", "neutral",
        "Cómo se sentirá una caída",
        f"En un mal momento este portafolio suele caer ~{_pct(dd)}: verías tu inversión bajar de "
        f"~{_money(outcomes['median'])} a ~{_money(after)}. Vender ahí convierte una caída temporal "
        f"en una pérdida real — el plan es aguantarla.",
        value=dd, importance=78.0))

    # 9) Mercado vs tu bolsillo
    if outcomes["market_share"] is not None and outcomes["market_gain"] is not None:
        f.append(_finding(
            "market_vs_pocket", "Mercado vs tu bolsillo",
            "positivo" if outcomes["market_share"] >= 0.5 else "neutral",
            "Cuánto lo pone el mercado",
            f"De los {_money(outcomes['median'])} de la mediana, ~{_money(outcomes['market_gain'])} "
            f"los generaría el mercado y {_money(outcomes['invested'])} salen de tu bolsillo: el "
            f"{_pct(outcomes['market_share'])} del resultado sería rendimiento, no aporte. Eso es el "
            f"interés compuesto trabajando por ti.",
            value=outcomes["market_share"], importance=61.0))

    # 10) ¿Vale el riesgo? (vs ahorro seguro)
    if outcomes["prob_beat_savings"] is not None:
        pb = outcomes["prob_beat_savings"]
        if pb < 0.5:
            f.append(_finding(
                "vs_savings", "¿Vale el riesgo?", "alerta", "Poca ventaja sobre un ahorro seguro",
                f"Este portafolio supera a un ahorro seguro al {_pct(SAFE_RATE)} anual en solo "
                f"{_pct(pb)} de los escenarios. Es mucho vaivén para tan poca ventaja: quizá el riesgo "
                f"no está compensando lo suficiente.",
                value=pb, importance=76.0))
        else:
            f.append(_finding(
                "vs_savings", "¿Vale el riesgo?", "positivo", "Compensa frente a un ahorro seguro",
                f"Este portafolio supera a un ahorro seguro al {_pct(SAFE_RATE)} anual en {_pct(pb)} "
                f"de los escenarios. Ese es el premio (probable, no seguro) por aceptar el vaivén.",
                value=pb, importance=59.0))

    f.sort(key=lambda x: -x["importance"])
    return f


def analyze(market_stats: dict, tickers: list[str], weights, result: dict, inputs: dict) -> dict:
    """Orquestador: estructura + distribución + hallazgos rankeados.

    `result` es el dict que devuelve `run_montecarlo` (tiene `final_values` y
    `max_drawdown_typical`). Devuelve un dict liviano (solo escalares y filas por activo).
    """
    structure = portfolio_structure(market_stats, tickers, weights)
    outcomes = outcome_metrics(result["final_values"], inputs)
    findings = build_findings(structure, outcomes, result, inputs)
    return {"structure": structure, "outcomes": outcomes, "findings": findings}
