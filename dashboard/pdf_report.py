"""Generador de PDF ejecutivo (3 páginas, landscape 1920x1080 pt).

Fase 2: dashboard + análisis detallado + CTA básica (sin el pulido lead-magnet de
Fase 3: logo con glow halo, QR clickeable). reportlab + kaleido (scale=1, nunca 2).

Reglas: cero emojis (Helvetica no los renderiza) — usamos formas dibujadas con reportlab
en vez de glyphs exóticos para garantizar que no aparezcan cuadraditos de glyph faltante.
Cero llamadas a Anthropic — solo datos locales/Supabase.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from core import statistics as st_metrics
from dashboard import charts
from dashboard import styles as S

PAGE_W, PAGE_H = 1920.0, 1080.0
MARGIN = 60.0

# Paleta → reportlab
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
    "Esta proyección NO es predicción ni recomendación de inversión. Proyecta escenarios "
    "estadísticos basados en retornos históricos. El comportamiento real del mercado puede "
    "diferir significativamente. Consulta a un asesor financiero antes de tomar decisiones."
)


# ── Fuentes ──────────────────────────────────────────────────────────────────
def register_fonts() -> dict:
    """Registra Helvetica Neue (macOS) → Inter (assets) → Helvetica built-in.

    Returns {"regular","bold","medium"} con nombres de fuente usables en el PDF.
    """
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
            return {"regular": "HelveticaNeue", "bold": "HelveticaNeue-Bold",
                    "medium": "HelveticaNeue-Medium"}

    inter = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "Inter-Regular.ttf"
    if inter.exists():
        try:
            pdfmetrics.registerFont(TTFont("Inter", str(inter)))
            return {"regular": "Inter", "bold": "Inter", "medium": "Inter"}
        except Exception:
            pass

    return {"regular": "Helvetica", "bold": "Helvetica-Bold", "medium": "Helvetica"}


def _ensure_kaleido_launcher() -> None:
    """Patch best-effort del launcher de kaleido 0.2.1 (quotea `cd $DIR`) para que el
    export funcione aunque la ruta del proyecto tenga espacios."""
    try:
        import kaleido

        launcher = Path(kaleido.__file__).parent / "executable" / "kaleido"
        if launcher.exists():
            txt = launcher.read_text()
            if "cd $DIR" in txt or "./bin/kaleido $@" in txt:
                txt = txt.replace("cd $DIR", 'cd "$DIR"').replace(
                    "./bin/kaleido $@", './bin/kaleido "$@"')
                launcher.write_text(txt)
    except Exception:
        pass


# ── Primitivas de dibujo ─────────────────────────────────────────────────────
def _y(top: float) -> float:
    """Convierte coordenada desde-arriba a coordenada reportlab (desde-abajo)."""
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


def _kpi(c, fonts, x, top, w, h, label, value, color, sub):
    _card(c, x, top, w, h)
    c.setFillColor(color)
    c.rect(x, _y(top) - 6, w, 6, stroke=0, fill=1)  # accent strip arriba
    _text(c, x + 22, top + 26, label.upper(), fonts["medium"], 17, C_LO)
    _text(c, x + 22, top + 56, value, fonts["bold"], 44, color)
    _text(c, x + 22, top + h - 26, sub, fonts["regular"], 15, C_LO)


def _disclaimer(c, fonts, top):
    x, w, h = MARGIN, PAGE_W - 2 * MARGIN, 84
    _card(c, x, top, w, h, fill=HexColor("#1A0E12"), border=C_RED, left_accent=C_RED)
    _text(c, x + 22, top + 16, "PROYECCION PROBABILISTICA — NO ES CERTEZA", fonts["bold"], 14, C_RED)
    # wrap simple del disclaimer
    c.setFont(fonts["regular"], 14)
    c.setFillColor(C_MD)
    words, line, yy = DISCLAIMER.split(), "", top + 40
    maxw = w - 44
    for wd in words:
        test = (line + " " + wd).strip()
        if c.stringWidth(test, fonts["regular"], 14) > maxw:
            c.drawString(x + 22, _y(yy + 14), line)
            line, yy = wd, yy + 20
        else:
            line = test
    if line:
        c.drawString(x + 22, _y(yy + 14), line)


def _chart_png(fig, w_px, h_px) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.close()
    fig.write_image(f.name, width=w_px, height=h_px, scale=1)  # scale=1 SIEMPRE
    return f.name


def _fmt_money(x):
    return f"${x:,.0f}"


# ── Páginas ──────────────────────────────────────────────────────────────────
def _page_header(c, fonts, title, subtitle):
    c.setFillColor(C_ORANGE)
    c.rect(MARGIN, _y(MARGIN + 44), 8, 44, stroke=0, fill=1)
    _text(c, MARGIN + 24, MARGIN, title, fonts["bold"], 34, C_HI)
    _text(c, MARGIN + 24, MARGIN + 44, subtitle, fonts["regular"], 16, C_LO)


def _page1(c, fonts, result, inputs):
    import numpy as np
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    _page_header(c, fonts, "DLP Backtester & Planner",
                 "Visualiza los 10.000 futuros posibles de tu portafolio — proyección probabilística")

    fv = result["final_values"]
    p5, p50, p95 = (float(np.percentile(fv, q)) for q in (5, 50, 95))
    years = inputs["horizon_years"]

    # Hero strip
    _card(c, MARGIN, 150, PAGE_W - 2 * MARGIN, 96, fill=C_CARD, border=C_ORANGE)
    metas = [("Capital inicial", _fmt_money(inputs["initial_capital"])),
             ("Aporte mensual", _fmt_money(inputs["monthly_contribution"])),
             ("Horizonte", f"{years} años"),
             ("Portafolio", ", ".join(inputs["tickers"])[:46])]
    mx = MARGIN + 28
    for lbl, val in metas:
        _text(c, mx, 168, lbl.upper(), fonts["medium"], 13, C_LO)
        _text(c, mx, 190, val, fonts["bold"], 22, C_HI)
        mx += 360
    _text(c, PAGE_W - MARGIN - 28, 162, f"MEDIANA A {years} AÑOS", fonts["medium"], 14, C_LO, right=True)
    _text(c, PAGE_W - MARGIN - 28, 184, _fmt_money(p50), fonts["bold"], 40, C_ORANGE, right=True)

    # Fan chart (grande, izquierda)
    fan = _chart_png(charts.fan_chart(result["percentiles"], result["months"], inputs["target"]), 1120, 520)
    c.drawImage(ImageReader(fan), MARGIN, _y(800), 1120, 520, mask="auto")

    # Derecha: histograma + (gauge o KPI)
    rx = MARGIN + 1150
    rw = PAGE_W - MARGIN - rx
    hist = _chart_png(charts.histogram_final(fv), int(rw), 250)
    c.drawImage(ImageReader(hist), rx, _y(540), rw, 250, mask="auto")
    if inputs.get("target"):
        g = _chart_png(charts.success_gauge(result["prob_target"] or 0.0,
                       f"Prob. meta {_fmt_money(inputs['target'])}"), int(rw), 250)
        c.drawImage(ImageReader(g), rx, _y(800), rw, 250, mask="auto")
    else:
        _kpi(c, fonts, rx, 560, rw, 240, "Aporte total",
             _fmt_money(inputs["initial_capital"] + inputs["monthly_contribution"] * 12 * years),
             C_GOLD, "Capital + aportes (sin rendimiento)")

    # KPI tiles abajo
    kw = (PAGE_W - 2 * MARGIN - 2 * 24) / 3
    _kpi(c, fonts, MARGIN, 824, kw, 140, "Pesimista (P5)", _fmt_money(p5), C_RED, "5% quedó por debajo")
    _kpi(c, fonts, MARGIN + kw + 24, 824, kw, 140, "Mediano (P50)", _fmt_money(p50), C_ORANGE, "Escenario central")
    _kpi(c, fonts, MARGIN + 2 * (kw + 24), 824, kw, 140, "Optimista (P95)", _fmt_money(p95), C_GREEN, "Solo 5% lo superó")

    _disclaimer(c, fonts, 980)
    c.showPage()


def _page2(c, fonts, result, inputs, benchmarks):
    import numpy as np
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    _page_header(c, fonts, "Análisis detallado",
                 "Percentiles por año · comparación con benchmarks · métricas de riesgo")

    # Tabla de percentiles por año
    years = [y for y in (5, 10, 15, 20) if y <= inputs["horizon_years"]] or [inputs["horizon_years"]]
    table = st_metrics.percentiles_at_years(result["percentiles"], years)
    _card(c, MARGIN, 150, 1120, 360)
    _text(c, MARGIN + 24, 168, "PATRIMONIO POR AÑO (PERCENTILES)", fonts["medium"], 15, C_LO)
    cols = ["Año", "P5", "P25", "Mediana", "P75", "P95"]
    colx = [MARGIN + 30, MARGIN + 220, MARGIN + 400, MARGIN + 590, MARGIN + 790, MARGIN + 970]
    for cx, name in zip(colx, cols):
        _text(c, cx, 210, name, fonts["bold"], 16, C_MD)
    row_top = 244
    for y in years:
        vals = table[y]
        _text(c, colx[0], row_top, f"{y}", fonts["bold"], 16, C_ORANGE)
        for cx, key, col in zip(colx[1:], ["P5", "P25", "P50", "P75", "P95"],
                                [C_RED, C_MD, C_ORANGE, C_MD, C_GREEN]):
            _text(c, cx, row_top, _fmt_money(vals[key]), fonts["regular"], 15, col)
        row_top += 40

    # Comparación con benchmarks
    _card(c, MARGIN + 1150, 150, PAGE_W - 2 * MARGIN - 1150, 360)
    bx = MARGIN + 1174
    _text(c, bx, 168, "TU CARTERA vs BENCHMARKS", fonts["medium"], 15, C_LO)
    rows = [("Tu portafolio", result, C_ORANGE)]
    rows += [(b["label"], b["result"], C_BLUE) for b in (benchmarks or [])]
    ry = 214
    for label, r, col in rows:
        med = float(np.percentile(r["final_values"], 50))
        _text(c, bx, ry, label, fonts["bold"], 16, col)
        _text(c, bx, ry + 24, f"Mediana {_fmt_money(med)}  ·  Sharpe {r['expected_sharpe']:.2f}",
              fonts["regular"], 14, C_MD)
        ry += 70

    # Métricas de riesgo (KPI tiles)
    kw = (PAGE_W - 2 * MARGIN - 3 * 24) / 4
    prob = result["prob_target"]
    _kpi(c, fonts, MARGIN, 560, kw, 150, "Sharpe esperado", f"{result['expected_sharpe']:.2f}",
         C_GOLD, "Retorno/riesgo anualizado")
    _kpi(c, fonts, MARGIN + kw + 24, 560, kw, 150, "Drawdown típico",
         f"{result['max_drawdown_typical']*100:.1f}%", C_BLUE, "Caída pico-a-valle mediana")
    _kpi(c, fonts, MARGIN + 2 * (kw + 24), 560, kw, 150, "Prob. de ruina",
         f"{result['probability_of_ruin']*100:.1f}%", C_LO, "Escenarios que tocaron $0")
    _kpi(c, fonts, MARGIN + 3 * (kw + 24), 560, kw, 150, "Prob. de meta",
         (f"{prob*100:.1f}%" if prob is not None else "—"),
         (C_GREEN if (prob or 0) >= 0.7 else C_ORANGE if (prob or 0) >= 0.5 else C_RED),
         "Escenarios que alcanzaron la meta")

    # Nota de método
    _text(c, MARGIN, 760, "Método: 10.000 simulaciones Montecarlo de retornos mensuales "
          "correlacionados (Cholesky), parámetros estimados de "
          f"{inputs['historical_window_years']} años de retornos históricos. "
          f"Modelo: {'t-Student (colas gordas)' if inputs['distribution']=='t-student' else 'Normal'}.",
          fonts["regular"], 14, C_DIM)

    _disclaimer(c, fonts, 980)
    c.showPage()


def _logo_with_glow(logo_path: str, box: int = 320) -> str | None:
    """Procesa el logo con esquinas redondeadas + glow halo naranja + sombra (PIL).
    Devuelve la ruta a un PNG temporal, o None si falla."""
    try:
        from PIL import Image, ImageDraw, ImageFilter

        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((box, box), Image.LANCZOS)
        lw, lh = logo.size
        radius = max(10, min(lw, lh) // 10)

        # Esquinas redondeadas (combina alpha existente con máscara redondeada)
        rmask = Image.new("L", (lw, lh), 0)
        ImageDraw.Draw(rmask).rounded_rectangle([0, 0, lw - 1, lh - 1], radius=radius, fill=255)
        alpha = Image.composite(logo.split()[-1], Image.new("L", (lw, lh), 0), rmask)
        logo.putalpha(alpha)

        pad = box // 2
        size = (lw + 2 * pad, lh + 2 * pad)
        out = Image.new("RGBA", size, (0, 0, 0, 0))

        # Sombra
        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        dark = Image.composite(Image.new("RGBA", (lw, lh), (0, 0, 0, 190)),
                               Image.new("RGBA", (lw, lh), (0, 0, 0, 0)), alpha)
        shadow.paste(dark, (pad + 8, pad + 14), dark)
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        out = Image.alpha_composite(out, shadow)

        # Glow halo naranja (silueta tintada, muy difuminada, compuesta 2x)
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        tint = Image.composite(Image.new("RGBA", (lw, lh), (255, 184, 77, 255)),
                               Image.new("RGBA", (lw, lh), (0, 0, 0, 0)), alpha)
        glow.paste(tint, (pad, pad), tint)
        glow = glow.filter(ImageFilter.GaussianBlur(pad // 4))
        out = Image.alpha_composite(out, glow)
        out = Image.alpha_composite(out, glow)

        # Logo encima
        out.paste(logo, (pad, pad), logo)
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        out.save(tmp.name)
        return tmp.name
    except Exception:
        return None


def _draw_qr(c, url: str, x: float, top: float, size: float):
    """QR clickeable sobre un card blanco (para contraste/escaneo)."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing

    pad = 16
    _card(c, x - pad, top - pad, size + 2 * pad, size + 2 * pad, fill=HexColor("#FFFFFF"),
          border=C_ORANGE, radius=12)
    code = qr.QrCodeWidget(url)
    b = code.getBounds()
    w, h = b[2] - b[0], b[3] - b[1]
    d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    d.add(code)
    renderPDF.draw(d, c, x, _y(top + size))
    c.linkURL(url, (x - pad, _y(top + size + pad), x + size + pad, _y(top - pad)), relative=0)


def _page3(c, fonts, inputs):
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    url = "https://diariolargoplazo.com"

    # Logo Club DLP con glow halo + sombra (Fase 3, lead magnet)
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "club_dlp_logo.png"
    if logo_path.exists():
        glow_png = _logo_with_glow(str(logo_path))
        if glow_png:
            try:
                img = ImageReader(glow_png)
                iw, ih = img.getSize()
                disp_w = 360.0
                disp_h = disp_w * ih / iw
                c.drawImage(img, PAGE_W / 2 - disp_w / 2, _y(80 + disp_h), disp_w, disp_h, mask="auto")
            except Exception:
                pass

    _text(c, PAGE_W / 2, 430, "¿Quieres decidir con datos en vez de corazonadas?",
          fonts["bold"], 46, C_HI, center=True)
    _text(c, PAGE_W / 2, 500,
          "Club DLP — comunidad de inversión a largo plazo para Latinoamérica.",
          fonts["regular"], 22, C_MD, center=True)
    _text(c, PAGE_W / 2, 538,
          "Estrategia, comunidad y herramientas para invertir con cabeza fría a 20 años.",
          fonts["regular"], 18, C_LO, center=True)

    # Botón CTA (negro con texto naranja), clickeable
    bw, bh = 560, 86
    bx, btop = PAGE_W / 2 - bw / 2, 600
    _card(c, bx, btop, bw, bh, fill=HexColor("#000000"), border=C_ORANGE, radius=16)
    _text(c, PAGE_W / 2, btop + 28, "ÚNETE EN DIARIOLARGOPLAZO.COM", fonts["bold"], 26, C_ORANGE, center=True)
    c.linkURL(url, (bx, _y(btop + bh), bx + bw, _y(btop)), relative=0)

    # QR clickeable
    qr_size = 150
    _draw_qr(c, url, PAGE_W / 2 - qr_size / 2, 730, qr_size)
    _text(c, PAGE_W / 2, 730 + qr_size + 28, "Escanea para unirte", fonts["regular"], 15, C_LO, center=True)

    _disclaimer(c, fonts, 980)
    c.showPage()


# ── API pública ──────────────────────────────────────────────────────────────
def generate_report(result: dict, inputs: dict, benchmarks: list[dict] | None = None) -> bytes:
    """Genera el PDF de 3 páginas y devuelve sus bytes."""
    import io

    _ensure_kaleido_launcher()
    fonts = register_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle("DLP — Proyección de portafolio")
    _page1(c, fonts, result, inputs)
    _page2(c, fonts, result, inputs, benchmarks or [])
    _page3(c, fonts, inputs)
    c.save()
    return buf.getvalue()
