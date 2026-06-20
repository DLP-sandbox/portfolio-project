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


def _card(c, x, top, w, h, fill=C_CARD, border=C_BORDER, left_accent=None, radius=14):
    y = _y(top + h)
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
    _page_header(c, fonts, "Proyección de Portafolio",
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


# ── API pública ──────────────────────────────────────────────────────────────
def generate_report(result: dict, inputs: dict, benchmarks: list[dict] | None = None) -> bytes:
    """Genera el PDF de 2 páginas (Resumen + Análisis detallado) y devuelve sus bytes."""
    import io

    _ensure_kaleido_launcher()
    fonts = register_fonts()

    # Conclusión por reglas locales (sin API). Quitamos el recordatorio final (ya hay disclaimer).
    raw = interpret.interpret_locally(result, inputs)
    paras = [p.strip() for p in raw.split("\n\n")
             if "no es predicción" not in p.lower() and "no es recomendación" not in p.lower()]
    conclusion = _plain(" ".join(paras))

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("Proyección de Portafolio")
    _page1(c, fonts, result, inputs)
    _page2(c, fonts, result, inputs, benchmarks or [], conclusion)
    c.save()
    return buf.getvalue()
