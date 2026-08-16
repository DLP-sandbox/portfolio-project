"""Generador del PDF (2 páginas, landscape 1920x1080 pt): Resumen + Análisis detallado.

Todo en español natural para principiantes (sin tecnicismos). Incluye una conclusión
automática generada por reglas locales (core.interpret) — SIN ninguna API de IA.
reportlab + kaleido (scale=1). Cero emojis: usamos formas dibujadas con reportlab.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core import interpret
from core import statistics as st_metrics
from dashboard import charts
from dashboard import styles as S

PAGE_W, PAGE_H = 1920.0, 1080.0
MARGIN = 60.0

C_BG = HexColor(S.BG_DEEP)
C_CARD = HexColor(S.BG_CARD)
C_CARD2 = HexColor(S.BG_CARD2)
C_BORDER = HexColor(S.BORDER)
C_ORANGE = HexColor(S.ORANGE)
C_GREEN = HexColor(S.GREEN)
C_RED = HexColor(S.RED)
C_BLUE = HexColor(S.BLUE)
C_GOLD = HexColor(S.GOLD)
C_HI = HexColor(S.TEXT_HI)
C_MD = HexColor(S.TEXT_MD)
C_LO = HexColor(S.TEXT_LO)
C_DIM = HexColor(S.TEXT_DIM)

DISCLAIMER = (
    "Esta proyección NO es predicción ni recomendación de inversión. Muestra escenarios "
    "estadísticos basados en cómo se comportó el mercado en el pasado. El comportamiento real "
    "puede diferir mucho. Consulta a un asesor financiero antes de tomar decisiones."
)


# ── Fuentes ──────────────────────────────────────────────────────────────────
def register_fonts() -> dict:
    """Helvetica Neue (macOS) → Inter (assets) → Helvetica built-in."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    sys_ttc = Path("/System/Library/Fonts/HelveticaNeue.ttc")
    if sys_ttc.exists():
        ok = True
        for idx, name in [(0, "HelveticaNeue"), (1, "HelveticaNeue-Bold"), (10, "HelveticaNeue-Medium")]:
            try:
                pdfmetrics.registerFont(TTFont(name, str(sys_ttc), subfontIndex=idx))
            except Exception:
                ok = False
        if ok:
            return {"regular": "HelveticaNeue", "bold": "HelveticaNeue-Bold", "medium": "HelveticaNeue-Medium"}
    inter = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Regular.ttf"
    if inter.exists():
        try:
            pdfmetrics.registerFont(TTFont("Inter", str(inter)))
            return {"regular": "Inter", "bold": "Inter", "medium": "Inter"}
        except Exception:
            pass
    return {"regular": "Helvetica", "bold": "Helvetica-Bold", "medium": "Helvetica"}


def _ensure_kaleido_launcher() -> None:
    """Patch del launcher de kaleido 0.2.1 (quotea `cd $DIR`) para rutas con espacios."""
    try:
        import kaleido

        launcher = Path(kaleido.__file__).parent / "executable" / "kaleido"
        if launcher.exists():
            txt = launcher.read_text()
            if "cd $DIR" in txt or "./bin/kaleido $@" in txt:
                txt = txt.replace("cd $DIR", 'cd "$DIR"').replace("./bin/kaleido $@", './bin/kaleido "$@"')
                launcher.write_text(txt)
    except Exception:
        pass


# ── Primitivas ───────────────────────────────────────────────────────────────
def _y(top: float) -> float:
    return PAGE_H - top


def _card(c, x, top, w, h, fill=C_CARD, border=C_BORDER, left_accent=None, radius=14,
          shadow: bool = True):
    y = _y(top + h)
    if shadow:   # sombra suave de una sola luz cenital (misma idea que en la app)
        c.setFillColor(HexColor("#07080A"))
        c.roundRect(x + 2, y - 3, w, h, radius, stroke=0, fill=1)
    c.setFillColor(fill)
    if border is not None:
        c.setStrokeColor(border)
        c.setLineWidth(1)
        c.roundRect(x, y, w, h, radius, stroke=1, fill=1)
    else:
        c.roundRect(x, y, w, h, radius, stroke=0, fill=1)
    if left_accent is not None:
        c.setFillColor(left_accent)
        c.rect(x, y, 6, h, stroke=0, fill=1)


def _text(c, x, top, s, font, size, color, center=False, right=False):
    c.setFont(font, size)
    c.setFillColor(color)
    if center:
        c.drawCentredString(x, _y(top + size), s)
    elif right:
        c.drawRightString(x, _y(top + size), s)
    else:
        c.drawString(x, _y(top + size), s)


def _paragraph(c, x, top, w, text, font, size, color, leading=None) -> float:
    """Texto con wrap automático. Devuelve el 'top' debajo del último renglón."""
    leading = leading or size + 6
    c.setFont(font, size)
    c.setFillColor(color)
    line, yy = "", top
    for wd in text.split():
        test = (line + " " + wd).strip()
        if c.stringWidth(test, font, size) > w and line:
            c.drawString(x, _y(yy + size), line)
            line, yy = wd, yy + leading
        else:
            line = test
    if line:
        c.drawString(x, _y(yy + size), line)
        yy += leading
    return yy


def _plain(text: str) -> str:
    return text.replace("**", "").replace("_", "")


def _kpi(c, fonts, x, top, w, h, label, value, color, sub):
    _card(c, x, top, w, h)
    c.setFillColor(color)
    c.rect(x, _y(top) - 6, w, 6, stroke=0, fill=1)
    _text(c, x + 20, top + 22, label.upper(), fonts["medium"], 15, C_LO)
    _text(c, x + 20, top + 48, value, fonts["bold"], 40, color)
    _paragraph(c, x + 20, top + 98, w - 40, sub, fonts["regular"], 13, C_LO, leading=16)


def _disclaimer(c, fonts, top):
    x, w, h = MARGIN, PAGE_W - 2 * MARGIN, 80
    _card(c, x, top, w, h, fill=HexColor("#1A0E12"), border=C_RED, left_accent=C_RED)
    _text(c, x + 22, top + 14, "PROYECCION PROBABILISTICA — NO ES CERTEZA", fonts["bold"], 14, C_RED)
    _paragraph(c, x + 22, top + 38, w - 44, DISCLAIMER, fonts["regular"], 13.5, C_MD, leading=18)


def prewarm() -> None:
    """Arranca kaleido en segundo plano al levantar el servidor.

    La PRIMERA imagen que renderiza kaleido cuesta ~6s (levanta su navegador); las
    siguientes, 0,23s. Como el servicio ya no se duerme, ese arranque se paga una sola
    vez en la vida del proceso: haciéndolo aquí, ningún usuario lo sufre. Silencioso y
    tolerante a fallos — si algo va mal, el primer PDF simplemente tarda como antes.
    """
    try:
        import plotly.graph_objects as go

        _ensure_kaleido_launcher()
        go.Figure().write_image(_tempfile_png(), width=8, height=8, scale=1)
    except Exception:
        pass


def _tempfile_png() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.close()
    return f.name


def _chart_png(fig, w_px, h_px) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.close()
    fig.write_image(f.name, width=w_px, height=h_px, scale=1)
    return f.name


def _fmt_money(x):
    return f"${x:,.0f}"


def _page_header(c, fonts, title, subtitle):
    c.setFillColor(C_ORANGE)
    c.rect(MARGIN, _y(MARGIN + 44), 8, 44, stroke=0, fill=1)
    _text(c, MARGIN + 24, MARGIN, title, fonts["bold"], 34, C_HI)
    _text(c, MARGIN + 24, MARGIN + 46, subtitle, fonts["regular"], 16, C_LO)


# ── Página 1 — Resumen ───────────────────────────────────────────────────────
def _page1(c, fonts, result, inputs):
    import numpy as np
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    _page_header(c, fonts, "Analista de Portafolios",
                 "Probamos 10.000 futuros posibles de tu inversión — esto es un rango de escenarios, no una predicción")

    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    years = inputs["horizon_years"]
    retiro = inputs["monthly_contribution"] < 0

    # Hero
    _card(c, MARGIN, 148, PAGE_W - 2 * MARGIN, 92, fill=C_CARD, border=C_ORANGE)
    metas = [("Capital inicial", _fmt_money(inputs["initial_capital"])),
             ("Retiro mensual" if retiro else "Aporte mensual", _fmt_money(abs(inputs["monthly_contribution"]))),
             ("Horizonte", f"{years} años"),
             ("Tu portafolio", ", ".join(inputs["tickers"])[:44])]
    mx = MARGIN + 28
    for lbl, val in metas:
        _text(c, mx, 164, lbl.upper(), fonts["medium"], 12, C_LO)
        _text(c, mx, 186, val, fonts["bold"], 21, C_HI)
        mx += 350
    _text(c, PAGE_W - MARGIN - 28, 158, f"LO MAS PROBABLE A {years} AÑOS", fonts["medium"], 13, C_LO, right=True)
    _text(c, PAGE_W - MARGIN - 28, 180, _fmt_money(p50), fonts["bold"], 38, C_ORANGE, right=True)

    # Izquierda: abanico + subtítulo simple + 3 tarjetas
    fan = _chart_png(charts.fan_chart(result["percentiles"], result["months"], inputs["target"]), 1120, 380)
    c.drawImage(ImageReader(fan), MARGIN, _y(640), 1120, 380, mask="auto")
    _text(c, MARGIN, 262, "TUS 10.000 FUTUROS POSIBLES", fonts["medium"], 14, C_HI)
    _paragraph(c, MARGIN, 648, 1120,
               "Cada línea clara es uno de los 10.000 futuros posibles de tu inversión. La franja "
               "naranja marca el rango más probable; la línea del centro es el resultado típico. "
               "Abajo: los años. A la izquierda: cuánto dinero tendrías.",
               fonts["regular"], 13, C_LO, leading=18)

    kw = (1120 - 2 * 20) / 3
    _kpi(c, fonts, MARGIN, 720, kw, 150, "Si va mal", _fmt_money(p5), C_RED, "Solo 1 de cada 20 futuros terminó peor que esto")
    _kpi(c, fonts, MARGIN + kw + 20, 720, kw, 150, "Lo más probable", _fmt_money(p50), C_ORANGE, "El escenario del medio: la mitad termina arriba y la mitad abajo")
    _kpi(c, fonts, MARGIN + 2 * (kw + 20), 720, kw, 150, "Si va bien", _fmt_money(p95), C_GREEN, "Solo 1 de cada 20 futuros terminó mejor que esto")

    # Derecha: histograma + (medidor de meta o tarjeta) con subtítulos simples
    rx, rw = MARGIN + 1150, PAGE_W - MARGIN - (MARGIN + 1150)
    hist = _chart_png(charts.histogram_final(fv, plain_labels=True), int(rw), 250)
    c.drawImage(ImageReader(hist), rx, _y(540), rw, 250, mask="auto")
    _text(c, rx, 262, "EN CUÁNTOS FUTUROS TERMINASTE CON CADA MONTO", fonts["medium"], 13, C_HI)
    _paragraph(c, rx, 544, rw,
               "La mayoría de los futuros caen en el centro; los extremos (muy malos o muy buenos) "
               "son poco frecuentes.", fonts["regular"], 13, C_LO, leading=18)

    if inputs.get("target") and not retiro:
        g = _chart_png(charts.success_gauge(result["prob_target"] or 0.0, ""), int(rw), 230)
        c.drawImage(ImageReader(g), rx, _y(870), rw, 230, mask="auto")
        _text(c, rx, 612, "PROBABILIDAD DE LLEGAR A TU META", fonts["medium"], 13, C_HI)
    else:
        total = inputs["initial_capital"] + max(inputs["monthly_contribution"], 0) * 12 * years
        _kpi(c, fonts, rx, 640, rw, 200, "Lo que pones de tu bolsillo", _fmt_money(total),
             C_GOLD, "Tu capital inicial más todos tus aportes, sin contar el rendimiento del mercado")

    _disclaimer(c, fonts, 984)
    c.showPage()


# ── Página 2 — Análisis detallado (visual + simple) ──────────────────────────
def _page2(c, fonts, result, inputs, benchmarks, conclusion):
    import numpy as np
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    _page_header(c, fonts, "Análisis detallado",
                 "Tu inversión explicada en simple — no necesitas saber nada de simulaciones para entenderla")

    # Intro: cómo leer esto
    _card(c, MARGIN, 150, PAGE_W - 2 * MARGIN, 86, left_accent=C_ORANGE)
    _text(c, MARGIN + 24, 162, "CÓMO LEER ESTO", fonts["medium"], 13, C_ORANGE)
    _paragraph(c, MARGIN + 24, 186, PAGE_W - 2 * MARGIN - 48,
               "Probamos 10.000 caminos posibles para tu dinero usando cómo se movió el mercado en el "
               "pasado. No es una predicción: es un abanico de escenarios para que planifiques pensando "
               "en un rango, no en un solo número.", fonts["regular"], 14, C_MD, leading=20)

    # Izquierda: tu dinero por año (tabla simple)
    years = [y for y in (5, 10, 15, 20) if y <= inputs["horizon_years"]] or [inputs["horizon_years"]]
    table = st_metrics.percentiles_at_years(result["percentiles"], years)
    lx, lw = MARGIN, 900
    _card(c, lx, 256, lw, 318)
    _text(c, lx + 24, 272, "TU DINERO A LO LARGO DEL TIEMPO", fonts["medium"], 15, C_HI)
    cols = ["Año", "Si va mal", "Lo más probable", "Si va bien"]
    colx = [lx + 30, lx + 240, lx + 470, lx + 720]
    for cx, name in zip(colx, cols):
        _text(c, cx, 312, name, fonts["bold"], 15, C_MD)
    row_top = 346
    for y in years:
        vals = table[y]
        _text(c, colx[0], row_top, f"{y} años", fonts["bold"], 15, C_ORANGE)
        for cx, key, col in zip(colx[1:], ["P5", "P50", "P95"], [C_RED, C_HI, C_GREEN]):
            _text(c, cx, row_top, _fmt_money(vals[key]), fonts["regular"], 15, col)
        row_top += 40
    _paragraph(c, lx + 24, row_top + 12, lw - 48,
               "‘Si va mal’ y ‘Si va bien’ son los casos extremos: solo 1 de cada 20 futuros queda por "
               "fuera de ese rango. ‘Lo más probable’ es el resultado del medio.",
               fonts["regular"], 12.5, C_LO, leading=17)

    # Derecha: riesgos en simple
    rx2, rw2 = lx + lw + 30, PAGE_W - MARGIN - (lx + lw + 30)
    _card(c, rx2, 256, rw2, 318)
    _text(c, rx2 + 24, 272, "QUÉ TAN RIESGOSO ES", fonts["medium"], 15, C_HI)
    dd = result["max_drawdown_typical"] * 100
    eff = result["expected_sharpe"]
    _text(c, rx2 + 24, 312, "Caída típica en un mal momento", fonts["bold"], 15, C_MD)
    _text(c, rx2 + 24, 334, f"{dd:.0f}%", fonts["bold"], 30, C_BLUE)
    _paragraph(c, rx2 + 24, 372, rw2 - 48,
               "Cuánto suele bajar tu inversión desde su punto más alto hasta el más bajo. Hay que "
               "aguantarlo sin vender en pánico.", fonts["regular"], 12.5, C_LO, leading=17)
    _text(c, rx2 + 24, 440, "Eficiencia (ganancia por el riesgo)", fonts["bold"], 15, C_MD)
    _text(c, rx2 + 24, 462, f"{eff:.2f}", fonts["bold"], 30, C_GOLD)
    _paragraph(c, rx2 + 24, 500, rw2 - 48,
               "Cuánto rinde tu portafolio en relación al riesgo que toma. Más alto es mejor.",
               fonts["regular"], 12.5, C_LO, leading=17)

    # Tu cartera frente a alternativas comunes
    _card(c, MARGIN, 594, PAGE_W - 2 * MARGIN, 120)
    _text(c, MARGIN + 24, 608, "TU PORTAFOLIO FRENTE A ALTERNATIVAS COMUNES", fonts["medium"], 14, C_HI)
    rows = [("Tu portafolio", result, C_ORANGE)] + [(b["label"], b["result"], C_BLUE) for b in (benchmarks or [])]
    bw = (PAGE_W - 2 * MARGIN - 48) / max(len(rows), 1)
    bx = MARGIN + 24
    for label, r, col in rows:
        med = float(np.percentile(r["final_values"], 50))
        _text(c, bx, 644, label, fonts["bold"], 15, col)
        _text(c, bx, 668, f"Lo más probable: {_fmt_money(med)}", fonts["regular"], 14, C_MD)
        bx += bw

    # Conclusión (generada por reglas locales, sin IA)
    _card(c, MARGIN, 734, PAGE_W - 2 * MARGIN, 230, left_accent=C_GREEN)
    _text(c, MARGIN + 24, 748, "CONCLUSIÓN", fonts["medium"], 14, C_GREEN)
    _paragraph(c, MARGIN + 24, 776, PAGE_W - 2 * MARGIN - 48, conclusion,
               fonts["regular"], 15, C_MD, leading=23)

    _disclaimer(c, fonts, 984)
    c.showPage()


# ── Página 3 — Composición, exposición y estrés ──────────────────────────────
def _page3(c, fonts, result, inputs, exposure, stress):
    """Composición + exposición + estrés, con hallazgos y lecturas (no solo gráficas).

    Presupuesto vertical (PAGE_H=1080): cabecera 150 · fila1 150-510 · fila2 534-684 ·
    fila3 708-998. Cada bloque cabe dentro de su tarjeta con holgura (sin solapes).
    """
    from dashboard import charts
    from core import interpret as _int

    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    _page_header(c, fonts, "Composición y riesgo",
                 "En qué está invertido tu dinero y cómo se comportaría en las peores crisis")

    items = [{"symbol": t, "weight": w * 100} for t, w in zip(inputs["tickers"], inputs["weights"])]
    GUT, PADX = 24, 28
    analysis = result.get("analysis") or {}

    # ── Fila 1: dona (izq) + exposición (der) ────────────────────────────────
    top1, h1, lw = 150, 360, 820
    _card(c, MARGIN, top1, lw, h1, left_accent=C_ORANGE)
    _text(c, MARGIN + PADX, top1 + 18, "TU PORTAFOLIO, ACTIVO POR ACTIVO", fonts["medium"], 14, C_HI)
    try:
        donut = _chart_png(charts.allocation_donut(items, show_labels=True), 660, 262)
        c.drawImage(ImageReader(donut), MARGIN + (lw - 660) / 2, _y(top1 + h1 - 24), 660, 262, mask="auto")
    except Exception:
        _text(c, MARGIN + PADX, top1 + 150, "(composición no disponible)", fonts["regular"], 13, C_LO)

    rx = MARGIN + lw + GUT
    rw = PAGE_W - MARGIN - rx
    _card(c, rx, top1, rw, h1)
    _text(c, rx + PADX, top1 + 18, "EXPOSICIÓN POR SECTOR", fonts["medium"], 14, C_HI)
    top = top1 + 52
    try:
        from data.sectors import top_sectors as _tops
        _secrows = _tops((exposure or {}).get("by_sector", []), 5)
    except Exception:
        _secrows = (exposure or {}).get("by_sector", [])[:5]
    for row in _secrows:
        _text(c, rx + PADX, top, row["name"][:22], fonts["regular"], 13, C_MD)
        _text(c, rx + rw - PADX, top, f"{row['pct']:.0f}%", fonts["bold"], 13, C_ORANGE, right=True)
        bw = (rw - 2 * PADX) * min(row["pct"], 100) / 100.0
        c.setFillColor(C_ORANGE)
        c.roundRect(rx + PADX, _y(top + 29), max(bw, 2), 4.5, 2, stroke=0, fill=1)
        top += 40
    # La tarjeta acaba en top1+h1 (=510) y las 5 filas de sector dejan el cursor en 402.
    # Con 3 clases o menos cabe holgado con el espaciado de siempre; con 4 (habitual desde
    # que se admiten 20 activos) la última fila caía JUSTO sobre el borde, así que ahí se
    # aprieta. Si hubiera más de 4 clases se agrupa la cola en "Otros" —igual que en los
    # sectores— para no ocultar ninguna en silencio.
    _clsrows = list((exposure or {}).get("by_class", []))
    if len(_clsrows) > 4:
        _clsrows = _clsrows[:3] + [{"name": "Otros",
                                    "pct": sum(float(r["pct"]) for r in _clsrows[3:])}]
    _tight = len(_clsrows) >= 4
    _step = 21 if _tight else 24
    top += 6 if _tight else 12
    _text(c, rx + PADX, top, "POR TIPO DE ACTIVO", fonts["medium"], 12, C_LO)
    top += _step
    for row in _clsrows:
        _text(c, rx + PADX, top, row["name"][:20], fonts["regular"], 12.5, C_MD)
        _text(c, rx + rw - PADX, top, f"{row['pct']:.0f}%", fonts["bold"], 12.5, C_HI, right=True)
        top += _step

    # ── Fila 2: lectura de la estructura + hallazgos clave ───────────────────
    top2, h2 = top1 + h1 + GUT, 150
    _card(c, MARGIN, top2, lw, h2, left_accent=C_GOLD)
    _text(c, MARGIN + PADX, top2 + 16, "LECTURA DE TU ESTRUCTURA", fonts["medium"], 13.5, C_HI)
    try:
        txt = _plain(_int.interpret_diversification(analysis.get("structure", {})))
    except Exception:
        txt = ""
    _paragraph(c, MARGIN + PADX, top2 + 46, lw - 2 * PADX, txt, fonts["regular"], 13, C_MD, leading=20)

    _card(c, rx, top2, rw, h2)
    _text(c, rx + PADX, top2 + 16, "HALLAZGOS CLAVE", fonts["medium"], 13.5, C_HI)
    yy = top2 + 48
    for fd in (analysis.get("findings") or [])[:3]:
        col = C_RED if fd.get("sentiment") == "alerta" else (
            C_GREEN if fd.get("sentiment") == "positivo" else C_BLUE)
        c.setFillColor(col)
        c.circle(rx + PADX + 4, _y(yy + 5), 3.5, stroke=0, fill=1)
        _text(c, rx + PADX + 16, yy - 3, _plain(fd.get("title", ""))[:42], fonts["bold"], 12, C_MD)
        yy += 28

    # ── Fila 3: estrés (gráfica + % + lectura) ───────────────────────────────
    top3, h3 = top2 + h2 + GUT, 290
    _card(c, MARGIN, top3, PAGE_W - 2 * MARGIN, h3, left_accent=C_RED)
    _text(c, MARGIN + PADX, top3 + 16, "CUÁNTO HABRÍA CAÍDO EN UN MAL MOMENTO", fonts["medium"], 13.5, C_HI)
    if stress and stress.get("events"):
        img_w = PAGE_W - 2 * MARGIN - 2 * PADX
        try:
            png = _chart_png(charts.stress_drop_bars(stress), int(img_w), 155)
            c.drawImage(ImageReader(png), MARGIN + PADX, _y(top3 + 46 + 155), img_w, 155, mask="auto")
        except Exception:
            pass
        plot_x0, plot_w = MARGIN + PADX + 10, img_w - 20
        step = plot_w / max(len(stress["events"]), 1)
        for i, ev in enumerate(stress["events"]):
            cx = plot_x0 + step * (i + 0.5)
            _text(c, cx, top3 + 210, f"−{ev['portfolio_drawdown']*100:.0f}%", fonts["bold"], 16, C_RED, center=True)
        try:
            lect = _plain(_int.interpret_stress(stress, result, inputs))
        except Exception:
            lect = ""
        _paragraph(c, MARGIN + PADX, top3 + 240, PAGE_W - 2 * MARGIN - 2 * PADX, lect,
                   fonts["regular"], 12.5, C_MD, leading=19)
    c.showPage()


# ── API pública ──────────────────────────────────────────────────────────────
def generate_report(result: dict, inputs: dict, benchmarks: list[dict] | None = None) -> bytes:
    """Genera el PDF de 2 páginas (Resumen + Análisis detallado) y devuelve sus bytes."""
    import io

    _ensure_kaleido_launcher()
    fonts = register_fonts()

    # Conclusión con variantes combinables (compositor por reglas, sembrado estable):
    # usa los datos reales del análisis y suena a redacción natural, sin ninguna API.
    conclusion = _plain(interpret.pdf_conclusion(result, inputs, benchmarks))

    # Exposición y estrés para la página 3 (ambos tolerantes a fallo)
    try:
        from data import sectors as _sect
        exposure = _sect.portfolio_exposure(
            [{"symbol": t, "weight": w} for t, w in zip(inputs["tickers"], inputs["weights"])])
    except Exception:
        exposure = None
    try:
        from core import stress as _stress
        import numpy as _np
        stress = _stress.compute_stress(inputs["tickers"], inputs["weights"],
                                        float(_np.percentile(result["final_values"], 50)),
                                        inputs.get("historical_window_years", 10))
    except Exception:
        stress = None

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("Analista de Portafolios")
    _page1(c, fonts, result, inputs)
    _page3(c, fonts, result, inputs, exposure, stress)
    _page2(c, fonts, result, inputs, benchmarks or [], conclusion)
    c.save()
    return buf.getvalue()
