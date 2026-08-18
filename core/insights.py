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


def _archetype(structure: dict, ctx: dict | None) -> dict:
    """Perfil de la cartera, con reglas. Aporta `idea` (qué es de verdad) y `rol` (para qué
    sirve), dos fragmentos que se reinyectan en distintos puntos de la prosa.

    Es el mecanismo que impide que dos carteras distintas suenen igual aunque caigan en la
    misma rama numérica (mismo enfoque que `_caracter_cesta()` en DLP Analyzer).
    """
    n = structure["n_assets"]
    mw = structure["max_weight"]
    corr = structure["wavg_corr"] or 0.0
    bets = structure["eff_bets"] or 1.0
    bonos = 0.0
    if ctx and ctx.get("exposure"):
        for row in (ctx["exposure"].get("by_class") or []):
            if row["name"] in ("Bonos",):
                bonos += float(row["pct"])
    vol = structure["ann_vol"] or 0.0

    if bonos >= 25:
        return {"clave": "defensivo",
                "idea": "una cartera con colchón: parte del dinero está en renta fija, que se "
                        "mueve menos y suele sostener el conjunto cuando la bolsa cae",
                "rol": "amortigua los malos años a cambio de quedarse algo atrás en los buenos"}
    if mw >= 0.45 or n <= 2:
        return {"clave": "concentrado",
                "idea": "una apuesta de convicción: pocas posiciones y una que manda con "
                        "claridad sobre el resultado",
                "rol": "puede dar alegrías grandes, pero exige aguantar sustos del mismo tamaño"}
    if n >= 10 and mw < 0.15 and corr < 0.6:
        return {"clave": "nucleo",
                "idea": "una cartera de núcleo: muchas piezas, ninguna decisiva, pensada para "
                        "acompañar al mercado sin depender de acertar con un nombre",
                "rol": "el tipo de cartera que se alimenta con aportes periódicos y se revisa "
                       "una vez al año, no cada semana"}
    if vol >= 0.28:
        return {"clave": "agresivo",
                "idea": "una cartera de crecimiento: busca rendimiento alto y acepta un camino "
                        "notablemente movido para conseguirlo",
                "rol": "rinde cuando el crecimiento se confirma y corrige fuerte cuando decepciona"}
    if bets >= 3.5:
        return {"clave": "equilibrado",
                "idea": "una mezcla trabajada: varias piezas que no se mueven todas a la vez",
                "rol": "busca crecer sin sobresaltos innecesarios, que es lo que permite "
                       "sostener el plan muchos años"}
    return {"clave": "mixto",
            "idea": "una cartera mixta: ni tan repartida como un índice ni tan concentrada "
                    "como una apuesta puntual",
            "rol": "funciona si sabes por qué está cada pieza dentro"}


def _portfolio_context(tickers: list[str], weights) -> dict:
    """Sector, clase y divisa del portafolio. Cada pieza en SU propio try/except.

    Importa: estas consultas tocan la red. Antes, un fallo aquí dentro habría dejado
    `analysis = None` y habrían desaparecido TODOS los hallazgos. Así, como mucho falta el
    hallazgo que dependía del dato.
    """
    ctx: dict = {"exposure": None, "currencies": None}
    try:
        from data import sectors as _sect
        items = [{"symbol": t, "weight": float(w)} for t, w in zip(tickers, weights)]
        ctx["exposure"] = _sect.portfolio_exposure(items)
    except Exception:
        pass
    try:
        from data import market_data as _md
        ctx["currencies"] = _md.currencies_of(tickers)
    except Exception:
        pass
    return ctx


def build_findings(structure: dict, outcomes: dict, result: dict, inputs: dict,
                   ctx: dict | None = None) -> list[dict]:
    """Hallazgos en lenguaje natural, ordenados por importancia REAL del portafolio.

    Dos cosas gobiernan el texto:

    * **La importancia** se calcula según la severidad de cada métrica (no es fija), así que
      los 5 que se muestran son los que de verdad le importan a ESTE portafolio.
    * **La redacción** se arma con variantes deterministas (`textgen.variant`) y un índice
      distinto por hueco: el mismo portafolio dice siempre lo mismo, pero dos portafolios
      distintos no se parecen. Estructura de cada hallazgo, como en DLP Analyzer:
      *qué vemos → qué significa para tu dinero → qué implica*.
    """
    from core import textgen as tg

    f: list[dict] = []
    years = int(inputs["horizon_years"])
    n = structure["n_assets"]
    assets = structure["assets"]
    retirement = outcomes["retirement"]
    arq = _archetype(structure, ctx)

    _key = tg.seed_key(inputs)
    _sn = sum(ord(c) for c in _key)

    def V(idx: int, *ops: str) -> str:
        """Variante determinista para el hueco `idx`."""
        return tg.variant(_key, idx, *ops)

    def A(idx: int, txt: str) -> str:
        """Aproximación en palabras («alrededor de un 25%») en vez del símbolo `~`."""
        return tg.approx(_sn + idx, txt)

    def add(key, category, sentiment, title, partes, value=None, importance=50.0):
        texto = tg.es_natural(" ".join(x for x in partes if x))
        f.append(_finding(key, category, sentiment, title, texto, value, importance))

    def imp(base: float, extra: float = 0.0) -> float:
        return max(35.0, min(100.0, base + extra))

    # ── 0) Qué tipo de cartera es esta ───────────────────────────────────────
    add("archetype", "Tu cartera", "neutral",
        V(1, "Qué tipo de cartera has armado", "El carácter de esta cartera",
          "Con qué estás jugando de verdad"),
        [V(2, f"Antes de mirar ninguna cifra conviene saber qué es esto: {arq['idea']}.",
            f"Lo primero que define el resultado no es un número, es el diseño: {arq['idea']}.",
            f"Vista en conjunto, es {arq['idea']}."),
         V(3, f"En una cartera, su papel es claro: {arq['rol']}.",
            f"Dicho en corto: {arq['rol']}.",
            f"Eso marca para qué sirve: {arq['rol']}."),
         V(4, "Todo lo que sigue se entiende mejor con eso en la cabeza.",
            "Las cifras de abajo son consecuencia de esa decisión de diseño.",
            "Si ese papel no es el que buscabas, lo que hay que cambiar es la mezcla, no el plazo.")],
        importance=imp(57))

    # ── 1) El peaje de la volatilidad: promedio ≠ lo que capitaliza ───────────
    cagr, drag, vol = structure["cagr"], structure["vol_drag"], structure["ann_vol"]
    if drag >= 0.02:
        sent = "alerta" if drag >= 0.06 else "neutral"
        add("vol_drag", "Retorno real", sent,
            V(11, "El promedio no es lo que capitaliza", "Por qué el promedio engaña",
              "La media dice una cosa, tu dinero otra"),
            [V(12, f"En el papel este portafolio promedia {_pct(structure['ann_return'])} al año, "
                   f"pero el dinero no crece al promedio: crece a la tasa compuesta, que aquí "
                   f"queda {A(12, _pct(cagr))}.",
               f"La media anual sale en {_pct(structure['ann_return'])}, aunque lo que de verdad "
               f"acumula tu dinero es {A(13, _pct(cagr))}: no son la misma cifra.",
               f"Este portafolio rinde {_pct(structure['ann_return'])} de media, y sin embargo "
               f"capitaliza {A(14, _pct(cagr))}."),
             V(13, f"Esa diferencia de {_pct(drag)} es el peaje que cobra el vaivén: perder la "
                   f"mitad obliga a ganar el doble solo para volver al punto de partida.",
               f"Los {_pct(drag)} que faltan se los lleva la irregularidad del camino, no las "
               f"comisiones ni los impuestos.",
               f"Entre una cifra y otra hay {_pct(drag)} de peaje, y lo cobra lo brusco del "
               f"recorrido: cuanto más bandazo, más caro."),
             V(14, "Por eso dos portafolios con la misma media pueden acabar muy separados: los "
                   "distingue lo movido que fue el trayecto.",
               "Es la razón de que suavizar el camino valga tanto como perseguir más rendimiento.",
               "Conviene mirar siempre la tasa compuesta antes que la media: es la que paga.")],
            value=drag, importance=imp(46, 320 * drag))
    else:
        add("vol_drag", "Retorno real", "positivo",
            V(15, "Un camino parejo conserva el retorno", "La regularidad te está pagando",
              "Poco vaivén, poco peaje"),
            [V(16, f"Este portafolio promedia {_pct(structure['ann_return'])} al año y, por ser "
                   f"poco brusco, capitaliza {A(16, _pct(cagr))}: casi no pierde nada por el camino.",
               f"Entre su media ({_pct(structure['ann_return'])}) y lo que realmente acumula "
               f"({A(17, _pct(cagr))}) apenas hay distancia, y eso es señal de un trayecto tranquilo.",
               f"Promedia {_pct(structure['ann_return'])} y convierte casi todo en crecimiento "
               f"efectivo, {A(18, _pct(cagr))}."),
             V(17, "Esa regularidad es justo lo que deja trabajar al interés compuesto sin fricción.",
               "Cuando el camino es parejo, el rendimiento llega entero al final.",
               "Es una ventaja discreta pero real: se nota en el resultado, no en el titular.")],
            value=drag, importance=imp(44))

    # ── 2) De dónde viene el riesgo de verdad ────────────────────────────────
    if assets and n >= 2:
        top = assets[0]
        rc, wt = top["risk_contrib"], top["weight"]
        ratio = rc / wt if wt > 0 else 1.0
        sym = top["symbol"]
        if rc >= 0.40 or (ratio >= 1.5 and rc >= 0.25):
            if ratio >= 1.3:
                cuerpo = [
                    V(21, f"{sym} ocupa {_pct(wt)} de tu dinero pero explica {_pct(rc)} de tus "
                          f"altibajos.",
                      f"Aunque {sym} solo pesa {_pct(wt)} del capital, de él sale {_pct(rc)} del "
                      f"movimiento de la cartera.",
                      f"Hay una diferencia grande entre lo que {sym} ocupa ({_pct(wt)}) y lo que "
                      f"decide ({_pct(rc)} del riesgo)."),
                    V(22, "Una cosa es cuánto pesa en la cartera y otra cuánto manda en el "
                          "resultado: tu tranquilidad depende casi toda de esa posición.",
                      "Es la distancia entre ocupar sitio y llevar el timón, y aquí lo lleva ella.",
                      "Parece una posición más, pero en la práctica es la que fija el ánimo de "
                      "toda la cartera."),
                    V(23, f"Si {sym} tropieza lo vas a sentir aunque el resto se porte bien.",
                      f"Un mal año de {sym} arrastra el conjunto por mucho que acompañen los demás.",
                      f"Conviene decidir ahora si estás cómodo con que {sym} tenga esa voz.")]
            else:
                cuerpo = [
                    V(24, f"{sym} concentra {_pct(rc)} de todo el riesgo del portafolio, y "
                          f"{_pct(wt)} del dinero.",
                      f"De cada movimiento de la cartera, {_pct(rc)} viene de {sym} (que pesa "
                      f"{_pct(wt)} del capital).",
                      f"{sym} se lleva {_pct(rc)} del riesgo total y {_pct(wt)} del dinero."),
                    V(25, f"En la práctica no tienes {n} apuestas: tienes una apuesta grande "
                          f"acompañada de otras que casi no mueven la aguja.",
                      f"Contar {n} posiciones da sensación de reparto, pero el resultado lo firma una.",
                      ("La otra posición aporta mucho menos de lo que su presencia sugiere."
                       if n - 1 == 1 else
                       f"Las otras {n - 1} posiciones aportan mucho menos de lo que su número "
                       f"sugiere.")),
                    V(26, "No es un error en sí mismo; solo conviene saberlo antes y no durante "
                          "una caída.",
                      "Es una decisión legítima, siempre que sea deliberada.",
                      "Lo importante es que sea una elección tuya y no un descuido del reparto.")]
            add("risk_source", "De dónde viene tu riesgo", "alerta",
                V(27, "Una sola posición manda en tu riesgo", "El riesgo lo decide un solo nombre",
                  "Tu resultado depende de una pieza"),
                cuerpo, value=rc, importance=imp(58, 95 * (rc - 0.25)))
        elif rc >= 0.28:
            add("risk_source", "De dónde viene tu riesgo", "neutral",
                V(28, "Un activo lleva la voz cantante", "Hay una pieza que marca el ritmo",
                  "Un nombre pesa más de lo que parece"),
                [V(29, f"{sym} aporta {_pct(rc)} del riesgo frente al {_pct(wt)} que pesa en dinero.",
                   f"{sym} pone {_pct(rc)} del movimiento con {_pct(wt)} del capital.",
                   f"Con {_pct(wt)} del dinero, {sym} explica {_pct(rc)} de los altibajos."),
                 V(30, "No llega a dominar, pero es el que marca el ritmo: cuando se mueve, la "
                       "cartera se entera.",
                   "Sin ser decisivo, es la pieza que más se nota en el día a día.",
                   "Está lejos de mandar en solitario, aunque sí lleva la iniciativa."),
                 V(31, "Vale la pena vigilarlo con algo más de atención que al resto.",
                   "Merece más seguimiento que las demás posiciones.",
                   "Es el nombre al que conviene mirar primero cuando algo se mueva.")],
                value=rc, importance=imp(52, 40 * (rc - 0.28)))
        else:
            add("risk_source", "De dónde viene tu riesgo", "positivo",
                V(32, "Tu riesgo está bien repartido", "Ninguna pieza decide sola",
                  "El riesgo no depende de un nombre"),
                [V(33, f"Ningún activo acapara el resultado: el que más aporta ({sym}) explica solo "
                       f"{_pct(rc)} del riesgo.",
                   f"El mayor contribuyente al riesgo ({sym}) se queda en {_pct(rc)}, que es poco "
                   f"para llevar la batuta.",
                   f"Ni siquiera {sym}, la pieza más influyente, pasa de {_pct(rc)} del riesgo."),
                 V(34, "Repartir el riesgo — y no solo el dinero — es lo que evita que un tropiezo "
                       "puntual arruine el plan.",
                   "Repartir dinero es fácil; repartir riesgo, que es lo que importa, es lo difícil "
                   "y aquí está conseguido.",
                   "Es la diferencia entre parecer diversificado y serlo."),
                 V(35, "Esa estructura es la que permite aguantar un mal año sin replantearse todo.",
                   "Con este reparto, ningún susto individual obliga a tomar decisiones apresuradas.",
                   "Es el tipo de diseño que se sostiene solo con el tiempo.")],
                value=rc, importance=imp(45))

    # ── 3) Diversificación real (correlación) ────────────────────────────────
    corr = structure["wavg_corr"]
    bets = structure["eff_bets"]
    if n >= 2 and corr is not None:
        if corr >= 0.7:
            add("diversification", "Diversificación real", "alerta",
                V(41, "Menos diversificación de la que parece", "Tus activos van todos a una",
                  "Repartido en el papel, no en la práctica"),
                [V(42, f"Tus {n} activos se mueven casi al unísono (su correlación media es "
                       f"{corr:.2f}): cuando uno cae, los demás suelen acompañarlo.",
                   f"Las piezas de esta cartera comparten destino casi por completo, con una "
                   f"correlación media de {corr:.2f}.",
                   f"Con una correlación media de {corr:.2f}, tus {n} activos reaccionan igual "
                   f"al mismo escenario."),
                 V(43, f"Por eso se comportan como {A(43, f'{bets:.1f}')} apuestas realmente "
                       f"distintas, y no como {n}.",
                   f"El resultado es que la cartera rinde como si tuviera {A(44, f'{bets:.1f}')} "
                   f"posiciones independientes en vez de {n}.",
                   f"En la práctica estás jugando {A(45, f'{bets:.1f}')} cartas distintas, no {n}."),
                 V(44, "Diversificar no es sumar nombres, es sumar comportamientos: algo que "
                       "reaccione distinto (bonos, oro, otras regiones) haría más por ti que otra "
                       "acción parecida.",
                   "La solución no pasa por añadir más de lo mismo, sino por meter algo que no "
                   "suba y baje a la vez que el resto.",
                   "Un activo que se comporte al revés vale aquí más que cinco que se comporten "
                   "igual.")],
                value=corr, importance=imp(56, 90 * (corr - 0.55)))
        elif corr >= 0.4:
            add("diversification", "Diversificación real", "neutral",
                V(45, "Diversificación a medias", "Repartido, aunque no del todo",
                  "Hay reparto, pero queda margen"),
                [V(46, f"Tus activos comparten bastante destino: la correlación media es {corr:.2f}.",
                   f"Con una correlación media de {corr:.2f}, las piezas se mueven juntas más de "
                   f"lo que convendría.",
                   f"La correlación media entre tus posiciones queda en {corr:.2f}."),
                 V(47, f"Eso equivale a {A(47, f'{bets:.1f}')} apuestas independientes de las {n} "
                       f"que tienes sobre la mesa.",
                   f"Traducido: rinden como {A(48, f'{bets:.1f}')} decisiones distintas, no como {n}.",
                   f"De tus {n} posiciones, el efecto real es el de {A(49, f'{bets:.1f}')}."),
                 V(48, "Está lejos de ser malo, pero todavía hay margen para suavizar el camino "
                       "combinando cosas que no suban y bajen a la vez.",
                   "No es un problema, es una oportunidad: queda sitio para algo que se comporte "
                   "distinto.",
                   "Con una pieza de otro carácter, el mismo rendimiento se conseguiría con menos "
                   "sobresaltos.")],
                value=corr, importance=imp(50, 30 * (corr - 0.4)))
        else:
            dr = structure["diversification_ratio"]
            add("diversification", "Diversificación real", "positivo",
                V(49, "Diversificación que sí funciona", "Aquí el reparto está trabajando",
                  "Piezas que no se mueven a la vez"),
                [V(50, f"Tus activos no se mueven todos juntos (correlación media {corr:.2f}), y "
                       f"eso se nota en el conjunto.",
                   f"La correlación media es de solo {corr:.2f}: cada pieza va bastante a lo suyo.",
                   f"Con {corr:.2f} de correlación media, la cartera no depende de un único "
                   f"escenario."),
                 V(51, f"El resultado es que el conjunto es {dr:.2f} veces más estable que sus "
                       f"piezas por separado.",
                   f"Sumadas, se comportan {dr:.2f} veces mejor que cada una por su cuenta.",
                   f"Esa descoordinación vale {dr:.2f} veces menos vaivén del que tendrían sueltas."),
                 V(52, "Es la única ventaja gratuita que ofrecen las finanzas: menos sobresaltos "
                       "sin resignar rendimiento.",
                   "Es lo más parecido a un regalo que hay en invertir, y aquí está cobrado.",
                   "Menos ruido por el mismo camino: eso es exactamente lo que se busca.")],
                value=corr, importance=imp(46))

    # ── 3b) Diversificación de más ───────────────────────────────────────────
    mw = structure["max_weight"]
    if n >= 12 and mw < 0.08:
        add("over_diversification", "Diversificación real", "neutral",
            V(55, "Puede que estés diversificando de más", "Tantas piezas empiezan a estorbar",
              "Repartir tanto también tiene coste"),
            [V(56, f"Tienes {n} activos y ninguno pasa del {_pct(mw)}: el riesgo está muy repartido.",
               f"Con {n} posiciones y ninguna por encima del {_pct(mw)}, el reparto es casi total.",
               f"Ninguna de tus {n} posiciones llega al {_pct(mw)} del capital."),
             V(57, "A partir de cierto punto, añadir nombres ya no reduce riesgo: solo diluye tus "
                   "mejores ideas y te acerca al comportamiento del índice, con mucho más "
                   "seguimiento encima.",
               "Pasado un umbral, cada activo nuevo aporta menos protección que trabajo, y empuja "
               "el resultado hacia la media del mercado.",
               "Más allá de una decena larga de posiciones, lo que se gana en calma se pierde en "
               "convicción."),
             V(58, "Si vas a parecerte al mercado, un índice barato lo hace más simple; si quieres "
                   "superarlo, tus mejores ideas necesitan peso suficiente.",
               "Conviene elegir: o simplificar con un índice, o dar tamaño a lo que de verdad "
               "convence.",
               "Un puñado de decisiones bien pensadas suele rendir más que una lista larga.")],
            value=n, importance=imp(58, 2 * (n - 12)))

    # ── 4) Concentración por peso ────────────────────────────────────────────
    sym_mw = structure["max_weight_symbol"]
    top3 = structure["top3_weight"]
    # Con 3 activos o menos, "las tres mayores suman 100%" es una obviedad: se calla.
    _t3 = f" y tus tres mayores posiciones suman {_pct(top3)}" if n >= 4 else ""
    _t3b = f"; entre las tres primeras juntan {_pct(top3)}" if n >= 4 else ""
    if mw >= 0.35:
        add("concentration", "Concentración", "alerta",
            V(61, "Demasiado peso en un solo nombre", "Una posición se lleva casi todo",
              "El tamaño de esa apuesta es grande"),
            [V(62, f"{_pct(mw)} de tu patrimonio está en {sym_mw}{_t3}.",
               f"{sym_mw} se lleva {_pct(mw)} del capital{_t3b}.",
               f"Con {_pct(mw)} en {sym_mw}, la cartera está muy escorada hacia un solo nombre."),
             V(63, "Concentrar así es lo que dispara los grandes aciertos, y también los grandes "
                   "arrepentimientos.",
               "Ese tamaño amplifica las dos direcciones por igual, no solo la buena.",
               "Es la decisión que más separa los resultados extremos, para bien y para mal."),
             V(64, f"La pregunta útil no es si {sym_mw} te gusta, sino si sostendrías el plan con "
                   f"calma viéndolo caer a la mitad.",
               f"Merece la pena imaginar {sym_mw} cayendo un 50% y comprobar si el plan aguanta.",
               f"Antes que acertar con {sym_mw}, importa poder convivir con un mal año suyo.")],
            value=mw, importance=imp(54, 110 * (mw - 0.35)))
    elif mw >= 0.22:
        add("concentration", "Concentración", "neutral",
            V(65, "Concentración vigilable", "Hay una posición con voz fuerte",
              "Reparto aceptable, con un nombre destacado"),
            [V(66, f"Tu mayor posición ({sym_mw}) es {_pct(mw)} del portafolio{_t3}.",
               f"{sym_mw} ocupa {_pct(mw)} del capital{_t3b}.",
               f"El primer nombre de la cartera pesa {_pct(mw)}."),
             V(67, "Es un nivel manejable para quien conoce lo que tiene.",
               "Nada preocupante si la elección es consciente.",
               "Está dentro de lo razonable para una cartera con criterio."),
             V(68, f"Solo conviene recordar que {sym_mw} tendrá voz fuerte en tu resultado final.",
               f"Eso sí: {sym_mw} pesará en el desenlace más que ninguna otra pieza.",
               f"Con ese tamaño, {sym_mw} deja de ser una posición más.")],
            value=mw, importance=imp(47, 30 * (mw - 0.22)))

    # ── 5) Probabilidad de terminar por debajo de lo aportado ────────────────
    pl = outcomes["prob_loss"]
    inv = _money(outcomes["invested"])
    if pl is not None:
        n_esc = int(len(result["final_values"]) / 1000)
        if pl >= 0.30:
            add("prob_loss", "Lo que puedes perder", "alerta",
                V(71, "Riesgo real de acabar en rojo", "Perder es un final probable aquí",
                  "Uno de cada tres finales, en negativo"),
                [V(72, f"En {_pct(pl)} de los {n_esc}.000 escenarios terminas con menos de los "
                       f"{inv} que habrás puesto de tu bolsillo en {years} años.",
                   f"De {n_esc}.000 futuros simulados, en {_pct(pl)} acabas por debajo de los {inv} "
                   f"aportados.",
                   f"{_pct(pl)} de los caminos posibles terminan por debajo de los {inv} que habrás "
                   f"ido poniendo."),
                 V(73, "Esa proporción de finales en negativo es mucho pedirle a la paciencia de "
                       "cualquiera.",
                   "Convivir con esa posibilidad durante años es más duro de lo que parece sobre "
                   "el papel.",
                   "Es el tipo de cifra que se lleva bien hasta que toca vivirla."),
                 V(74, "O el horizonte es corto para este nivel de riesgo, o el riesgo es alto "
                       "para este horizonte.",
                   "Se arregla dando más tiempo al plan o bajando el nivel de riesgo: las dos "
                   "palancas funcionan.",
                   "Merece la pena revisar la mezcla antes que confiar en que el tiempo lo cure "
                   "todo.")],
                value=pl, importance=imp(58, 120 * (pl - 0.30)))
        elif pl >= 0.10:
            add("prob_loss", "Lo que puedes perder", "neutral",
                V(75, "Puedes terminar por debajo", "Acabar en negativo es posible",
                  "No todos los finales salen bien"),
                [V(76, f"En {_pct(pl)} de los escenarios acabas con menos de los {inv} aportados.",
                   f"Uno de cada varios futuros ({_pct(pl)}) termina por debajo de los {inv} que pones.",
                   f"{_pct(pl)} de los caminos simulados no llegan a recuperar los {inv} aportados."),
                 V(77, "Es el peaje normal de invertir en activos con vaivén: la mayoría de las "
                       "veces sales ganando, pero no está garantizado.",
                   "Forma parte del trato: la probabilidad juega a favor, la certeza no existe.",
                   "Ningún activo con rendimiento serio ofrece la alternativa de cero sustos."),
                 V(78, "Por eso el dinero que vas a necesitar pronto no debería estar aquí.",
                   "Conviene que aquí solo esté el dinero que puedes dejar quieto todo el plazo.",
                   "El colchón de corto plazo se guarda en otro sitio, no en esta cartera.")],
                value=pl, importance=imp(48, 45 * (pl - 0.10)))
        else:
            add("prob_loss", "Lo que puedes perder", "positivo",
                V(79, "Muy pocas veces terminas perdiendo", "Casi todos los finales salen bien",
                  "El tiempo juega claramente a favor"),
                [V(80, f"Solo en {_pct(pl)} de los escenarios acabas por debajo de los {inv} aportados.",
                   f"Apenas {_pct(pl)} de los futuros simulados terminan sin recuperar los {inv} puestos.",
                   f"Perder respecto a los {inv} aportados ocurre en solo {_pct(pl)} de los caminos."),
                 V(81, f"El tiempo hace su trabajo: con {years} años por delante, los tramos malos "
                       f"tienen espacio de sobra para recuperarse.",
                   f"Con {years} años de plazo, casi cualquier mala racha cabe dentro y se corrige.",
                   f"Un horizonte de {years} años absorbe los tropiezos que a corto plazo asustan."),
                 V(82, "Es la ventaja silenciosa de invertir a largo: no exige acertar, exige quedarse.",
                   "No hace falta acertar el momento; basta con no interrumpir el plan.",
                   "La constancia, aquí, vale más que la puntería.")],
                value=pl, importance=imp(43))

    # ── 6) La caída típica, traducida a dinero ───────────────────────────────
    dd = result.get("max_drawdown_typical") or 0.0
    med = outcomes["median"]
    after = med * (1 - dd) if med else None
    add("drawdown_dollars", "Prepárate para los baches",
        "alerta" if dd >= 0.35 else "neutral",
        V(85, "Cómo se va a sentir una mala racha", "El bache que tendrás que aguantar",
          "Lo que verás en pantalla un mal año"),
        [V(86, f"En un mal momento este portafolio suele ceder {A(86, _pct(dd))}.",
           f"Las malas rachas de esta cartera rondan el {_pct(dd)} de caída.",
           f"Cuando vienen mal dadas, lo habitual aquí es perder {A(88, _pct(dd))}."),
         V(87, f"Traducido a tu caso: ver la cuenta bajar de {A(89, _money(med))} a "
               f"{A(90, _money(after))} y no tocar nada.",
           f"En dinero tuyo: pasar de {A(91, _money(med))} a {A(92, _money(after))} y aguantar.",
           f"Puesto en cifras concretas: {A(93, _money(med))} convertidos en "
           f"{A(94, _money(after))} durante una temporada."),
         V(88, "Esa caída es temporal en el papel, pero se vuelve pérdida definitiva en el momento "
               "en que vendes.",
           "Mientras no vendas es una cifra en pantalla; al vender se convierte en pérdida real.",
           "La diferencia entre un bache y una pérdida la marca lo que decidas hacer ese día."),
         V(89, "Decidir hoy cómo vas a reaccionar vale más que cualquier pronóstico.",
           "Tener la respuesta preparada de antemano es lo que evita las decisiones caras.",
           "Conviene escribir ahora qué harás entonces, con la cabeza fría.")],
        value=dd, importance=imp(50, 85 * dd))

    # ── 7) Poder adquisitivo ─────────────────────────────────────────────────
    real = outcomes["median_real"]
    keep = outcomes["prob_keep_power"]
    extra = ""
    if keep is not None:
        extra = V(93, f"Con todo, en {_pct(keep)} de los escenarios tu dinero crece por encima de "
                      f"la inflación, que es la meta mínima real de invertir.",
                  f"La buena noticia: en {_pct(keep)} de los futuros le ganas a la inflación, que "
                  f"es el primer objetivo de cualquier plan.",
                  f"Aun así, {_pct(keep)} de los caminos conservan poder de compra o lo mejoran.")
    add("real_value", "Poder adquisitivo", "neutral",
        V(94, "Qué comprarás de verdad con eso", "El número de hoy, no el de mañana",
          "Cuánto vale ese dinero en realidad"),
        [V(95, f"Tu mediana de {_money(med)} suena grande, pero dentro de {years} años los precios "
               f"también habrán subido.",
           f"Los {_money(med)} de la mediana impresionan hoy; en {years} años valdrán menos de lo "
           f"que parecen.",
           f"Conviene bajar los {_money(med)} de la mediana a dinero de hoy antes de celebrarlos."),
         V(96, f"Equivalen a {A(96, _money(real))} actuales, contando una inflación del "
               f"{_pct(INFLATION)} anual.",
           f"Con {_pct(INFLATION)} de inflación al año, son {A(97, _money(real))} en dinero de hoy.",
           f"Al ritmo del {_pct(INFLATION)} anual de inflación, se quedan en {A(98, _money(real))} "
           f"de poder de compra actual."),
         V(97, "Pensar en poder de compra — y no en el número nominal — es lo que evita planes que "
               "parecen holgados y luego no alcanzan.",
           "Razonar en dinero de hoy es la única forma honesta de saber si el plan llega.",
           "El número grande tranquiliza; el número real es el que decide si alcanza."),
         extra],
        value=real, importance=imp(55, 40 * (1 - (real or 0) / max(med or 1, 1))))

    # ── 8) La cola mala, con nombre y apellido ───────────────────────────────
    cvar = outcomes["cvar5"]
    add("cvar", "Lo que puedes perder", "neutral",
        V(101, "El tramo malo, con nombre y apellido", "Cómo sería el peor 5% de los futuros",
          "El escenario feo, puesto en cifras"),
        [V(102, f"Si te toca el peor 5% de los futuros, terminarías en promedio con {_money(cvar)}.",
           f"En la peor veinteava parte de los escenarios, el final medio es {_money(cvar)}.",
           f"El peor 5% de los caminos deja, de media, {_money(cvar)}."),
         V(103, "No es el fin del mundo ni una fatalidad: es el escenario para el que conviene "
                "estar preparado mentalmente antes de invertir.",
           "No es una condena, es simplemente la parte del abanico que hay que poder asumir.",
           "Saberlo de antemano quita casi todo su poder a ese escenario."),
         V(104, "Es justo cuando se toman las peores decisiones, y por eso se planifica antes.",
           "Las decisiones caras se toman ahí; tenerlo previsto es la mejor defensa.",
           "Quien lo ha pensado con calma antes, rara vez improvisa después.")],
        value=cvar, importance=imp(44))

    # ── 9) Quién pone el dinero: tu bolsillo o el mercado ────────────────────
    ms = outcomes["market_share"]
    if ms is not None:
        add("market_vs_pocket", "Mercado y tu bolsillo",
            "positivo" if ms >= 0.5 else "neutral",
            V(107, "Quién pone realmente el dinero", "Cuánto pones tú y cuánto el mercado",
              "El reparto entre ahorro y rendimiento"),
            [V(108, f"De los {_money(med)} de la mediana, {_money(outcomes['invested'])} salen de "
                    f"tu bolsillo y {A(108, _money(outcomes['market_gain']))} los pondría el mercado.",
               f"Del resultado mediano ({_money(med)}), tú aportas {_money(outcomes['invested'])} y "
               f"el mercado añade {A(109, _money(outcomes['market_gain']))}.",
               f"Tu esfuerzo son {_money(outcomes['invested'])}; el resto hasta {_money(med)}, "
               f"{A(110, _money(outcomes['market_gain']))}, es rendimiento."),
             V(109, f"Es decir: el {_pct(ms)} del resultado sería rendimiento, no ahorro.",
               f"Dicho de otra forma, {_pct(ms)} de lo que acabas teniendo no lo has ahorrado tú.",
               f"El {_pct(ms)} del total vendría del interés compuesto, no de tus depósitos."),
             V(110, "Eso explica por qué empezar temprano y no interrumpir pesa más que acertar el "
                    "momento de entrada.",
               "Por eso el tiempo dentro del mercado importa más que elegir el día de entrada.",
               "Es el argumento más sólido a favor de la constancia frente a la puntería.")],
            value=ms, importance=imp(46, 25 * ms))

    # ── 10) ¿Compensa el riesgo frente a un depósito seguro? ─────────────────
    pb = outcomes["prob_beat_savings"]
    if pb is not None:
        if pb < 0.5:
            add("vs_savings", "¿Vale el riesgo?", "alerta",
                V(113, "Mucho sobresalto para tan poca ventaja", "El riesgo no se está pagando",
                  "Sales perdiendo frente a un depósito"),
                [V(114, f"Este portafolio le gana a un depósito seguro al {_pct(SAFE_RATE)} anual en "
                        f"apenas {_pct(pb)} de los escenarios.",
                   f"Frente a un depósito al {_pct(SAFE_RATE)}, solo vence en {_pct(pb)} de los futuros.",
                   f"Contra una alternativa segura al {_pct(SAFE_RATE)} anual, gana {_pct(pb)} de "
                   f"las veces."),
                 V(115, f"Y aun así te hace pasar por caídas de {A(115, _pct(dd))}.",
                   f"Todo ello aguantando bajones de {A(116, _pct(dd))} por el camino.",
                   f"Con el añadido de tener que soportar caídas de {A(117, _pct(dd))}."),
                 V(116, "Cuando el premio esperado no compensa el mal rato, casi siempre sobra "
                        "riesgo mal pagado; suele arreglarse diversificando, no apostando más fuerte.",
                   "Riesgo que no paga es riesgo mal colocado: la salida es mejorar la mezcla, no "
                   "subir la apuesta.",
                   "Antes de aceptar ese trato conviene revisar la composición: casi siempre hay "
                   "una versión más eficiente de la misma idea.")],
                value=pb, importance=imp(60, 70 * (0.5 - pb)))
        else:
            add("vs_savings", "¿Vale el riesgo?", "positivo",
                V(117, "El riesgo está pagando", "Compensa frente a un depósito seguro",
                  "El vaivén tiene premio aquí"),
                [V(118, f"Este portafolio supera a un depósito seguro al {_pct(SAFE_RATE)} anual en "
                        f"{_pct(pb)} de los escenarios.",
                   f"Frente a una alternativa segura al {_pct(SAFE_RATE)}, gana en {_pct(pb)} de "
                   f"los futuros simulados.",
                   f"En {_pct(pb)} de los caminos le saca ventaja a un depósito al {_pct(SAFE_RATE)} "
                   f"anual."),
                 V(119, "Ese margen es tu premio por tolerar el vaivén: probable, nunca garantizado.",
                   "Es exactamente lo que se cobra por aceptar el movimiento: una probabilidad, no "
                   "una promesa.",
                   "El extra existe, aunque llega en forma de probabilidad y no de certeza."),
                 V(120, "Y solo lo cobra quien se queda el tiempo suficiente.",
                   "La condición es permanecer: quien sale a mitad de camino no lo ve.",
                   "Se paga al final del plazo, no durante.")],
                value=pb, importance=imp(44, 20 * (pb - 0.5)))

    # ── 11) Eficiencia (Sharpe) ──────────────────────────────────────────────
    sharpe = (structure["ann_return"] - SAFE_RATE) / vol if vol and vol > 0 else None
    if sharpe is not None:
        if sharpe < 0.35:
            add("sharpe", "Eficiencia", "alerta",
                V(123, "Pagas mucho riesgo por poco retorno", "La eficiencia se queda corta",
                  "Demasiado sobresalto por cada punto"),
                [V(124, f"Tu eficiencia es baja (Sharpe {sharpe:.2f}, la relación entre lo que "
                        f"esperas ganar y lo que sufres por conseguirlo).",
                   f"La relación entre premio y sufrimiento es floja: Sharpe de {sharpe:.2f}.",
                   f"Medida la eficiencia (Sharpe {sharpe:.2f}), el retorno no luce tanto una vez "
                   f"descontado el vaivén."),
                 V(125, "Significa que el retorno esperado no compensa bien el camino que hay que "
                        "recorrer para cobrarlo.",
                   "En otras palabras, estás pagando caro en nervios cada punto de rendimiento.",
                   "El rendimiento está ahí, pero sale a un precio alto en sobresaltos."),
                 V(126, "Portafolios más equilibrados suelen lograr un resultado parecido con "
                        "bastante menos sobresalto.",
                   "Una mezcla mejor repartida daría un final similar por un camino más llevadero.",
                   "Casi siempre existe una versión más eficiente de la misma idea.")],
                value=sharpe, importance=imp(52, 60 * (0.35 - sharpe)))
        elif sharpe >= 0.7:
            add("sharpe", "Eficiencia", "positivo",
                V(127, "Buen retorno por cada punto de riesgo", "La eficiencia acompaña",
                  "El equilibrio está bien resuelto"),
                [V(128, f"Tu eficiencia es sólida (Sharpe {sharpe:.2f}): el rendimiento esperado "
                        f"compensa bien el vaivén que asumes.",
                   f"Con un Sharpe de {sharpe:.2f}, lo que esperas ganar justifica el camino.",
                   f"La relación entre premio y riesgo es buena: Sharpe de {sharpe:.2f}."),
                 V(129, "Es la señal de una mezcla trabajada, no de una apuesta con suerte.",
                   "Ese número no sale de acertar, sale de combinar bien.",
                   "Habla de diseño, no de fortuna.")],
                value=sharpe, importance=imp(43))

    # ── 12) Modo retiro: ¿te alcanza el dinero? ──────────────────────────────
    if retirement:
        ruin = float(np.mean(np.asarray(result["final_values"]) <= 0))
        add("ruin", "Modo retiro", "alerta" if ruin >= 0.10 else "neutral",
            V(133, "¿Te alcanza el dinero?", "Cuánto dura el capital",
              "El riesgo de quedarte sin fondo"),
            [V(134, f"Retirando {tg.per_month(_money(abs(inputs.get('monthly_contribution', 0.0))))}, "
                    f"el capital se agota antes de los {years} años en {_pct(ruin)} de los escenarios.",
               f"Con retiros de {tg.per_month(_money(abs(inputs.get('monthly_contribution', 0.0))))}, "
               f"en {_pct(ruin)} de los futuros el dinero no llega a los {years} años.",
               f"Sacando {tg.per_month(_money(abs(inputs.get('monthly_contribution', 0.0))))}, "
               f"{_pct(ruin)} de los caminos se quedan sin fondo antes de tiempo."),
             V(135, "En retiro el orden de los años importa tanto como el promedio.",
               "Cuando se retira dinero, la secuencia pesa tanto como la media.",
               "Retirando, no da igual cuándo llegan los años malos."),
             V(136, "Unos primeros años malos mientras sacas dinero hacen un daño muy difícil de "
                    "revertir después.",
               "Un mal arranque con retiros en marcha deja una herida que los buenos años "
               "posteriores rara vez cierran.",
               "El peor escenario no es una mala década: es una mala primera etapa.")],
            value=ruin, importance=imp(70, 120 * ruin))

    # ═════════════════════════════════════════════════════════════════════════
    # Dimensiones que no salen de μ/Σ: sector, divisa, renta fija, costes, aporte
    # Cada una en su propio try/except — si falla el dato, se pierde ESE hallazgo
    # y no el análisis entero.
    # ═════════════════════════════════════════════════════════════════════════

    # ── 13) Concentración por SECTOR (aunque haya muchos nombres) ────────────
    try:
        rows = ((ctx or {}).get("exposure") or {}).get("by_sector") or []
        if rows and n >= 3:
            top_s = rows[0]
            pct_s = float(top_s["pct"])
            if pct_s >= 45:
                add("sector_concentration", "Concentración", "alerta",
                    V(141, "Un solo sector decide el resultado", "Todo tu dinero mira al mismo sitio",
                      "Muchos nombres, un solo sector"),
                    [V(142, f"El {pct_s:.0f}% de tu dinero está en {top_s['name']}, aunque lo tengas "
                            f"repartido entre {n} activos distintos.",
                       f"Tienes {n} posiciones, pero {pct_s:.0f}% del capital pertenece al mismo "
                       f"sector: {top_s['name']}.",
                       f"Repartir en {n} nombres no ha repartido el sector: {top_s['name']} concentra "
                       f"el {pct_s:.0f}%."),
                     V(143, "Las empresas de un mismo sector comparten clientes, regulación y ciclo: "
                            "cuando el sector se enfría, se enfrían casi todas a la vez.",
                       "Dentro de un sector, los problemas se contagian: mismo ciclo, mismas reglas, "
                       "mismos clientes.",
                       "Un sector entero puede pasar años a contracorriente por motivos que nada "
                       "tienen que ver con lo buena que sea cada empresa."),
                     V(144, "Añadir un sector de carácter distinto haría más por tu tranquilidad que "
                            "otra empresa parecida.",
                       "La diversificación que falta aquí no es de nombres, es de sectores.",
                       "Meter algo que dependa de otro ciclo cambiaría bastante el perfil.")],
                    value=pct_s / 100.0, importance=imp(53, 60 * (pct_s / 100.0 - 0.45)))
    except Exception:
        pass

    # ── 14) Exposición a divisa ──────────────────────────────────────────────
    try:
        cur = (ctx or {}).get("currencies") or {}
        if cur and assets:
            wmap = {a["symbol"]: a["weight"] for a in assets}
            foreign = sum(w for s, w in wmap.items() if (cur.get(s) or "USD") != "USD")
            monedas = sorted({c for s, c in cur.items() if c and c != "USD" and wmap.get(s, 0) > 0})
            if foreign >= 0.20 and monedas:
                add("currency", "Divisa", "neutral",
                    V(147, "Parte del resultado la decide la divisa", "No todo cotiza en dólares",
                      "Tienes una apuesta de moneda dentro"),
                    [V(148, f"El {_pct(foreign)} de tu cartera cotiza en "
                            f"{tg.natural_join(monedas)}, no en dólares.",
                       f"Casi {_pct(foreign)} del capital vive en otra moneda "
                       f"({tg.natural_join(monedas)}).",
                       f"{tg.natural_join(monedas)} {tg.plural(len(monedas), 'pesa', 'pesan')} "
                       f"{_pct(foreign)} de tu cartera."),
                     V(149, "Eso añade una segunda apuesta a la primera: además de acertar con los "
                            "activos, influye cómo se mueva el tipo de cambio.",
                       "Ganas o pierdes por dos vías: lo que hagan los activos y lo que haga la moneda.",
                       "El tipo de cambio puede sumar o restar por su cuenta, al margen de las empresas."),
                     V(150, "No es bueno ni malo en sí: a largo plazo suele suavizar tanto como "
                            "estorba, y conviene saber que está ahí.",
                       "A muchos años tiende a compensarse, pero explica diferencias que si no "
                       "parecerían inexplicables.",
                       "Tenerlo presente evita sorpresas cuando el resultado no cuadre con lo que "
                       "hicieron los activos.")],
                    value=foreign, importance=imp(45, 30 * foreign))
    except Exception:
        pass

    # ── 15) Renta fija frente al horizonte ───────────────────────────────────
    try:
        rows_c = ((ctx or {}).get("exposure") or {}).get("by_class") or []
        bonos = sum(float(r["pct"]) for r in rows_c if r["name"] == "Bonos")
        if bonos >= 30 and years >= 15:
            add("bonds_horizon", "Renta fija", "neutral",
                V(153, "Mucho freno para tantos años", "La renta fija te está frenando",
                  "Colchón amplio para un plazo largo"),
                [V(154, f"Un {bonos:.0f}% de la cartera está en renta fija y te quedan {years} años "
                        f"por delante.",
                   f"Con {years} años de horizonte, llevar {bonos:.0f}% en bonos es un colchón amplio.",
                   f"La renta fija ocupa {bonos:.0f}% en un plan que dura {years} años."),
                 V(155, "Los bonos cumplen su función cuando el dinero se necesita pronto: sujetan "
                        "las caídas a cambio de crecer menos.",
                   "Su papel es amortiguar, y ese servicio se paga en rendimiento.",
                   "Ese colchón reduce los sustos, pero también el techo del resultado."),
                 V(156, "Con un plazo tan largo, el tiempo ya hace parte de ese trabajo por ti.",
                   "A tantos años vista, el propio horizonte es un amortiguador que no cuesta "
                   "rendimiento.",
                   "Conviene revisar si ese colchón responde a una necesidad real de corto plazo o "
                   "solo a la costumbre.")],
                value=bonos / 100.0, importance=imp(48, 20 * (bonos / 100.0)))
        elif bonos <= 5 and years <= 7 and n >= 2:
            add("bonds_horizon", "Renta fija", "alerta",
                V(157, "Plazo corto sin ningún colchón", "Poco tiempo y nada que amortigüe",
                  "Sin freno para un horizonte corto"),
                [V(158, f"La cartera es prácticamente toda de riesgo y el plazo es de {years} años.",
                   f"Con {years} años por delante no hay apenas renta fija que sujete las caídas.",
                   f"En {years} años, una cartera sin colchón deja poco margen de maniobra."),
                 V(159, "Un mal tramo cerca del final no tiene tiempo de recuperarse.",
                   "Si la caída llega al final del plazo, no queda recorrido para revertirla.",
                   "El riesgo aquí no es la caída, es que llegue tarde."),
                 V(160, "Cuando la fecha manda, conviene que una parte del dinero deje de depender "
                        "del mercado según se acerca.",
                   "Con una fecha concreta en el calendario, ir bajando riesgo cerca del final "
                   "protege lo conseguido.",
                   "Merece la pena decidir de antemano cuándo empezar a asegurar el resultado.")],
                value=bonos / 100.0, importance=imp(54))
    except Exception:
        pass

    # ── 16) Lo que se llevan las comisiones a largo plazo ────────────────────
    try:
        fees = float(inputs.get("annual_fees_pct") or 0.0) / 100.0
        if fees > 0 and med:
            sin_fees = med * ((1 + fees) ** years)
            coste = sin_fees - med
            if coste > 0:
                sent = "alerta" if fees >= 0.01 else "neutral"
                add("fees", "Costes", sent,
                    V(163, "Lo que se llevan las comisiones", "El coste que no se ve en el gráfico",
                      "Cuánto cuesta ese porcentaje anual"),
                    [V(164, f"Un {_pct(fees, 2)} anual de comisiones parece poco, pero en {years} "
                            f"años se lleva {A(164, _money(coste))} de tu resultado.",
                       f"Ese {_pct(fees, 2)} al año se traduce en {A(165, _money(coste))} menos al "
                       f"cabo de {years} años.",
                       f"Las comisiones del {_pct(fees, 2)} anual restan {A(166, _money(coste))} a "
                       f"lo largo de los {years} años."),
                     V(165, "Las comisiones se cobran siempre, ganes o pierdas, y se comen el "
                            "interés compuesto justo por donde más duele.",
                       "Es el único coste garantizado del plan: no depende del mercado ni de tu suerte.",
                       "Se pagan cada año sobre el total, así que crecen a la vez que tu cartera."),
                     V(166, "Es la variable más fácil de mejorar de todo el plan: no exige acertar "
                            "nada, solo comparar.",
                       "De todo lo que puedes controlar, esta es la que más resultado da por menos "
                       "esfuerzo.",
                       "Bajar ese porcentaje es la única mejora del plan que no depende del mercado.")],
                    value=fees, importance=imp(50, 900 * fees))
    except Exception:
        pass

    # ── 17) El aporte mensual frente al capital inicial ──────────────────────
    try:
        cap = float(inputs.get("initial_capital") or 0.0)
        flow = float(inputs.get("monthly_contribution") or 0.0)
        if flow > 0 and cap > 0:
            aportado = flow * 12 * years
            share_ap = aportado / (cap + aportado)
            if share_ap >= 0.6:
                add("contribution", "Tu plan de ahorro", "positivo",
                    V(169, "Tu constancia pesa más que el capital", "El plan lo construye el aporte",
                      "Aquí manda el hábito, no el punto de partida"),
                    [V(170, f"De todo lo que pondrás, {_pct(share_ap)} vendrá de tus aportes "
                            f"mensuales y no del capital con el que empiezas.",
                       f"Tus {tg.per_month(_money(flow))} suman {_money(aportado)} en {years} años, "
                       f"muy por encima de los {_money(cap)} iniciales.",
                       f"El capital inicial son {_money(cap)}; tus aportes acumularán "
                       f"{_money(aportado)}."),
                     V(171, "Eso es una buena noticia: el resultado depende sobre todo de algo que "
                            "controlas tú, no del mercado.",
                       "La palanca principal del plan está en tus manos, no en la bolsa.",
                       "Cuando el aporte manda, la disciplina vale más que el acierto."),
                     V(172, "Mantener el aporte en los años malos es, con diferencia, lo que más "
                            "cambia el final.",
                       "Justo en las caídas es cuando cada aporte compra más, aunque sea cuando "
                       "menos apetece.",
                       "Interrumpirlo en el peor momento es el error que más caro sale.")],
                    value=share_ap, importance=imp(47, 20 * share_ap))
            elif share_ap <= 0.2:
                add("contribution", "Tu plan de ahorro", "neutral",
                    V(173, "Casi todo depende del capital inicial", "El aporte apenas mueve la aguja",
                      "El punto de partida lo decide casi todo"),
                    [V(174, f"Tus aportes sumarán {_money(aportado)} frente a los {_money(cap)} con "
                            f"los que arrancas: solo {_pct(share_ap)} del total.",
                       f"El capital inicial ({_money(cap)}) pesa mucho más que todo lo que aportarás "
                       f"({_money(aportado)}).",
                       f"De cuanto pondrás, apenas {_pct(share_ap)} llegará por la vía del aporte "
                       f"mensual."),
                     V(175, "Significa que el resultado lo decide sobre todo cómo se comporte el "
                            "dinero que ya está dentro.",
                       "Con ese reparto, el mercado tiene más voz que tu constancia.",
                       "El plan descansa en la inversión, no en el ahorro."),
                     V(176, "Subir el aporte es la palanca que más control te devuelve sobre el final.",
                       "Si quieres depender menos del mercado, la vía es aportar más.",
                       "Cada euro adicional de aporte reduce cuánto depende todo de la suerte.")],
                    value=share_ap, importance=imp(43))
    except Exception:
        pass

    # ── Orden final: por importancia, sin repetir tema ───────────────────────
    # Descarte por firma de prefijo (el truco de DLP Analyzer): dos hallazgos que empiezan
    # igual cuentan la misma historia, y ocupar dos de las cinco tarjetas con lo mismo es
    # justo lo que hacía que todos los análisis se parecieran.
    f.sort(key=lambda x: -x["importance"])
    vistos: set[str] = set()
    out: list[dict] = []
    for item in f:
        sig = (item["text"] or "")[:24].lower()
        if sig and sig in vistos:
            continue
        vistos.add(sig)
        out.append(item)
    return out


def analyze(market_stats: dict, tickers: list[str], weights, result: dict, inputs: dict) -> dict:
    """Orquestador: estructura + distribución + hallazgos rankeados.

    `result` es el dict que devuelve `run_montecarlo` (tiene `final_values` y
    `max_drawdown_typical`). Devuelve un dict liviano (solo escalares y filas por activo).
    """
    structure = portfolio_structure(market_stats, tickers, weights)
    outcomes = outcome_metrics(result["final_values"], inputs)
    ctx = _portfolio_context(tickers, weights)
    findings = build_findings(structure, outcomes, result, inputs, ctx)
    return {"structure": structure, "outcomes": outcomes, "findings": findings,
            "archetype": _archetype(structure, ctx)}
