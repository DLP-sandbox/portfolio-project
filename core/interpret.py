"""Interpretación en lenguaje natural de la proyección.

`interpret_locally(...)`: intérprete por REGLAS, 100% local, sin ninguna API de IA.
Nunca recomienda comprar/vender un activo: solo describe escenarios.
"""
from __future__ import annotations

from core import textgen as _tg


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

    def _v(idx, *ops):
        """Variante determinista por hueco: el mismo plan se lee igual siempre; dos planes
        distintos no se leen calcados."""
        return _tg.variant(_tg.seed_key(inputs), idx, *ops)

    if flow < 0:  # modo retiro
        ruin = result["probability_of_ruin"]
        verdict = "preocupante" if ruin >= 0.20 else "moderado" if ruin >= 0.05 else "bajo"
        lines.append(
            f"En **modo retiro** (retiras {_money(-flow)} al mes), tu capital se agotó antes "
            f"de los {years} años en **{ruin*100:.0f}%** de los 10.000 escenarios — un riesgo "
            f"de ruina **{verdict}**. El escenario mediano dejó {_money(p50)} al final del horizonte.")
        if ruin >= 0.05:
            lines.append(_v(1,
                "Para bajar ese riesgo puedes reducir el retiro mensual, acortar el horizonte "
                "o sumar activos más estables.",
                "Hay tres palancas para mejorarlo: sacar menos cada mes, contar con menos años "
                "por delante o dar más peso a lo que se mueve poco.",
                "Se corrige por tres vías: un retiro más pequeño, un horizonte más corto o una "
                "mezcla algo más tranquila."))
    else:  # acumulación
        spread = (p95 / p5) if p5 > 0 else float("inf")
        lines.append(_v(2,
            f"A {years} años, el escenario **mediano** proyecta {_money(p50)}: la mitad de los "
            f"futuros simulados terminó por encima y la mitad por debajo.",
            f"El punto central de la simulación a {years} años queda en {_money(p50)}, con la "
            f"mitad de los futuros por encima y la otra mitad por debajo.",
            f"Puesto en una sola cifra, {years} años de plan apuntan a {_money(p50)}: es el "
            f"resultado que deja tantos escenarios mejores como peores."))
        lines.append(_v(3,
            f"Entre el escenario **pesimista** ({_money(p5)}, si va mal) y el **optimista** "
            f"({_money(p95)}, si va bien) hay cerca de {spread:.0f} veces de diferencia. Esa "
            f"amplitud es esperable: a {years} años la incertidumbre es enorme y conviene "
            f"planificar con el rango, no con un solo número.",
            f"El abanico va desde {_money(p5)} en el escenario **pesimista** hasta "
            f"{_money(p95)} en el **optimista**: unas {spread:.0f} veces de distancia entre uno "
            f"y otro. Con {years} años por delante esa horquilla es normal, y planificar con "
            f"ella es más honesto que fiarse de un número único.",
            f"Lo **pesimista** ({_money(p5)}) y lo **optimista** ({_money(p95)}) están separados "
            f"por unas {spread:.0f} veces. No es un fallo del modelo: es lo que da de sí la "
            f"incertidumbre a {years} años, y por eso conviene razonar en rangos."))

    if inputs.get("target"):
        prob = result.get("prob_target") or 0.0
        verdict = "alta" if prob >= 0.70 else "moderada" if prob >= 0.50 else "baja"
        lines.append(_v(4,
            f"Tu meta de {_money(inputs['target'])} se alcanzó en **{prob*100:.0f}%** de los "
            f"escenarios — una probabilidad {verdict}.",
            f"Llegar a {_money(inputs['target'])} ocurrió en **{prob*100:.0f}%** de los futuros "
            f"simulados: probabilidad {verdict}.",
            f"De todos los caminos posibles, **{prob*100:.0f}%** alcanzan tu meta de "
            f"{_money(inputs['target'])}. Es una probabilidad {verdict}."))
        if prob < 0.50:
            lines.append(_v(5,
                "Para mejorar esa probabilidad puedes subir el aporte mensual, extender el "
                "horizonte o revisar la composición del portafolio.",
                "Tres palancas la mueven: aportar algo más cada mes, darle más años o cambiar "
                "la mezcla de activos.",
                "Se puede empujar al alza aumentando el aporte, ganando tiempo o ajustando qué "
                "hay dentro de la cartera."))

    dd = result.get("max_drawdown_typical", 0.0)
    lines.append(_v(6,
        f"Habrá baches en el camino: la **caída típica** (cuánto baja en un mal momento) fue "
        f"alrededor de un {dd*100:.0f}%. Soportarla sin vender en pánico es parte del plan.",
        f"El trayecto no será recto: en los malos momentos la cartera cedió alrededor de un "
        f"**{dd*100:.0f}%**. Aguantar ahí sin vender es, literalmente, parte del trabajo.",
        f"Cuenta con retrocesos: la **caída típica** rondó el **{dd*100:.0f}%**. Quien la "
        f"soporta sin tocar nada es quien acaba cobrando el rendimiento de largo plazo."))

    if inputs.get("distribution") == "t-student":
        lines.append(_v(7,
            "Usaste un modelo que contempla **caídas bruscas** con más frecuencia, para que los "
            "escenarios de corto y medio plazo salgan más realistas.",
            "El modelo elegido reserva más sitio a los **sustos fuertes**, que es lo que ocurre "
            "de verdad en los plazos cortos y medios.",
            "Al usar un modelo con **colas gruesas**, los episodios extremos aparecen tan a "
            "menudo como en la realidad, y no menos."))

    fees, tax = inputs.get("annual_fees_pct", 0.0), inputs.get("annual_tax_on_gains_pct", 0.0)
    if fees or tax:
        lines.append(
            f"Incluiste costos: **{fees:.0f}% de comisiones** al año y **{tax:.0f}% de impuesto** sobre "
            f"las ganancias. Por el interés compuesto, restan más de lo que parece.")

    if stress and stress.get("events"):
        worst = max(stress["events"], key=lambda e: e["portfolio_drawdown"])
        lines.append(
            f"**Prueba de crisis**: un evento como *{worst['name']}* implicaría para tu portafolio una "
            f"caída estimada de alrededor de un {worst['portfolio_drawdown']*100:.0f}% (según cuánto se mueve tu "
            f"portafolio frente al mercado). Es una estimación de magnitud, no una predicción.")

    lines.append(_v(8,
        "_Recuerda: esto proyecta escenarios estadísticos basados en retornos históricos. "
        "No es predicción ni recomendación. Los retornos reales pueden diferir "
        "significativamente._",
        "_Ten presente que son escenarios estadísticos calculados sobre el comportamiento "
        "histórico. Ni predicen el futuro ni son una recomendación: lo que ocurra de verdad "
        "puede alejarse bastante._",
        "_Conviene recordarlo: todo esto sale de simular el pasado muchas veces. No es una "
        "predicción ni un consejo de inversión, y la realidad puede diferir de forma notable._"))
    return "\n\n".join(lines)


def interpret_goal(result: dict, inputs: dict) -> str:
    """Párrafo natural que explica la vista '¿Alcanzo mi meta?' — con o sin meta fijada."""
    import numpy as np

    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    years = inputs["horizon_years"]
    target = inputs.get("target")
    retirement = inputs.get("monthly_contribution", 0.0) < 0

    def _v(idx, *ops):
        return _tg.variant(_tg.seed_key(inputs), idx, *ops)

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
        cierre = _v(11,
            "No es una garantía: los retornos reales pueden diferir de lo simulado.",
            "Conviene leerlo como una probabilidad, no como una promesa: la realidad puede "
            "separarse de la simulación.",
            "Nada de esto está asegurado; es la mejor estimación posible, no una certeza.")
        return _v(12,
            f"Tu meta de **{_money(target)}** a {years} años se alcanzó en el "
            f"**{prob*100:.0f}%** de los 10.000 escenarios — una meta {verdict}. En el gráfico, "
            f"tu objetivo queda {where}. {lever} {cierre}",
            f"De los 10.000 futuros simulados, **{prob*100:.0f}%** llegan a tus "
            f"**{_money(target)}** en {years} años: una meta {verdict}. Sobre el gráfico, ese "
            f"objetivo cae {where}. {lever} {cierre}",
            f"Llegar a **{_money(target)}** en {years} años ocurrió en **{prob*100:.0f}%** de "
            f"los escenarios, lo que la convierte en una meta {verdict}. Mirando el gráfico, "
            f"tu objetivo queda {where}. {lever} {cierre}")

    spread = (p95 / p5) if p5 > 0 else float("inf")
    return _v(13,
        f"Aún no fijaste una meta, así que aquí ves el **abanico completo** de resultados "
        f"posibles a {years} años. La mayoría de los futuros se agrupan alrededor de "
        f"{_money(p50)}, pero el rango es amplio: desde cerca de {_money(p5)} si el mercado "
        f"acompaña poco hasta {_money(p95)} si acompaña mucho — unas {spread:.0f} veces de "
        f"diferencia entre un extremo y otro. Si escribes una meta en 'Tu plan', te diré en qué "
        f"porcentaje de escenarios se logra.",
        f"Sin meta fijada, lo que se ve aquí es el **abanico entero** de finales posibles a "
        f"{years} años. El grueso se concentra cerca de {_money(p50)}, aunque los extremos "
        f"están lejos: {_money(p5)} si el mercado apenas acompaña y {_money(p95)} si acompaña "
        f"mucho, unas {spread:.0f} veces de distancia. Escribe un objetivo en 'Tu plan' y te "
        f"digo en cuántos escenarios se cumple.",
        f"Como no hay meta, esta vista muestra **todo el abanico** de desenlaces a {years} "
        f"años. El centro de gravedad está en {_money(p50)}; los bordes, en {_money(p5)} y "
        f"{_money(p95)} — unas {spread:.0f} veces de diferencia entre lo malo y lo bueno. "
        f"Si defines una meta en 'Tu plan', calculo en qué porcentaje de futuros se alcanza.")


def interpret_risks(result: dict, inputs: dict, analysis: dict | None = None) -> str:
    """Párrafo natural que resume los riesgos del portafolio para principiante/intermedio."""
    import numpy as np

    dd = result.get("max_drawdown_typical", 0.0)
    years = inputs["horizon_years"]
    retirement = inputs.get("monthly_contribution", 0.0) < 0
    p50 = float(np.percentile(result["final_values"], 50))
    after = p50 * (1.0 - dd)

    def _v(idx, *ops):
        return _tg.variant(_tg.seed_key(inputs), idx, *ops)

    parts = [_v(21,
        f"El riesgo más real de este portafolio no es 'perderlo todo', sino **aguantar las "
        f"caídas del camino**: en un mal momento suele retroceder alrededor de un "
        f"**{dd*100:.0f}%**, lo que se sentiría como ver tu inversión bajar de {_money(p50)} a "
        f"{_money(after)}. Quien vende ahí convierte una caída temporal en una pérdida definitiva.",
        f"Aquí el peligro no es la ruina, es **el trayecto**: en las malas rachas esta cartera "
        f"cede alrededor de un **{dd*100:.0f}%**, que en tu caso sería ver {_money(p50)} "
        f"convertidos en {_money(after)}. Esa caída solo se vuelve pérdida de verdad si vendes "
        f"mientras dura.",
        f"El riesgo que de verdad importa no es perderlo todo, sino **sostener el bache**: la "
        f"cartera suele retroceder alrededor de un **{dd*100:.0f}%** en los malos momentos "
        f"— {_money(p50)} pasando a {_money(after)}. En pantalla es temporal; al vender se "
        f"vuelve definitiva.")]
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
            bits.append(f"una volatilidad anual que sube y baja alrededor de un {vol*100:.0f}%")
        if mw is not None and mw >= 0.30:
            bits.append(f"una concentración alta ({mw*100:.0f}% en {sym})")
        if corr is not None and corr >= 0.70:
            bits.append(f"activos que se mueven muy juntos (correlación media {corr:.2f})")
        if bits:
            parts.append("Lo que más suma a ese riesgo es " + _tg.natural_join(bits) + ".")
    parts.append("Nada de esto predice el futuro: es la forma de la incertidumbre, para que planifiques con la cabeza "
                 "fría y no con miedo.")
    return " ".join(parts)


# ═════════════════════════════════════════════════════════════════════════════
# Compositor de textos con variantes (suena a IA auténtica, es 100% por reglas)
# ═════════════════════════════════════════════════════════════════════════════
# Cada texto se arma combinando pools de apertura/cuerpo/cierre (≥20 combinaciones
# por escenario) con un RNG SEMBRADO por el contenido del portafolio: el texto es
# estable entre reruns (no cambia al navegar) pero distinto entre portafolios.

def _seeded(inputs_or_key, salt: str):
    """Delegado en `core.textgen` para que haya UN solo motor de redacción."""
    return _tg.seeded(inputs_or_key, salt)


def _compose(rng, *pools) -> str:
    return _tg.es_natural(_tg.compose(rng, *pools))


def interpret_diversification(structure: dict) -> str:
    """HALLAZGO sobre la estructura (2-3 líneas), no una lectura de las cifras en pantalla.

    Regla: el usuario ya ve correlación, apuestas y mayor posición. Aquí se le dice qué
    SIGNIFICA eso para su resultado y qué cambiaría — con una sola cifra de anclaje.
    """
    corr = structure.get("wavg_corr", 0.5)
    n = structure.get("n_assets", 1)
    bets = structure.get("eff_bets", float(n))
    mw = structure.get("max_weight", 0.0)
    sym = structure.get("max_weight_symbol", "")
    top = (structure.get("assets") or [{}])[0]
    rc = top.get("risk_contrib", 0.0)
    rng = _seeded(f"{corr:.3f}|{n}|{mw:.3f}|{sym}", "diverV2")

    if n < 2:
        return ("Con un solo activo no hay estructura que analizar: tu resultado será "
                "exactamente el suyo. Sumar una segunda pieza que no dependa de lo mismo es "
                "el cambio con mayor impacto que puedes hacer hoy.")

    # Caso 0: la renta variable manda el riesgo, pero la mezcla está bien construida.
    # Es lo normal en una cartera sana: conviene explicarlo, no alarmar.
    if rc >= 0.45 and corr < 0.35:
        pools = ([
            f"Aunque tienes {n} piezas distintas, casi todo tu riesgo lo aporta {sym}.",
            f"El reparto del dinero engaña: el riesgo real se concentra en {sym}.",
            f"Tu dinero está repartido, pero el riesgo no: lo aporta principalmente {sym}.",
        ], [
            "No es un error: la parte de mayor crecimiento siempre domina los altibajos, y el resto está ahí para amortiguar.",
            "Es el diseño esperado de una cartera equilibrada — lo defensivo estabiliza, no manda.",
            "Así funciona: unas piezas empujan el rendimiento y otras suavizan el camino.",
        ], [
            "Súbela o bájala según cuánto vaivén quieras, sabiendo que ahí está la palanca de tu resultado.",
            "Si quieres más calma, el ajuste no es añadir nombres: es darle algo menos de peso.",
            "Tenerlo claro te evita sorpresas: cuando el portafolio se mueva, sabrás exactamente por qué.",
        ])
    # Caso 1: el riesgo lo manda una sola posición (aunque haya varias)
    elif rc >= 0.45:
        pools = ([
            f"Tu riesgo no está donde parece: aunque repartiste en {n} activos, el resultado lo decide {sym}.",
            f"El portafolio aparenta estar repartido, pero en la práctica es una apuesta a {sym} con acompañantes.",
            f"Hay más nombres que ideas: {sym} domina el comportamiento del conjunto.",
        ], [
            "Los demás activos apenas mueven la aguja, así que su diversificación es más nominal que real.",
            "El resto amortigua poco: cuando esa posición se mueve, el portafolio la sigue.",
            "Eso concentra tu suerte en una sola historia, no en una cartera.",
        ], [
            "Bajarla de tamaño cambiaría tu experiencia mucho más que añadir otro activo parecido.",
            "Si crees en ella, mantenla consciente; si no, reducirla es el ajuste de mayor efecto.",
            "La pregunta útil: ¿aguantarías el plan si justo esa posición se estanca cinco años?",
        ])
    # Caso 2: muchos nombres, mismo motor (correlación alta)
    elif corr >= 0.65:
        pools = ([
            "Tienes varios nombres, pero un solo motor: casi todo reacciona al mismo escenario.",
            "Diversificaste en apariencia, no en comportamiento: tus activos comparten destino.",
            "El conjunto se mueve casi como una sola pieza ante las mismas noticias.",
        ], [
            f"Por eso tus {n} posiciones rinden como unas {bets:.0f} apuestas reales frente a un mal año.",
            "Cuando llega un mal año, no hay nada que sostenga al resto.",
            "Añadir otro activo del mismo tipo no cambiaría este diagnóstico.",
        ], [
            "Lo que sí lo cambia: incorporar algo que gane cuando lo tuyo pierde (bonos, oro, otras regiones).",
            "La mejora está en cambiar de motor, no en sumar más nombres.",
            "Diversificar de verdad es combinar reacciones distintas, no logotipos distintos.",
        ])
    # Caso 3: sobre-diversificado
    elif n >= 12 and mw < 0.08:
        pools = ([
            "Estás tan repartido que el conjunto ya se comporta como el mercado.",
            "A este nivel de reparto, tus mejores ideas dejan de notarse en el resultado.",
            "El portafolio alcanzó el punto donde diversificar deja de proteger y empieza a diluir.",
        ], [
            "Eso reduce sustos, pero también recorta el premio de acertar.",
            "Ganas estabilidad a cambio de parecerte cada vez más al índice.",
            "Con tantas posiciones, seguirlas bien cuesta más de lo que aportan.",
        ], [
            "Si el objetivo es el mercado, un índice barato lo consigue con menos trabajo.",
            "Si buscas superarlo, tus convicciones necesitan peso suficiente para notarse.",
            "Simplificar aquí no es renunciar: es dejar que lo que sí te convence pese.",
        ])
    # Caso 4: estructura sana
    else:
        pools = ([
            "La estructura está haciendo su trabajo: ninguna pieza decide sola el resultado.",
            "Aquí no hay un punto único de falla, que es lo difícil de conseguir.",
            "El conjunto está equilibrado: el resultado lo decide la cartera, no una apuesta.",
        ], [
            "Cuando una parte sufre, el resto tiende a sostener el camino.",
            "Eso hace el trayecto más llevadero sin renunciar a crecer.",
            "Es la clase de reparto que se aguanta emocionalmente en un mal año.",
        ], [
            "Con esta base, lo que más moverá tu resultado ya no es la mezcla: es cuánto aportas y cuánto tiempo la sostienes.",
            "Tu siguiente palanca no está aquí, sino en el hábito de aportar y no interrumpir.",
            "Mantenerla así, y revisarla una vez al año, suele valer más que cualquier ajuste fino.",
        ])
    return _compose(rng, *pools)


def interpret_benchmark(result: dict, inputs: dict, bench: dict, prob_beat: float | None) -> str:
    """VEREDICTO frente al índice: si el riesgo extra está pagado y qué lo justificaría.

    No repite medianas ni porcentajes: eso ya está en las tarjetas y en la gráfica.
    """
    import numpy as np

    med = float(np.median(result["final_values"]))
    bmed = float(np.median(bench["result"]["final_values"]))
    dd = result.get("max_drawdown_typical", 0.0)
    bdd = bench["result"].get("max_drawdown_typical", 0.0)
    gana = med >= bmed
    mas_riesgo = dd > bdd * 1.08
    rng = _seeded(inputs, "benchV2")

    if gana and not mas_riesgo:
        pools = ([
            "Este es el caso poco común: le ganas al índice sin pagarlo con un camino más duro.",
            "Tu mezcla mejora al índice y además lo hace por la vía tranquila.",
            "Aquí hay valor real: más resultado esperado sin más sobresaltos.",
        ], [
            "Cuando eso ocurre, suele venir de combinar bien piezas distintas, no de acertar con una.",
            "Ese equilibrio es difícil de sostener por casualidad: normalmente viene de la estructura.",
            "Es la señal de una cartera pensada, no de una apuesta afortunada.",
        ], [
            "Lo sensato ahora es no tocarla de más: el mayor riesgo pasa a ser tu propia impaciencia.",
            "Mantén el rumbo y revísala una vez al año; lo demás es ruido.",
            "Consérvala simple: lo que ya funciona rara vez necesita más movimientos.",
        ])
    elif gana and mas_riesgo:
        pools = ([
            "Le ganas al índice, pero el premio viene con factura: tu camino es más brusco.",
            "Sí, superas al índice — a cambio de aceptar un viaje bastante más movido.",
            "Hay ventaja, aunque no es gratis: la pagas en sobresaltos.",
        ], [
            "La pregunta no es si el número es mayor, sino si sostendrías el plan durante la peor parte.",
            "Ese extra solo se cobra si sigues dentro cuando el camino se pone feo.",
            "Muchos abandonan justo antes de recoger esa diferencia.",
        ], [
            "Si dudas de tu aguante, moderar la parte más volátil suele conservar casi todo el resultado con menos ruido.",
            "Vale la pena si tu horizonte es largo y el dinero no se toca; si no, conviene suavizarla.",
            "Decide hoy, con calma, cuánta turbulencia estás dispuesto a firmar.",
        ])
    elif not gana and mas_riesgo:
        pools = ([
            "Aquí hay un problema de eficiencia: asumes más riesgo que el índice y aun así te quedas detrás.",
            "Estás pagando volatilidad sin que te la paguen de vuelta.",
            "El mercado te está ofreciendo más por menos esfuerzo que tu mezcla actual.",
        ], [
            "Eso suele indicar posiciones que suman riesgo sin aportar rendimiento distinto al del índice.",
            "Normalmente pasa cuando varias piezas repiten la misma apuesta con peor precio.",
            "Es el patrón típico de una cartera que creció por acumulación y no por diseño.",
        ], [
            "O hay una tesis clara detrás de esas posiciones, o simplificar hacia el índice mejoraría el trato.",
            "Si no puedes explicar por qué cada pieza está ahí, el índice es el rival difícil de justificar.",
            "Revisar lo que aporta cada activo es aquí más rentable que buscar el próximo.",
        ])
    else:
        pools = ([
            "Te quedas algo por detrás del índice, pero a cambio de un camino más tranquilo.",
            "El índice proyecta más; tu mezcla ofrece menos sobresaltos.",
            "No ganas la carrera, y aun así el intercambio puede convenirte.",
        ], [
            "Ese cambio es razonable si tu prioridad es dormir tranquilo o el horizonte no es tan largo.",
            "Menos vaivén también es rendimiento: evita las decisiones impulsivas que destruyen resultados.",
            "Un plan que se sostiene rinde más que uno óptimo que abandonas a mitad.",
        ], [
            "Solo asegúrate de que la diferencia sea una decisión consciente y no una consecuencia del azar.",
            "Si el objetivo era acompañar al mercado, revisa si tanta prudencia te está costando de más.",
            "Con horizonte largo, acercarte un poco al índice recuperaría parte de esa distancia.",
        ])
    return _compose(rng, *pools)


def pdf_conclusion(result: dict, inputs: dict, benchmarks: list | None = None) -> str:
    """Conclusión del PDF: variantes combinables con los datos reales del análisis."""
    import numpy as np

    years = inputs["horizon_years"]
    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    dd = result.get("max_drawdown_typical", 0.0)
    analysis = result.get("analysis") or {}
    s, o = analysis.get("structure", {}), analysis.get("outcomes", {})
    rng = _seeded(inputs, "pdfconc")

    open_p = [
        f"Después de simular 10.000 futuros posibles, el mensaje central es este: a {years} años tu plan apunta a {_money(p50)} en el escenario típico, con un rango razonable entre {_money(p5)} y {_money(p95)}.",
        f"Si hubiera que resumir todo el análisis en una frase: lo más probable es terminar cerca de {_money(p50)} a {years} años, sabiendo que el abanico realista va de {_money(p5)} a {_money(p95)}.",
        f"El veredicto de los 10.000 escenarios es claro: tu punto central a {years} años es {_money(p50)}, y planificar con el rango que va de {_money(p5)} a {_money(p95)} es más honesto que aferrarse a un solo número.",
    ]
    risk_p = [
        f"El precio del boleto será la volatilidad: en algún momento verás la cuenta caer alrededor de {dd*100:.0f}% desde su máximo, y ese día tu mejor herramienta no será el análisis sino la calma.",
        f"Prepárate para el peaje del camino: caídas típicas de alrededor de un {dd*100:.0f}% son parte del plan, no una falla del plan — quien lo sabe de antemano no vende en el peor momento.",
        f"Habrá baches cercanos al {dd*100:.0f}% en el trayecto; la diferencia entre un buen y un mal resultado casi nunca está en elegir mejor, sino en no abandonar en mitad de la tormenta.",
    ]
    if o.get("median_real"):
        real_p = [
            f"En poder de compra de hoy, esa mediana equivale a cerca de {_money(o['median_real'])}: el número que de verdad importa cuando pienses en qué podrás hacer con el dinero.",
            f"Ajustado por inflación, hablamos de alrededor de {_money(o['median_real'])} en dinero de hoy — la medida honesta de tu meta.",
        ]
    else:
        real_p = []
    if s.get("wavg_corr") is not None and s.get("n_assets", 1) >= 2:
        struct_p = [
            f"Estructuralmente, tus {s['n_assets']} activos equivalen a unas {s.get('eff_bets', 0):.1f} apuestas independientes (correlación media {s['wavg_corr']:.2f}); ahí está la palanca más barata para mejorar el plan.",
            f"La estructura cuenta su propia historia: correlación media de {s['wavg_corr']:.2f} y {s.get('max_weight', 0)*100:.0f}% en tu mayor posición — vigilar esos dos números vale más que perseguir el próximo activo de moda.",
        ]
    else:
        struct_p = []
    if benchmarks:
        try:
            bmed = float(np.median(benchmarks[0]["result"]["final_values"]))
            # "en línea" cuando la diferencia es <1%: una cartera 100% SPY contra el
            # propio S&P daba "por encima" siendo idénticas.
            vs = ("prácticamente en línea" if abs(p50 - bmed) <= 0.01 * max(bmed, 1.0)
                  else "por encima" if p50 > bmed else "por debajo")
            bench_p = [
                f"Frente al S&P 500 ({_money(bmed)} de mediana), tu mezcla proyecta {vs} del índice: úsalo como brújula periódica, no como examen diario.",
                f"La vara del S&P 500 quedó en {_money(bmed)}; tu plan proyecta {vs}. Revisar esa distancia una vez al año es suficiente.",
            ]
        except Exception:
            bench_p = []
    else:
        bench_p = []
    close_p = [
        "Este documento no predice el futuro: te muestra su forma probable para que tus decisiones — aportar constante, no vender en pánico, revisar una vez al año — se tomen con la cabeza fría.",
        "Nada aquí es recomendación de compra o venta; es un mapa de probabilidades para que el plan dependa de tu disciplina y no de tu estado de ánimo.",
        "Tómalo como un mapa, no como una promesa: la ruta se recorre aportando con constancia y dejando que el interés compuesto haga su parte.",
    ]
    return _compose(rng, open_p, risk_p, real_p, struct_p, bench_p, close_p)


def interpret_stress(stress: dict, result: dict, inputs: dict) -> str:
    """HALLAZGO del estrés: qué revela la sensibilidad al mercado y qué decisión implica.

    Los porcentajes de cada crisis ya están sobre las barras: aquí no se repiten.
    """
    evs = stress.get("events") or []
    if not evs:
        return "No hay eventos de estrés disponibles para este portafolio."
    beta = stress.get("beta", 1.0)
    years = inputs.get("horizon_years", 20)
    retirement = inputs.get("monthly_contribution", 0.0) < 0
    rng = _seeded(inputs, "stressV2")

    if beta >= 1.15:
        pools = ([
            "Tu portafolio no solo acompaña al mercado: lo exagera.",
            "En las crisis, esta mezcla amplifica lo que hace el mercado en vez de amortiguarlo.",
            "Frente a un desplome, tu cartera tiende a caer más que el índice, no menos.",
        ], [
            "En las subidas eso juega a favor; en las caídas convierte un mal año en uno muy difícil de aguantar.",
            "Es el mismo rasgo que te da los buenos años: no puedes quedarte solo con una cara de la moneda.",
            "Ese exceso de sensibilidad es justo lo que hace que la gente venda en el peor momento.",
        ], [])
    elif beta <= 0.85:
        pools = ([
            "La lectura importante es defensiva: tu mezcla amortigua los golpes del mercado.",
            "Esta cartera está construida para sufrir menos que el índice cuando todo cae.",
            "Ante una crisis, tu portafolio tiende a resistir mejor que el mercado.",
        ], [
            "Ese colchón tiene un costo: también recorta parte de las subidas fuertes.",
            "A cambio, en los grandes rebotes te quedarás algo atrás — es el precio de la calma.",
            "Es un intercambio deliberado: menos dolor abajo, menos euforia arriba.",
        ], [])
    else:
        pools = ([
            "Tu cartera se comporta prácticamente como el mercado en una crisis.",
            "En un desplome, tu experiencia sería muy parecida a la del índice.",
            "No hay ni amplificación ni colchón: sigues al mercado de cerca.",
        ], [
            "Eso significa que tu resultado en los años malos dependerá del mercado, no de tu selección.",
            "Ni te protege de más ni te expone de más: el ciclo manda.",
            "La selección de activos aquí no cambia tu suerte en las caídas.",
        ], [])

    if retirement:
        close = [
            "Y como estás retirando, ese tramo pesa el doble: vender en plena caída consolida el daño para siempre.",
            "Retirando dinero, una crisis temprana es el escenario más peligroso de todos: conviene tener un colchón en algo estable.",
            "En retiro, lo relevante no es la caída sino de dónde sacas el dinero mientras dura.",
        ]
    elif years >= 15:
        close = [
            f"Con {years} años por delante hay tiempo de sobra para recuperarse: el peligro real no es la caída, es abandonar durante ella.",
            "A tu horizonte, estos episodios son baches, no finales: lo único que los vuelve permanentes es vender.",
            "El tiempo juega a tu favor; decide hoy que no venderás, y el resto se resuelve solo.",
        ]
    else:
        close = [
            f"Con solo {years} años de horizonte hay menos margen para recuperar: si el dinero se necesita pronto, conviene moderar la exposición.",
            "Tu horizonte es corto para este nivel de exposición: una crisis tardía podría no dar tiempo a rebotar.",
            "Cuanto más cerca esté la meta, menos sentido tiene aguantar esta sensibilidad.",
        ]
    return _compose(rng, *pools, close)
