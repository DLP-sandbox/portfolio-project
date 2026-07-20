"""Interpretación en lenguaje natural de la proyección.

`interpret_locally(...)`: intérprete por REGLAS, 100% local, sin ninguna API de IA.
Nunca recomienda comprar/vender un activo: solo describe escenarios.
"""
from __future__ import annotations


def _money(x: float | None) -> str:
    return "—" if x is None else f"${x:,.0f}"


def interpret_locally(result: dict, inputs: dict, stress: dict | None = None) -> str:
    """Narrativa honesta construida a partir de los números. Sin API, sin costo."""
    import numpy as np

    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    years = inputs["horizon_years"]
    flow = inputs.get("monthly_contribution", 0.0)
    lines: list[str] = []

    if flow < 0:  # modo retiro
        ruin = result["probability_of_ruin"]
        verdict = "preocupante" if ruin >= 0.20 else "moderado" if ruin >= 0.05 else "bajo"
        lines.append(
            f"En **modo retiro** (retiras {_money(-flow)}/mes), tu capital se agotó antes "
            f"de los {years} años en **{ruin*100:.0f}%** de los 10.000 escenarios — un riesgo "
            f"de ruina **{verdict}**. El escenario mediano dejó {_money(p50)} al final del horizonte.")
        if ruin >= 0.05:
            lines.append("Para bajar el riesgo de ruina puedes reducir el retiro mensual, "
                         "acortar el horizonte o sumar activos más estables.")
    else:  # acumulación
        spread = (p95 / p5) if p5 > 0 else float("inf")
        lines.append(
            f"A {years} años, el escenario **mediano** proyecta {_money(p50)}: la mitad de los "
            f"futuros simulados terminó por encima y la mitad por debajo.")
        lines.append(
            f"Entre el escenario **pesimista** ({_money(p5)}, si va mal) y el **optimista** "
            f"({_money(p95)}, si va bien) hay ~{spread:.0f} veces de diferencia. Esa amplitud es "
            f"esperable: la incertidumbre a 20 años es enorme y conviene planificar con el rango, "
            f"no con un solo número.")

    if inputs.get("target"):
        prob = result.get("prob_target") or 0.0
        verdict = "alta" if prob >= 0.70 else "moderada" if prob >= 0.50 else "baja"
        lines.append(
            f"Tu meta de {_money(inputs['target'])} se alcanzó en **{prob*100:.0f}%** de los "
            f"escenarios — probabilidad {verdict}.")
        if prob < 0.50:
            lines.append("Para mejorar la probabilidad de meta puedes subir el aporte mensual, "
                         "extender el horizonte o revisar la composición del portafolio.")

    dd = result.get("max_drawdown_typical", 0.0)
    lines.append(
        f"Habrá baches en el camino: la **caída típica** (cuánto baja en un mal momento) fue "
        f"~{dd*100:.0f}%. Soportarla sin vender en pánico es parte del plan a largo plazo.")

    if inputs.get("distribution") == "t-student":
        lines.append("Usaste un modelo que toma en cuenta **caídas bruscas** más seguido, "
                     "para ver escenarios de corto/mediano plazo más realistas.")

    fees, tax = inputs.get("annual_fees_pct", 0.0), inputs.get("annual_tax_on_gains_pct", 0.0)
    if fees or tax:
        lines.append(
            f"Incluiste costos: **{fees:.0f}% de comisiones** al año y **{tax:.0f}% de impuesto** sobre "
            f"las ganancias. Por el interés compuesto, restan más de lo que parece.")

    if stress and stress.get("events"):
        worst = max(stress["events"], key=lambda e: e["portfolio_drawdown"])
        lines.append(
            f"**Prueba de crisis**: un evento como *{worst['name']}* implicaría para tu portafolio una "
            f"caída estimada de ~{worst['portfolio_drawdown']*100:.0f}% (según cuánto se mueve tu "
            f"portafolio frente al mercado). Es una estimación de magnitud, no una predicción.")

    lines.append(
        "_Recuerda: esto proyecta escenarios estadísticos basados en retornos históricos. "
        "No es predicción ni recomendación. Los retornos reales pueden diferir significativamente._")
    return "\n\n".join(lines)


def interpret_goal(result: dict, inputs: dict) -> str:
    """Párrafo natural que explica la vista '¿Alcanzo mi meta?' — con o sin meta fijada."""
    import numpy as np

    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    years = inputs["horizon_years"]
    target = inputs.get("target")
    retirement = inputs.get("monthly_contribution", 0.0) < 0

    if retirement:
        ruin = result.get("probability_of_ruin", 0.0)
        return (f"En modo retiro la pregunta cambia: no es *cuánto llego a tener*, sino *cuánto me dura el dinero*. "
                f"El gráfico muestra que en el **{ruin*100:.0f}%** de los escenarios el capital se agota antes de los "
                f"{years} años; en la mitad de los casos terminarías con {_money(p50)} o más. Si ese porcentaje te "
                f"incomoda, bajar el retiro mensual o acortar el horizonte lo reduce de inmediato.")

    if target:
        prob = result.get("prob_target") or 0.0
        verdict = ("muy alcanzable" if prob >= 0.70 else
                   "posible, aunque no asegurada" if prob >= 0.50 else "hoy exigente")
        where = ("por debajo del resultado típico, así que es un objetivo cómodo" if target <= p50 else
                 "entre lo típico y el mejor de los casos, así que necesitarás algo de viento a favor"
                 if target <= p95 else
                 "por encima incluso del mejor 5% simulado, así que con el plan actual es muy difícil")
        lever = ("Si quieres subir esa probabilidad, el aporte mensual y el horizonte son las dos palancas "
                 "que más la mueven." if prob < 0.70 else
                 "Mantén el rumbo: el hábito de aportar constante es lo que sostiene esa probabilidad.")
        return (f"Tu meta de **{_money(target)}** a {years} años se alcanzó en el **{prob*100:.0f}%** de los 10.000 "
                f"escenarios — una meta {verdict}. En el gráfico, tu objetivo queda {where}. {lever} No es una "
                f"garantía: los retornos reales pueden diferir de lo simulado.")

    spread = (p95 / p5) if p5 > 0 else float("inf")
    return (f"Aún no fijaste una meta, así que aquí ves el **abanico completo** de resultados posibles a {years} años. "
            f"La mayoría de los futuros se agrupan alrededor de {_money(p50)}, pero el rango es amplio: desde ~{_money(p5)} "
            f"si el mercado acompaña poco hasta ~{_money(p95)} si acompaña mucho — unas {spread:.0f} veces de diferencia "
            f"entre un extremo y otro. Si escribes una meta en 'Tu plan', te diré en qué porcentaje de escenarios se logra.")


def interpret_risks(result: dict, inputs: dict, analysis: dict | None = None) -> str:
    """Párrafo natural que resume los riesgos del portafolio para principiante/intermedio."""
    import numpy as np

    dd = result.get("max_drawdown_typical", 0.0)
    years = inputs["horizon_years"]
    retirement = inputs.get("monthly_contribution", 0.0) < 0
    p50 = float(np.percentile(result["final_values"], 50))
    after = p50 * (1.0 - dd)

    parts = [
        f"El riesgo más real de este portafolio no es 'perderlo todo', sino **aguantar las caídas del camino**: "
        f"en un mal momento suele retroceder ~**{dd*100:.0f}%**, lo que se sentiría como ver tu inversión bajar de "
        f"~{_money(p50)} a ~{_money(after)}. Quien vende ahí convierte una caída temporal en una pérdida definitiva."
    ]
    if retirement:
        ruin = result.get("probability_of_ruin", 0.0)
        parts.append(f"Y como estás retirando, pesa el riesgo de secuencia: en el {ruin*100:.0f}% de los escenarios el "
                     f"capital se agota antes de los {years} años.")
    if analysis:
        s = analysis.get("structure", {})
        corr, mw, sym = s.get("wavg_corr"), s.get("max_weight"), s.get("max_weight_symbol", "")
        vol = s.get("ann_vol")
        bits = []
        if vol is not None:
            bits.append(f"una volatilidad anual de ±{vol*100:.0f}%")
        if mw is not None and mw >= 0.30:
            bits.append(f"una concentración alta ({mw*100:.0f}% en {sym})")
        if corr is not None and corr >= 0.70:
            bits.append(f"activos que se mueven muy juntos (correlación media {corr:.2f})")
        if bits:
            parts.append("Lo que más suma a ese riesgo es " + ", ".join(bits) + ".")
    parts.append("Nada de esto predice el futuro: es la forma de la incertidumbre, para que planifiques con la cabeza "
                 "fría y no con miedo.")
    return " ".join(parts)
