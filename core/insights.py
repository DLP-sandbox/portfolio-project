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

    # Retorno COMPUESTO (lo que de verdad capitaliza) vs el promedio aritmético.
    # g ≈ μ − σ²/2: el "peaje de la volatilidad". Mostrar solo μ sobreestima el resultado.
    cagr = ann_return - (ann_vol ** 2) / 2.0
    vol_drag = ann_return - cagr

    return {
        "n_assets": n, "ann_return": ann_return, "ann_vol": ann_vol,
        "cagr": cagr, "vol_drag": vol_drag,
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
    """Hallazgos en lenguaje natural, ordenados por importancia REAL del portafolio.

    La importancia se calcula según la severidad de cada métrica (no es fija), de modo que
    los 5 que se muestran son de verdad los que más le importan a ESTE portafolio: si está
    muy concentrado sube la concentración; si es muy volátil sube el peaje de volatilidad.
    Redacción pensada para principiantes/intermedios: primero qué pasa, luego qué significa
    para tu dinero y qué implica hacer.
    """
    f: list[dict] = []
    years = int(inputs["horizon_years"])
    n = structure["n_assets"]
    assets = structure["assets"]
    retirement = outcomes["retirement"]

    def imp(base: float, extra: float = 0.0) -> float:
        return max(35.0, min(100.0, base + extra))

    # ── 1) El peaje de la volatilidad: promedio ≠ lo que capitaliza ───────────
    cagr, drag, vol = structure["cagr"], structure["vol_drag"], structure["ann_vol"]
    if drag >= 0.02:
        sent = "alerta" if drag >= 0.06 else "neutral"
        f.append(_finding(
            "vol_drag", "Retorno real", sent, "El promedio engaña: lo que de verdad capitaliza",
            f"En el papel este portafolio promedia {_pct(structure['ann_return'])} al año, pero el "
            f"dinero no crece al promedio: crece a la tasa **compuesta**, que aquí es ~{_pct(cagr)}. "
            f"Esos {_pct(drag)} de diferencia son el peaje que cobra el vaivén (perder 50% exige "
            f"ganar 100% solo para volver al punto de partida). Cuanto más brusco el camino, más "
            f"grande el peaje: por eso dos portafolios con el mismo promedio pueden terminar muy "
            f"distintos.",
            value=cagr, importance=imp(46, 320 * drag)))
    else:
        f.append(_finding(
            "vol_drag", "Retorno real", "positivo", "Un camino parejo conserva el rendimiento",
            f"Este portafolio promedia {_pct(structure['ann_return'])} al año y, por ser poco "
            f"brusco, capitaliza a ~{_pct(cagr)}: casi no pierde nada por el vaivén. Esa "
            f"regularidad es justo lo que hace que el interés compuesto trabaje sin fricción.",
            value=cagr, importance=imp(44)))

    # ── 2) De dónde viene el riesgo (contribución al riesgo) ─────────────────
    if assets and n >= 2:
        top = assets[0]
        rc, wt = top["risk_contrib"], top["weight"]
        ratio = (rc / wt) if wt > 0 else 1.0
        if rc >= 0.40 or (ratio >= 1.5 and rc >= 0.25):
            if ratio >= 1.3:
                txt = (f"{top['symbol']} ocupa {_pct(wt)} de tu dinero pero explica {_pct(rc)} de "
                       f"tus altibajos. Es la diferencia entre *cuánto pesa en la cartera* y "
                       f"*cuánto manda en el resultado*: aunque parezca una posición más, tu "
                       f"tranquilidad depende casi toda de ella. Si ese activo tropieza, lo vas a "
                       f"sentir aunque el resto se comporte bien.")
            else:
                txt = (f"{top['symbol']} concentra {_pct(rc)} de todo el riesgo del portafolio "
                       f"(y {_pct(wt)} del dinero). En la práctica no tienes {n} apuestas: tienes "
                       f"una apuesta grande acompañada de otras que casi no mueven la aguja.")
            f.append(_finding("risk_source", "De dónde viene tu riesgo", "alerta",
                              "Una sola posición manda en tu riesgo", txt,
                              value=rc, importance=imp(58, 95 * (rc - 0.25))))
        elif rc >= 0.28:
            f.append(_finding(
                "risk_source", "De dónde viene tu riesgo", "neutral",
                "Un activo lleva la voz cantante",
                f"{top['symbol']} aporta {_pct(rc)} del riesgo frente al {_pct(wt)} que pesa. No "
                f"llega a dominar, pero es el que marca el ritmo: cuando se mueve, tu portafolio "
                f"se entera. Vale la pena vigilarlo con más atención que al resto.",
                value=rc, importance=imp(52, 40 * (rc - 0.28))))
        else:
            f.append(_finding(
                "risk_source", "De dónde viene tu riesgo", "positivo",
                "Tu riesgo está bien repartido",
                f"Ningún activo acapara el resultado: el que más aporta ({top['symbol']}) explica "
                f"solo {_pct(rc)} del riesgo. Repartir el riesgo —no solo el dinero— es lo que "
                f"evita que un tropiezo puntual arruine todo el plan.",
                value=rc, importance=imp(45)))

    # ── 3) Diversificación real (correlación + ratio de diversificación) ─────
    corr, dr, bets = structure["wavg_corr"], structure["diversification_ratio"], structure["eff_bets"]
    if n >= 2:
        if corr >= 0.7:
            f.append(_finding(
                "diversification", "Diversificación real", "alerta",
                "Tienes menos diversificación de la que parece",
                f"Tus {n} activos se mueven casi al unísono (correlación media {corr:.2f}): cuando "
                f"uno cae, los demás suelen acompañarlo. Por eso se comportan como ~{bets:.1f} "
                f"apuestas realmente distintas, no como {n}. Diversificar no es sumar nombres, es "
                f"sumar comportamientos: activos que reaccionen distinto al mismo escenario "
                f"(bonos, oro, otras regiones) harían más por ti que otra acción parecida.",
                value=corr, importance=imp(56, 90 * (corr - 0.55))))
        elif corr >= 0.4:
            f.append(_finding(
                "diversification", "Diversificación real", "neutral",
                "Diversificación a medias",
                f"Tus activos comparten bastante destino (correlación media {corr:.2f}): equivalen "
                f"a ~{bets:.1f} apuestas independientes de las {n} que tienes. Está lejos de ser "
                f"malo, pero todavía hay margen para suavizar el camino combinando cosas que no "
                f"suban y bajen a la vez.",
                value=corr, importance=imp(50, 30 * (corr - 0.4))))
        else:
            f.append(_finding(
                "diversification", "Diversificación real", "positivo",
                "Diversificación que sí funciona",
                f"Tus activos no se mueven todos juntos (correlación media {corr:.2f}), y eso se "
                f"nota: el conjunto es {dr:.2f} veces más estable que sus piezas por separado. "
                f"Esa es la única 'comida gratis' de las finanzas — menos sobresaltos sin resignar "
                f"rendimiento.",
                value=corr, importance=imp(46)))

    # ── 3b) Sobre-diversificación: diversificar de más diluye el rendimiento ──
    if n >= 12 and structure["max_weight"] < 0.08:
        f.append(_finding(
            "over_diversification", "Diversificación real", "neutral",
            "Puede que estés diversificando de más",
            f"Tienes {n} activos y ninguno pasa del {_pct(structure['max_weight'])}: el riesgo está "
            f"muy repartido, pero a partir de cierto punto añadir posiciones ya no reduce riesgo — "
            f"solo diluye tus mejores ideas y te acerca al comportamiento del índice, con mucho más "
            f"trabajo de seguimiento. Si vas a parecerte al mercado, un índice barato lo hace más "
            f"simple; si quieres superarlo, tus mejores convicciones necesitan peso suficiente.",
            value=float(n), importance=imp(58, 2.0 * (n - 12))))

    # ── 4) Concentración por peso ────────────────────────────────────────────
    mw, sym = structure["max_weight"], structure["max_weight_symbol"]
    if mw >= 0.35:
        f.append(_finding(
            "concentration", "Concentración", "alerta", "Demasiado peso en un solo nombre",
            f"{_pct(mw)} de tu patrimonio está en {sym}, y tus tres mayores posiciones suman "
            f"{_pct(structure['top3_weight'])}. Concentrar así es lo que dispara los grandes "
            f"aciertos… y también los grandes arrepentimientos. La pregunta útil no es si "
            f"{sym} te gusta, sino si podrías sostener el plan con calma si cayera a la mitad.",
            value=mw, importance=imp(54, 110 * (mw - 0.35))))
    elif mw >= 0.22:
        f.append(_finding(
            "concentration", "Concentración", "neutral", "Concentración vigilable",
            f"Tu mayor posición ({sym}) es {_pct(mw)} del portafolio y el top 3 suma "
            f"{_pct(structure['top3_weight'])}. Es un nivel manejable para quien conoce lo que "
            f"tiene; solo recuerda que ese activo tendrá voz fuerte en tu resultado.",
            value=mw, importance=imp(47, 30 * (mw - 0.22))))

    # ── 5) Probabilidad de terminar perdiendo ────────────────────────────────
    if outcomes["prob_loss"] is not None:
        pl = outcomes["prob_loss"]
        inv = _money(outcomes["invested"])
        if pl >= 0.30:
            f.append(_finding(
                "prob_loss", "Lo que puedes perder", "alerta", "Riesgo real de acabar en rojo",
                f"En {_pct(pl)} de los {int(len(result['final_values'])/1000)}.000 escenarios "
                f"terminas con menos de los {inv} que habrás puesto de tu bolsillo en {years} años. "
                f"Uno de cada tres finales en negativo es mucho pedirle a la paciencia de "
                f"cualquiera: o el horizonte es corto para este nivel de riesgo, o el riesgo es "
                f"alto para este horizonte.",
                value=pl, importance=imp(58, 120 * (pl - 0.30))))
        elif pl >= 0.10:
            f.append(_finding(
                "prob_loss", "Lo que puedes perder", "neutral", "Puedes terminar por debajo",
                f"En {_pct(pl)} de los escenarios acabas con menos de los {inv} aportados. Es el "
                f"peaje normal de invertir en activos con vaivén: la mayoría de las veces sales "
                f"ganando, pero no está garantizado, y por eso el dinero que necesitas pronto no "
                f"debería estar aquí.",
                value=pl, importance=imp(48, 45 * (pl - 0.10))))
        else:
            f.append(_finding(
                "prob_loss", "Lo que puedes perder", "positivo", "Muy pocas veces terminas perdiendo",
                f"Solo en {_pct(pl)} de los escenarios acabas por debajo de los {inv} aportados. "
                f"El tiempo hace su trabajo: con {years} años por delante, los tramos malos tienen "
                f"espacio de sobra para recuperarse.",
                value=pl, importance=imp(43)))

    # ── 6) Cómo se sentirá una caída (framing conductual) ────────────────────
    dd = result.get("max_drawdown_typical", 0.0)
    med = outcomes["median"]
    after = med * (1.0 - dd)
    f.append(_finding(
        "drawdown_dollars", "Prepárate para los baches", "alerta" if dd >= 0.35 else "neutral",
        "Cómo se va a sentir una mala racha",
        f"En un mal momento este portafolio suele ceder ~{_pct(dd)}. Traducido a tu caso: ver la "
        f"cuenta bajar de ~{_money(med)} a ~{_money(after)} y no tocar nada. Esa caída es temporal "
        f"en el papel, pero se vuelve pérdida definitiva en el momento en que vendes. Decidir hoy "
        f"cómo vas a reaccionar vale más que cualquier pronóstico.",
        value=dd, importance=imp(50, 85 * dd)))

    # ── 7) Poder adquisitivo (inflación) ─────────────────────────────────────
    keep = outcomes.get("prob_keep_power")
    extra = (f" Con todo, en {_pct(keep)} de los escenarios tu dinero crece por encima de la "
             f"inflación, que es la meta mínima real de invertir." if keep is not None else "")
    f.append(_finding(
        "real_value", "Poder adquisitivo", "neutral", "Qué comprarás de verdad con ese dinero",
        f"Tu mediana de {_money(med)} suena grande, pero dentro de {years} años los precios también "
        f"habrán subido: equivale a ~{_money(outcomes['median_real'])} de hoy (con {_pct(INFLATION)} "
        f"de inflación anual). Pensar en poder de compra —y no en el número nominal— es lo que evita "
        f"planes que parecen holgados y luego no alcanzan.{extra}",
        value=outcomes["median_real"], importance=imp(55, 40 * (1 - outcomes["median_real"] / max(med, 1)))))

    # ── 8) El peor 5% (CVaR) ─────────────────────────────────────────────────
    f.append(_finding(
        "cvar", "Lo que puedes perder", "neutral", "El tramo malo, con nombre y apellido",
        f"Si te toca el peor 5% de los futuros, terminarías en promedio con {_money(outcomes['cvar5'])}. "
        f"No es el fin del mundo ni una fatalidad: es el escenario para el que conviene estar "
        f"preparado mentalmente ANTES de invertir, porque es cuando se toman las peores decisiones.",
        value=outcomes["cvar5"], importance=imp(44)))

    # ── 9) Cuánto lo pone el mercado (interés compuesto) ─────────────────────
    if outcomes["market_share"] is not None and outcomes["market_gain"] is not None:
        ms = outcomes["market_share"]
        f.append(_finding(
            "market_vs_pocket", "Mercado vs tu bolsillo",
            "positivo" if ms >= 0.5 else "neutral", "Quién pone realmente el dinero",
            f"De los {_money(med)} de la mediana, {_money(outcomes['invested'])} salen de tu bolsillo "
            f"y ~{_money(outcomes['market_gain'])} los pondría el mercado: el {_pct(ms)} del resultado "
            f"sería rendimiento, no ahorro. Ese es el interés compuesto trabajando — y explica por qué "
            f"empezar temprano y no interrumpir pesa más que acertar el momento de entrada.",
            value=ms, importance=imp(46, 25 * ms)))

    # ── 10) ¿Compensa el riesgo? (vs ahorro seguro) ──────────────────────────
    if outcomes["prob_beat_savings"] is not None:
        pb = outcomes["prob_beat_savings"]
        if pb < 0.5:
            f.append(_finding(
                "vs_savings", "¿Vale el riesgo?", "alerta", "Mucho sobresalto para tan poca ventaja",
                f"Este portafolio le gana a un depósito seguro al {_pct(SAFE_RATE)} anual en apenas "
                f"{_pct(pb)} de los escenarios, y aun así te hace pasar por caídas de ~{_pct(dd)}. "
                f"Cuando el premio esperado no compensa el mal rato, casi siempre sobra riesgo mal "
                f"pagado: suele arreglarse diversificando, no apostando más fuerte.",
                value=pb, importance=imp(60, 70 * (0.5 - pb))))
        else:
            f.append(_finding(
                "vs_savings", "¿Vale el riesgo?", "positivo", "El riesgo está pagando",
                f"Este portafolio supera a un depósito seguro al {_pct(SAFE_RATE)} anual en {_pct(pb)} "
                f"de los escenarios. Ese margen es tu premio por tolerar el vaivén: probable, nunca "
                f"garantizado, y solo lo cobra quien se queda el tiempo suficiente.",
                value=pb, importance=imp(44, 20 * (pb - 0.5))))

    # ── 11) Eficiencia (Sharpe) leída en simple ──────────────────────────────
    sharpe = result.get("expected_sharpe", 0.0)
    if sharpe < 0.35:
        f.append(_finding(
            "sharpe", "Eficiencia", "alerta", "Estás pagando mucho riesgo por cada punto de retorno",
            f"Tu eficiencia (Sharpe {sharpe:.2f}) es baja: significa que el retorno que esperas no "
            f"luce tan bien una vez descontado lo que sufres para conseguirlo. Portafolios más "
            f"equilibrados suelen lograr un rendimiento parecido con bastante menos sobresalto.",
            value=sharpe, importance=imp(52, 60 * (0.35 - sharpe))))
    elif sharpe >= 0.7:
        f.append(_finding(
            "sharpe", "Eficiencia", "positivo", "Buen retorno por cada unidad de riesgo",
            f"Tu eficiencia (Sharpe {sharpe:.2f}) es sólida: el rendimiento esperado compensa bien "
            f"el vaivén que asumes. Es la señal de una mezcla trabajada, no de una apuesta con suerte.",
            value=sharpe, importance=imp(43)))

    if retirement:   # en modo retiro, la ruina manda sobre todo lo demás
        ruin = result.get("probability_of_ruin", 0.0)
        f.append(_finding(
            "ruin", "Modo retiro", "alerta" if ruin >= 0.10 else "neutral",
            "¿Te alcanza el dinero?",
            f"Retirando {_money(abs(inputs.get('monthly_contribution', 0.0)))} al mes, el capital se "
            f"agota antes de los {years} años en {_pct(ruin)} de los escenarios. En retiro el orden "
            f"de los años importa tanto como el promedio: unos primeros años malos mientras sacas "
            f"dinero hacen un daño que después es muy difícil de revertir.",
            value=ruin, importance=imp(70, 120 * ruin)))

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
