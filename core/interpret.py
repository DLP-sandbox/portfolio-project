"""Interpretación en lenguaje natural de la proyección.

DOS modos:
- `interpret_locally(...)`: intérprete por REGLAS, 100% local, **costo $0** (sin API). Es el
  modo por defecto de la app.
- `interpret_with_claude(...)`: OPCIONAL. Solo corre si el usuario lo activa explícitamente
  Y hay ANTHROPIC_API_KEY. Por defecto NO se invoca → no gasta créditos.

La interpretación nunca recomienda comprar/vender un activo: describe escenarios.
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


def claude_available() -> bool:
    """True solo si hay ANTHROPIC_API_KEY (en st.secrets o env). No llama a la API."""
    import os
    try:
        import streamlit as st
        if "ANTHROPIC_API_KEY" in st.secrets:
            return True
    except Exception:
        pass
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def interpret_with_claude(result: dict, inputs: dict, stress: dict | None = None,
                          model: str = "claude-opus-4-8") -> str:
    """OPCIONAL — interpretación con Claude. CUESTA CRÉDITOS DE API.

    Solo se ejecuta si el llamador decide invocarla explícitamente y hay API key.
    Nunca se llama por defecto en la app (ver core/interpret: el default es local).
    """
    import os

    key = None
    try:
        import streamlit as st
        key = st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        key = None
    key = key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("No hay ANTHROPIC_API_KEY configurada — usa la interpretación local (gratis).")

    import numpy as np
    from anthropic import Anthropic

    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    facts = (
        f"Horizonte {inputs['horizon_years']} años. Mediana ${p50:,.0f}, P5 ${p5:,.0f}, "
        f"P95 ${p95:,.0f}. Prob. meta: {result.get('prob_target')}. "
        f"Drawdown típico {result.get('max_drawdown_typical')}. "
        f"Prob. ruina {result.get('probability_of_ruin')}.")
    system = ("Eres un asistente de Diario Largo Plazo. Explica esta PROYECCIÓN PROBABILÍSTICA "
              "en español neutro de Latinoamérica, claro y honesto. PROHIBIDO: prometer certeza, "
              "garantizar, predecir, o recomendar comprar/vender un activo. Aclara siempre que el "
              "futuro puede diferir.")
    client = Anthropic(api_key=key)
    msg = client.messages.create(
        model=model, max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": f"Interpreta esta proyección de portafolio:\n{facts}"}],
    )
    return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
