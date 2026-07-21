"""Sistema de diseño DLP — extensión visual directa de DLP Market Analyzer.

Los tokens y superficies son los MISMOS que usa la app madre (L-DLP-Analysis):
tipografía Inter para cuerpo + JetBrains Mono para datos/labels, fondo radial
Bloomberg-grade, cards en degradado 135° con borde dorado, y micro-animaciones
(fade-up, pulse-glow, shimmer). Así ambas apps se leen como un mismo producto.
"""
from __future__ import annotations

import streamlit as st

# ── Paleta (idéntica a DLP Market Analyzer — no aproximar) ───────────────────
BG_DEEP = "#0A0D11"      # fondo principal (analyzer)
BG_CARD = "#0F1419"      # base de card / fondo de gráficos (analyzer)
BG_CARD2 = "#131922"     # tope del degradado de card (analyzer)
BG_ELEV = "#1A1F28"      # superficie elevada (tooltips, popovers)
BG_CTA = "#0F1419"
ORANGE = "#FFB84D"
ORANGE_DK = "#FFA500"
GOLD = "#FFD740"
GREEN = "#00FF88"
GREEN_DK = "#00C853"
RED = "#FF3B5C"
RED_DK = "#E53935"
BLUE = "#4A9EFF"
BLUE_DK = "#2196F3"
PURPLE = "#9B59FF"
TEXT_HI = "#FFFFFF"
TEXT_MD = "#E4E7EC"
TEXT_SOFT = "#C8D0D8"    # tono intermedio del analyzer
TEXT_LO = "#7A8898"
TEXT_DIM = "#5A6878"
BORDER = "#1E2530"
BORDER_SOFT = "#2A3545"

# Firma visual del analyzer: bordes/divisores teñidos de oro (no grises)
GOLD_HAIR = "rgba(255,184,77,0.12)"
GOLD_LINE = "rgba(255,184,77,0.15)"
GOLD_EDGE = "rgba(255,184,77,0.18)"
GOLD_HOVER = "rgba(255,184,77,0.35)"

# Gridlines de las gráficas: hairline gris que no compite con los datos (analyzer)
GRID_HAIR = "rgba(122,136,152,0.10)"
GRID_ZERO = "rgba(122,136,152,0.18)"

# Fondo de página exacto del analyzer
APP_BG = "radial-gradient(ellipse at top, #0F1218 0%, #0A0D11 60%, #06080B 100%)"
# Superficie de card exacta del analyzer
CARD_BG = f"linear-gradient(135deg, {BG_CARD} 0%, {BG_CARD2} 100%)"
# Superficie "metálica": gris-azulada más clara que el fondo, con relieve, para diferenciar
# claramente las tarjetas de la página (se usa en tiles, cards y cápsulas por pestaña).
METAL_BG = "linear-gradient(150deg, #1B2230 0%, #12192A 100%)"
METAL_BORDER = "rgba(255,184,77,.20)"
METAL_SHADOW = "0 8px 26px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.05)"

FONT_FAMILY = "'Inter', sans-serif"
MONO = "'JetBrains Mono', ui-monospace, 'SF Mono', 'Roboto Mono', monospace"


def color_for_percentile(kind: str) -> str:
    return {"median": ORANGE, "optimistic": GREEN, "pessimistic": RED}[kind]


def disable_context_menu() -> None:
    """Desactiva el menú contextual (clic derecho) en toda la app.

    Streamlit NO ejecuta <script> dentro de st.markdown, así que usamos un componente
    HTML (iframe height=0, invisible) y desde ahí enganchamos el listener en el
    documento padre —la app real— vía window.parent.document (mismo origen). El guard
    __dlpNoCtx evita apilar listeners en cada rerun. Es puramente disuasorio para el
    usuario casual (abrir en pestaña nueva, "ver código fuente", etc.); no cambia nada
    del contenido ni de la lógica. Llamar una vez al inicio de app.py.
    """
    import streamlit.components.v1 as _stc

    _stc.html(
        """
        <script>
        (function () {
          var block = function (e) { e.preventDefault(); return false; };
          try {
            var pdoc = window.parent.document;
            if (!window.parent.__dlpNoCtx) {
              window.parent.__dlpNoCtx = true;
              pdoc.addEventListener('contextmenu', block, true);
            }
          } catch (err) { /* cross-origin improbable: seguimos con el iframe local */ }
          document.addEventListener('contextmenu', block, true);
        })();
        </script>
        """,
        height=0,
    )


def inject_css() -> None:
    """Inyecta el CSS global premium. Llamar una vez al inicio de app.py."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap');

        /* ── Animaciones (mismas que la app madre) ────────────── */
        @keyframes dlpFadeUp {{ from {{opacity:0; transform:translateY(20px);}} to {{opacity:1; transform:translateY(0);}} }}
        @keyframes dlpFadeIn {{ from {{opacity:0;}} to {{opacity:1;}} }}
        @keyframes dlpBreathe {{ 0%,100% {{opacity:.55;}} 50% {{opacity:1;}} }}
        /* pulse-glow del analyzer: glow de texto que respira */
        @keyframes dlpPulseGlow {{
            0%,100% {{ text-shadow: 0 0 20px rgba(255,184,77,.4), 0 0 40px rgba(255,184,77,.2); }}
            50%     {{ text-shadow: 0 0 30px rgba(255,184,77,.7), 0 0 60px rgba(255,184,77,.4); }}
        }}
        /* glow-border del analyzer */
        @keyframes dlpPulse {{
            0%,100% {{ box-shadow:0 0 0 1px rgba(255,184,77,.3), 0 0 20px rgba(255,184,77,.1); }}
            50% {{ box-shadow:0 0 0 1px rgba(255,184,77,.6), 0 0 40px rgba(255,184,77,.25); }}
        }}
        @keyframes dlpShimmer {{ 0% {{background-position:0% 50%;}} 100% {{background-position:200% 50%;}} }}
        @keyframes dlpSpin {{ from {{transform:rotate(45deg);}} to {{transform:rotate(405deg);}} }}
        @keyframes dlpScanLine {{ 0% {{transform:translateX(-100%);}} 100% {{transform:translateX(100%);}} }}

        /* ── Curvas de easing fuertes (design-eng: las nativas son flojas) ─────
           ease-out potente para entradas/hover · in-out para movimiento en pantalla */
        :root {{
            --dlp-ease-out: cubic-bezier(0.23, 1, 0.32, 1);
            --dlp-ease-io:  cubic-bezier(0.77, 0, 0.175, 1);
        }}

        /* ── Base (fondo radial Bloomberg-grade del analyzer) ─── */
        html, body, [data-testid="stAppViewContainer"], .stApp {{
            background: {APP_BG} !important;
            color: {TEXT_MD} !important;
            font-family: {FONT_FAMILY} !important;
        }}
        [data-testid="stMain"] {{ background: transparent !important; }}
        /* Embed cuadrado 1:1 (~800px): contenido centrado y compacto */
        .block-container {{ padding-top: .8rem; padding-bottom: 2rem; max-width: 780px;
            animation: dlpFadeUp .8s ease-out both; }}
        section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{ display: none !important; }}
        h1, h2, h3, h4, h5 {{
            font-family: {MONO} !important; color: {TEXT_HI};
            text-transform: uppercase; letter-spacing: .06em; font-weight: 700;
        }}
        #MainMenu, footer, header {{ visibility: hidden; display: none !important; }}
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}

        /* ── Scrollbar (firma del analyzer) ───────────────────── */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: {BG_DEEP}; }}
        ::-webkit-scrollbar-thumb {{ background: linear-gradient(180deg, {BORDER_SOFT}, {BORDER}); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(255,184,77,0.4); }}

        /* ── Divisores dorados (analyzer) ─────────────────────── */
        hr {{ border-color: rgba(255,184,77,0.1) !important; margin: 16px 0 !important; }}

        /* ── Loader overlay: fijo, centrado, imposible de perderse (patrón analyzer) ── */
        .dlp-loader-overlay {{
            position: fixed; inset: 0; z-index: 100000;
            display: flex; align-items: center; justify-content: center;
            background: radial-gradient(ellipse at center, rgba(8,11,15,.78), rgba(6,8,11,.92));
            backdrop-filter: blur(7px); -webkit-backdrop-filter: blur(7px);
            animation: dlpFadeIn .18s ease both;
        }}
        .dlp-loader-panel {{
            display: flex; flex-direction: column; align-items: center; gap: 20px;
            background: {CARD_BG}; border: 1px solid rgba(255,184,77,.30); border-radius: 20px;
            padding: 36px 48px;
            box-shadow: 0 24px 70px rgba(0,0,0,.65), 0 0 0 1px rgba(255,184,77,.08),
                        0 0 70px rgba(255,184,77,.14);
        }}
        .dlp-loader-ring {{
            width: 150px; height: 150px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 48px rgba(255,184,77,.30); transition: background .12s linear;
        }}
        .dlp-loader-hole {{
            width: 116px; height: 116px; border-radius: 50%; background: {BG_DEEP};
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }}
        .dlp-loader-hole .pct {{ font-family: {MONO}; font-size: 34px; font-weight: 800; color: {ORANGE};
            filter: drop-shadow(0 0 12px rgba(255,184,77,.4)); }}
        .dlp-loader-hole .lbl {{ font-family: {MONO}; font-size: 10px; letter-spacing: .20em;
            color: {TEXT_LO}; margin-top: 3px; }}
        .dlp-loader-msg {{ font-family: {MONO}; text-transform: uppercase; letter-spacing: .14em;
            color: {TEXT_MD}; font-size: 13px; animation: dlpBreathe 2.4s ease-in-out infinite; }}

        /* ── Hero de página (mismo tratamiento que .alpha-hero) ─ */
        .dlp-page-hero {{ position: relative; text-align: center; padding: 8px 0 4px;
            animation: dlpFadeUp .8s ease-out both; }}
        .dlp-page-hero .glow {{
            position:absolute; top:-30px; left:50%; transform:translateX(-50%);
            width:640px; height:240px; pointer-events:none; filter: blur(18px);
            background: radial-gradient(ellipse at center, rgba(255,184,77,.18), rgba(255,184,77,0) 70%);
            animation: dlpBreathe 6s ease-in-out infinite;
        }}
        .dlp-page-hero .diamond {{
            color:{GOLD}; font-size:20px; line-height:1; display:inline-block;
            filter: drop-shadow(0 0 12px rgba(255,215,64,.55)); margin-bottom: 4px;
        }}
        /* Marca: degradado 135° + pulse-glow exactos de .alpha-hero-brand */
        .dlp-page-hero .title {{
            font-family:{MONO}; font-weight:800; font-size:38px; line-height:1.0;
            text-transform:uppercase; letter-spacing:.05em; margin: 2px 0 6px;
            background: linear-gradient(135deg, {ORANGE} 0%, {GOLD} 50%, {ORANGE_DK} 100%);
            -webkit-background-clip:text; background-clip:text;
            -webkit-text-fill-color:transparent;
            animation: dlpPulseGlow 4s ease-in-out infinite;
        }}
        /* Tagline: Inter en mayúsculas, igual que .alpha-hero-tagline */
        .dlp-page-hero .sub {{
            font-family:{FONT_FAMILY}; color:{TEXT_LO}; text-transform:uppercase;
            letter-spacing:.15em; font-size:13px; font-weight:400;
        }}
        .dlp-rule {{ height:1px; max-width:100px; margin:20px auto 6px;
            background: linear-gradient(90deg, transparent, {ORANGE}, transparent); }}

        /* ── Stepper ──────────────────────────────────────────── */
        .dlp-steps {{ display:flex; gap:12px; justify-content:center; margin:14px 0 20px; flex-wrap:wrap; }}
        .dlp-step {{
            display:flex; align-items:center; gap:10px; padding:9px 18px; border-radius:12px;
            background:{BG_CARD}; border:1px solid {BORDER}; font-family:{MONO};
            font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:{TEXT_LO};
            transition: border-color .25s var(--dlp-ease-out), color .25s var(--dlp-ease-out), box-shadow .25s var(--dlp-ease-out);
        }}
        .dlp-step .num {{ width:22px; height:22px; border-radius:50%; display:flex;
            align-items:center; justify-content:center; font-size:11px; font-weight:700;
            background:{BG_CARD2}; color:{TEXT_LO}; border:1px solid {BORDER}; }}
        .dlp-step.done {{ border-color: rgba(0,255,136,.4); color:{TEXT_MD}; }}
        .dlp-step.done .num {{ background:rgba(0,255,136,.15); color:{GREEN}; border-color:rgba(0,255,136,.5); }}
        .dlp-step.active {{ border-color:{ORANGE}; color:{ORANGE};
            box-shadow:0 0 22px rgba(255,184,77,.16); }}
        .dlp-step.active .num {{ background:rgba(255,184,77,.16); color:{ORANGE}; border-color:{ORANGE}; }}

        /* ── Pills de estado ──────────────────────────────────── */
        .dlp-pill {{ display:inline-block; padding:3px 10px; border-radius:6px; font-family:{MONO};
            font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.07em; }}
        .dlp-pill-orange {{ background:linear-gradient(135deg,{ORANGE},{ORANGE_DK}); color:#1A1206; }}
        .dlp-pill-blue   {{ background:linear-gradient(135deg,{BLUE},{BLUE_DK});   color:#06121F; }}
        .dlp-pill-green  {{ background:linear-gradient(135deg,{GREEN},{GREEN_DK}); color:#04140A; }}
        .dlp-pill-ghost  {{ background:{BG_CARD2}; color:{TEXT_LO}; border:1px solid {BORDER}; }}

        /* ── Sidebar ──────────────────────────────────────────── */
        section[data-testid="stSidebar"] > div {{
            background: linear-gradient(180deg, #0A0D11 0%, #0D1117 100%);
            border-right: 1px solid {BORDER};
        }}
        .dlp-side-brand {{ display:flex; align-items:center; gap:10px; padding:6px 2px 2px; }}
        .dlp-side-brand .d {{ color:{GOLD}; font-size:18px; filter: drop-shadow(0 0 10px rgba(255,215,64,.5)); }}
        .dlp-side-brand .t {{ font-family:{MONO}; font-weight:800; color:{TEXT_HI}; letter-spacing:.06em; }}
        .dlp-side-brand .s {{ font-family:{MONO}; font-size:10px; color:{TEXT_LO}; letter-spacing:.22em; }}
        .dlp-side-title {{ color:{TEXT_LO}; font-family:{MONO}; font-size:11px; font-weight:700;
            text-transform:uppercase; letter-spacing:.16em; margin:18px 0 8px; }}
        .dlp-side-item {{ background:{BG_CARD}; border:1px solid {BORDER}; border-left:3px solid {ORANGE};
            border-radius:8px; padding:9px 12px; margin-bottom:8px;
            transition: transform .18s var(--dlp-ease-out), border-color .18s var(--dlp-ease-out); }}
        .dlp-side-item:hover {{ border-color:rgba(255,184,77,.4); transform: translateX(2px); }}
        .dlp-side-item .lbl {{ color:{TEXT_MD}; font-size:13px; font-weight:600; }}
        .dlp-side-item .meta {{ color:{TEXT_LO}; font-size:11px; margin-top:2px; }}

        /* ── Hero de resultados (v2): monto grande centrado, meta distribuida ── */
        .dlp-hero-v2 {{ text-align:center; background:
            radial-gradient(600px 220px at 50% -40px, rgba(255,184,77,.10), rgba(0,0,0,0) 70%), {METAL_BG};
            border:1px solid {ORANGE}; border-radius:18px; padding:24px 30px 20px; margin-bottom:18px;
            box-shadow: {METAL_SHADOW}, 0 0 50px rgba(255,184,77,.10);
            animation: dlpFadeUp .5s var(--dlp-ease-out) both; }}
        .dlp-hero-v2 .hero-top {{ font-family:{MONO}; text-transform:uppercase; letter-spacing:.14em;
            font-size:11.5px; color:{TEXT_LO}; }}
        .dlp-hero-v2 .hero-top .hero-glyph {{ color:{GOLD}; filter:drop-shadow(0 0 8px rgba(255,215,64,.5)); }}
        .dlp-hero-v2 .hero-number {{ font-family:{MONO}; font-weight:800; line-height:1.02;
            font-size:clamp(38px, 8.5vw, 60px); margin:6px 0 2px;
            filter: drop-shadow(0 4px 26px rgba(255,184,77,.22)); }}
        .dlp-hero-v2 .hero-meta {{ display:flex; justify-content:center; gap:12px; margin-top:16px;
            flex-wrap:wrap; border-top:1px solid {BORDER}; padding-top:14px; }}
        .dlp-hero-v2 .hm {{ flex:1; min-width:110px; }}
        .dlp-hero-v2 .hm-label {{ font-family:{MONO}; font-size:10px; text-transform:uppercase;
            letter-spacing:.10em; color:{TEXT_LO}; }}
        .dlp-hero-v2 .hm-value {{ font-size:17px; font-weight:700; color:{TEXT_HI}; margin-top:3px; }}

        /* ── Cards (superficie 135° + borde dorado del analyzer) ─ */
        .dlp-card {{ background:{METAL_BG}; border:1px solid {METAL_BORDER}; border-radius:12px;
            padding:20px 22px; margin-bottom:16px;
            transition: transform .25s var(--dlp-ease-out), border-color .25s var(--dlp-ease-out), box-shadow .25s var(--dlp-ease-out);
            box-shadow: {METAL_SHADOW};
            animation: dlpFadeUp .4s var(--dlp-ease-out) both; }}
        .dlp-card:hover {{ border-color: {GOLD_HOVER}; transform: translateY(-2px);
            box-shadow: {METAL_SHADOW}, 0 0 26px rgba(255,184,77,.07); }}
        .dlp-card2 {{ background:{BG_CARD2}; }}
        /* Acento izquierdo dorado — igual que .analysis-card / .agent-header */
        .dlp-card-left {{ border-left:3px solid {ORANGE}; }}

        /* ── Hero card (resultados) — patrón .qv-header ────────── */
        .dlp-hero {{ background: {CARD_BG};
            border:1px solid {GOLD_HOVER}; border-left:3px solid {ORANGE};
            border-radius:12px; padding:26px 30px; margin-bottom:18px;
            display:flex; align-items:center; justify-content:space-between;
            box-shadow:0 4px 24px rgba(0,0,0,.4); animation: dlpFadeUp .4s ease-out both; }}
        .dlp-hero .glyph {{ font-size:74px; font-weight:800; line-height:1; font-family:{MONO};
            background:linear-gradient(135deg,{ORANGE},{ORANGE_DK}); -webkit-background-clip:text;
            -webkit-text-fill-color:transparent; background-clip:text;
            filter: drop-shadow(0 0 18px rgba(255,184,77,.35)); }}
        .dlp-hero .meta-label {{ color:{TEXT_LO}; font-family:{MONO}; font-size:11px;
            text-transform:uppercase; letter-spacing:.10em; }}
        .dlp-hero .meta-value {{ color:{TEXT_HI}; font-size:20px; font-weight:700; }}

        /* ── KPI tile (stat tile): superficie metálica + borde dorado + termómetro + "?" ── */
        .dlp-kpi {{ position:relative; display:flex; flex-direction:column;
            background:{METAL_BG}; border:1px solid rgba(255,184,77,.30); border-radius:13px;
            padding:16px 17px 15px; min-height:178px; height:100%; overflow:visible;
            box-shadow: {METAL_SHADOW}, 0 0 0 1px rgba(255,184,77,.05);
            transition: transform .2s var(--dlp-ease-out), border-color .2s var(--dlp-ease-out),
                        box-shadow .2s var(--dlp-ease-out);
            animation: dlpFadeUp .45s var(--dlp-ease-out) both; }}
        .dlp-kpi:hover {{ transform: translateY(-3px); border-color: {GOLD_HOVER};
            box-shadow: {METAL_SHADOW}, 0 0 0 1px rgba(255,184,77,.14), 0 0 34px rgba(255,184,77,.12); }}
        .dlp-kpi .accent {{ position:absolute; top:0; left:0; right:0; height:4px;
            border-radius:13px 13px 0 0; opacity:.95; }}
        .dlp-kpi .kpi-head {{ display:flex; align-items:center; gap:8px; }}
        .dlp-kpi .kpi-label {{ color:{TEXT_SOFT}; font-family:{MONO}; font-size:11.5px; font-weight:700;
            text-transform:uppercase; letter-spacing:.10em; line-height:1.2; flex:1; min-width:0; }}
        .dlp-kpi .kpi-value {{ font-family:{MONO}; font-weight:800; line-height:1.1;
            font-size:clamp(20px, 4.0vw, 31px); margin:8px 0 2px;
            white-space:nowrap; overflow:hidden; text-overflow:clip; }}
        .dlp-kpi .kpi-sub {{ color:{TEXT_LO}; font-size:12px; line-height:1.35; }}
        /* Termómetro rojo→verde con marcador + palabra (pinned al fondo → tiles uniformes) */
        .dlp-kpi .kpi-meter {{ margin-top:auto; padding-top:12px; }}
        .kpi-meter-track {{ position:relative; height:6px; border-radius:4px;
            background: linear-gradient(90deg, {RED} 0%, {ORANGE} 50%, {GREEN} 100%);
            box-shadow: inset 0 1px 2px rgba(0,0,0,.5); }}
        .kpi-meter-dot {{ position:absolute; top:50%; transform:translate(-50%,-50%);
            width:13px; height:13px; border-radius:50%; background:#FFFFFF; border:2.5px solid #fff; }}
        .kpi-meter-word {{ font-family:{MONO}; font-size:10.5px; font-weight:800;
            text-transform:uppercase; letter-spacing:.08em; margin-top:6px; text-align:right; }}

        /* Badge "?" dorado con tooltip (portado de DLP Analyzer .kpi-help) */
        .dlp-kpi-help {{ display:inline-flex; align-items:center; justify-content:center;
            width:17px; height:17px; border-radius:50%; background:rgba(255,184,77,.10);
            border:1px solid rgba(255,184,77,.45); color:{ORANGE}; font-size:11px; font-weight:800;
            font-family:{FONT_FAMILY}; cursor:help; position:relative; flex-shrink:0;
            transition: all .2s var(--dlp-ease-out); }}
        .dlp-kpi-help:hover {{ background:rgba(255,184,77,.22); border-color:{ORANGE}; color:{GOLD};
            transform:scale(1.12); }}
        .dlp-kpi-help::after {{ content:attr(data-tooltip); position:absolute; bottom:calc(100% + 9px);
            right:-6px; background:linear-gradient(135deg,{BG_CARD2},{BG_ELEV}); color:{TEXT_MD};
            padding:11px 13px; border-radius:9px; border:1px solid rgba(255,184,77,.35);
            border-bottom:2px solid {ORANGE}; white-space:normal; width:238px; font-size:12.5px;
            font-weight:400; font-family:{FONT_FAMILY}; line-height:1.5; letter-spacing:0;
            text-transform:none; text-align:left; z-index:9999; pointer-events:none;
            box-shadow:0 12px 32px rgba(0,0,0,.7);
            opacity:0; transform:translateY(4px); transition: opacity .2s ease, transform .2s ease; }}
        .dlp-kpi-help:hover::after {{ opacity:1; transform:translateY(0); }}

        /* ── Disclaimer ───────────────────────────────────────── */
        .dlp-disclaimer {{ background:rgba(255,59,92,.08); border:1px solid rgba(255,59,92,.45);
            border-left:5px solid {RED}; border-radius:12px; padding:16px 20px; margin:14px 0 18px;
            animation: dlpFadeUp .45s ease both; }}
        .dlp-disclaimer .head {{ color:{RED}; font-family:{MONO}; font-size:12px; font-weight:800;
            text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px; }}
        .dlp-disclaimer .body {{ color:{TEXT_MD}; font-size:14px; line-height:1.5; }}
        .dlp-sample-warn {{ background:rgba(255,215,64,.08); border:1px solid rgba(255,215,64,.45);
            border-left:5px solid {GOLD}; border-radius:10px; padding:12px 16px; margin:10px 0;
            color:{TEXT_MD}; font-size:13.5px; }}

        /* ── Botones ──────────────────────────────────────────── */
        /* CTA primario "Analizar": color SÓLIDO + borde nítido dorado + glow en el borde que
           llama la atención (estático premium, sin pulse perpetuo) + feedback al presionar. */
        button[data-testid^="stBaseButton-primary"] {{
            background: {ORANGE} !important;
            color:#1A1206 !important; font-family:{MONO} !important; font-weight:800 !important;
            text-transform:uppercase; letter-spacing:.12em; font-size:15px !important;
            border:1.5px solid rgba(255,226,140,.95) !important;
            border-radius:12px !important; padding:15px 22px !important;
            box-shadow: 0 0 0 1px rgba(255,184,77,.45), 0 0 22px rgba(255,184,77,.38),
                        0 8px 26px rgba(255,165,0,.30), inset 0 1px 0 rgba(255,255,255,.35) !important;
            transition: transform .16s var(--dlp-ease-out), box-shadow .2s var(--dlp-ease-out),
                        background .16s var(--dlp-ease-out);
        }}
        button[data-testid^="stBaseButton-primary"]:hover {{
            background: #FFC85C !important; transform: translateY(-2px);
            box-shadow: 0 0 0 1px rgba(255,214,110,.8), 0 0 34px rgba(255,184,77,.55),
                        0 12px 34px rgba(255,165,0,.42), inset 0 1px 0 rgba(255,255,255,.4) !important; }}
        button[data-testid^="stBaseButton-primary"]:active {{ transform: scale(.97); }}
        button[data-testid^="stBaseButton-primary"]:disabled {{
            background:{BG_CARD2} !important; color:{TEXT_DIM} !important;
            box-shadow:none !important; animation:none; opacity:1 !important;
            border:1px dashed {BORDER} !important;
        }}
        /* Secundario: superficie sólida azul-gris + borde nítido */
        button[data-testid^="stBaseButton-secondary"] {{
            background:{BG_CARD2} !important; color:{TEXT_MD} !important;
            border:1px solid {BORDER_SOFT} !important; border-radius:10px !important;
            font-family:{MONO} !important; font-weight:700 !important; letter-spacing:.06em;
            text-transform:uppercase; padding:11px 18px !important;
            transition: transform .16s var(--dlp-ease-out), border-color .16s var(--dlp-ease-out),
                        color .16s var(--dlp-ease-out), box-shadow .16s var(--dlp-ease-out);
        }}
        button[data-testid^="stBaseButton-secondary"]:hover {{
            border-color:{ORANGE} !important; color:{ORANGE} !important; transform: translateY(-1px);
            box-shadow: 0 0 18px rgba(255,184,77,.12) !important; }}
        button[data-testid^="stBaseButton-secondary"]:active {{ transform: scale(.97); }}

        /* Inputs */
        .stTextInput input, .stNumberInput input {{
            background:{BG_CARD2} !important; color:{TEXT_HI} !important;
            border:1px solid {BORDER} !important; border-radius:9px !important; }}
        .stTextInput input:focus, .stNumberInput input:focus {{
            border-color:{ORANGE} !important; box-shadow:0 0 0 2px rgba(255,184,77,.15) !important; }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{ gap:6px; }}
        .stTabs [data-baseweb="tab"] {{ font-family:{MONO}; text-transform:uppercase;
            letter-spacing:.06em; font-size:13px; }}
        .stTabs [aria-selected="true"] {{ color:{ORANGE} !important; }}

        /* ── Cards vía keyed containers: st.container(key="card-…") ── */
        div[class*="st-key-card-"] {{
            background: {METAL_BG};
            border: 1px solid {METAL_BORDER}; border-radius: 18px;
            padding: 10px 26px 22px; margin-bottom: 18px;
            box-shadow: {METAL_SHADOW};
            transition: border-color .2s var(--dlp-ease-out);
        }}
        div[class*="st-key-card-"]:hover {{ border-color: rgba(255,184,77,.26); }}
        .dlp-card-head {{ display:flex; align-items:baseline; gap:11px; margin: 8px 0 16px;
            border-bottom:1px solid {BORDER}; padding-bottom:12px; }}
        .dlp-card-head .ic {{ color:{ORANGE}; font-size:15px;
            filter: drop-shadow(0 0 8px rgba(255,184,77,.45)); }}
        .dlp-card-head .tx {{ font-family:{MONO}; font-weight:700; text-transform:uppercase;
            letter-spacing:.12em; color:{TEXT_HI}; font-size:15px; }}
        .dlp-card-head .hint {{ font-family:{FONT_FAMILY}; color:{TEXT_LO}; font-size:12.5px;
            margin-left:auto; }}

        /* ── Inputs limpios (sin steppers +/- ) y más aire ─────── */
        [data-testid="stNumberInput"] button {{ display:none !important; }}
        [data-testid="stNumberInput"] input, .stTextInput input {{
            height:46px !important; font-size:15px !important; font-family:{MONO} !important; }}
        [data-testid="stWidgetLabel"] p, .stRadio label p {{
            font-family:{MONO} !important; font-size:11px !important; text-transform:uppercase;
            letter-spacing:.09em; color:{TEXT_LO} !important; font-weight:500; }}
        .stSlider [data-baseweb="slider"] {{ padding-top: 6px; }}
        [data-baseweb="select"] > div {{ background:{BG_CARD2} !important; border-color:{BORDER} !important;
            border-radius:9px !important; min-height:46px; }}
        div[data-testid="stExpander"] {{ border:1px solid {BORDER} !important; border-radius:14px !important;
            background:{BG_CARD} !important; }}
        div[data-testid="stExpander"] summary {{ font-family:{MONO}; text-transform:uppercase;
            letter-spacing:.08em; font-size:13px; }}

        /* ── Menú de resultados del buscador (panel elevado, se separa del fondo) ── */
        div[class*="st-key-searchmenu"] {{
            background: linear-gradient(180deg, #131922 0%, #0C1117 100%);
            border: 1px solid rgba(255,184,77,.40); border-radius: 14px;
            padding: 12px 14px 6px; margin: 6px 0 14px;
            box-shadow: 0 20px 54px rgba(0,0,0,.6); animation: dlpFadeUp .2s ease both;
        }}
        .dlp-search-hd {{ font-family:{MONO}; text-transform:uppercase; letter-spacing:.14em;
            font-size:10px; color:{TEXT_LO}; margin: 2px 2px 8px; }}
        /* Tarjeta de un ticker: código a la izq (con color), nombre+bolsa a la der */
        .dlp-tk {{ display:flex; align-items:center; gap:14px; padding:9px 12px;
            background:{BG_CARD2}; border:1px solid {BORDER}; border-radius:11px;
            transition: transform .15s var(--dlp-ease-out), border-color .15s var(--dlp-ease-out); }}
        .dlp-tk:hover {{ border-color: rgba(255,184,77,.45); transform: translateX(2px); }}
        .dlp-tk .code {{ font-family:{MONO}; font-weight:800; font-size:18px; min-width:72px;
            text-align:center; padding:8px 6px; border:1px solid; border-radius:9px;
            background:rgba(0,0,0,.28); }}
        .dlp-tk .meta {{ margin-left:auto; text-align:right; line-height:1.3; }}
        .dlp-tk .meta .nm {{ color:{TEXT_MD}; font-size:13.5px; font-weight:600; }}
        .dlp-tk .meta .ex {{ color:{TEXT_LO}; font-size:11px; font-family:{MONO}; letter-spacing:.06em; }}

        /* ── Tooltips de ayuda (?) — popover con color para que se note ── */
        [data-testid="stTooltipContent"] {{
            background:{BG_CARD2} !important; color:{TEXT_MD} !important;
            border:1px solid rgba(255,184,77,.55) !important; border-radius:10px !important;
            box-shadow:0 10px 34px rgba(0,0,0,.5) !important; font-size:13px !important;
            line-height:1.5 !important; }}
        [data-testid="stTooltipHoverTarget"] svg, svg[data-testid="stTooltipIcon"] {{
            color:{ORANGE} !important; fill:{ORANGE} !important; }}

        /* ── Botón "Agregar Portafolio B" (azul, evidente, sin pulse) ── */
        div.st-key-addb button {{
            background: rgba(74,158,255,.10) !important; color:{BLUE} !important;
            border:1.5px dashed rgba(74,158,255,.7) !important; border-radius:12px !important;
            padding:14px 18px !important; font-family:{MONO} !important; font-weight:800 !important;
            text-transform:uppercase; letter-spacing:.08em; animation:none !important; }}
        div.st-key-addb button {{ transition: transform .16s var(--dlp-ease-out), background .16s var(--dlp-ease-out); }}
        div.st-key-addb button:hover {{ background: rgba(74,158,255,.18) !important;
            transform: translateY(-1px); }}
        div.st-key-addb button:active {{ transform: scale(.97); }}

        /* ── Tabla comparativa A vs B ── */
        .dlp-cmp {{ width:100%; border-collapse:collapse; font-family:{FONT_FAMILY}; margin-top:4px; }}
        .dlp-cmp th {{ font-family:{MONO}; text-transform:uppercase; letter-spacing:.06em;
            font-size:11px; color:{TEXT_LO}; padding:8px 12px; border-bottom:1px solid {BORDER}; }}
        .dlp-cmp td {{ padding:10px 12px; border-bottom:1px solid {BORDER}; text-align:right;
            font-family:{MONO}; font-weight:700; font-size:15px; color:{TEXT_MD}; }}
        .dlp-cmp td.metric {{ text-align:left; font-family:{FONT_FAMILY}; font-weight:400;
            color:{TEXT_LO}; font-size:13px; }}
        .dlp-cmp tr:last-child td {{ border-bottom:none; }}
        .dlp-cmp .win::after {{ content:" ◆"; font-size:9px; vertical-align:middle; }}

        /* ── Cara a cara (versus) ── */
        .dlp-side {{ text-align:center; }}
        .dlp-side .nm {{ font-family:{MONO}; font-weight:800; letter-spacing:.10em; font-size:13px; }}
        .dlp-side .big {{ font-family:{MONO}; font-weight:800; font-size:27px; margin:2px 0; }}
        .dlp-side .sub {{ color:{TEXT_LO}; font-size:11px; }}
        .dlp-vs-badge {{ display:flex; align-items:center; justify-content:center; min-height:300px; }}
        .dlp-vs-badge span {{ width:48px; height:48px; border-radius:50%; border:1.5px solid {GOLD};
            color:{GOLD}; font-family:{MONO}; font-weight:800; font-size:14px; letter-spacing:.06em;
            display:flex; align-items:center; justify-content:center;
            box-shadow:0 0 20px rgba(255,215,64,.30); background:rgba(255,215,64,.06); }}

        /* ── Barras enfrentadas métrica a métrica ── */
        .dlp-vsm {{ margin:6px 0 16px; }}
        .dlp-vsm .m-lbl {{ font-family:{MONO}; font-size:11px; text-transform:uppercase;
            letter-spacing:.09em; color:{TEXT_LO}; margin-bottom:7px; }}
        .dlp-vsm .m-row {{ display:flex; align-items:center; gap:10px; margin:5px 0; }}
        .dlp-vsm .m-tag {{ font-family:{MONO}; font-weight:800; font-size:13px; width:16px; }}
        .dlp-vsm .m-track {{ flex:1; height:15px; background:{BG_CARD2}; border-radius:8px;
            overflow:hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,.45); }}
        .dlp-vsm .m-fill {{ height:100%; border-radius:8px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.35), inset 0 -3px 5px rgba(0,0,0,.22),
                        0 0 9px rgba(255,184,77,.12); }}
        .dlp-vsm .m-val {{ font-family:{MONO}; font-size:13.5px; color:{TEXT_LO};
            min-width:104px; text-align:right; }}
        .dlp-vsm .m-val.m-win {{ color:{TEXT_HI}; font-weight:800; }}
        .dlp-vsm .m-val.m-win::after {{ content:" ◆"; font-size:9px; }}

        /* ── Botón de PDF: amarillo, grande y llamativo (genera + descarga) ── */
        div.st-key-pdfgo button, div.st-key-pdfdl button {{
            background: linear-gradient(180deg, #FFE680 0%, {GOLD} 45%, {ORANGE} 100%) !important;
            color:#1A1206 !important; border:none !important; border-radius:14px !important;
            font-family:{MONO} !important; font-weight:800 !important; text-transform:uppercase;
            letter-spacing:.10em; font-size:16px !important; padding:18px 24px !important;
            box-shadow:0 0 0 1px rgba(255,215,64,.65), 0 10px 36px rgba(255,184,77,.45) !important;
            transition: transform .16s var(--dlp-ease-out); }}
        div.st-key-pdfgo button:hover, div.st-key-pdfdl button:hover {{ transform: translateY(-2px); }}
        div.st-key-pdfgo button:active, div.st-key-pdfdl button:active {{ transform: scale(.97); }}

        /* ── File uploader: español + nube dorada (traduce el UI interno de Streamlit) ── */
        [data-testid="stFileUploaderDropzone"] {{
            background:{BG_CARD2} !important; border:1.5px dashed rgba(255,184,77,.42) !important;
            border-radius:12px !important; transition: border-color .18s var(--dlp-ease-out); }}
        [data-testid="stFileUploaderDropzone"]:hover {{ border-color:{ORANGE} !important; }}
        [data-testid="stFileUploaderDropzone"] svg {{ fill:{ORANGE} !important; color:{ORANGE} !important;
            filter: drop-shadow(0 0 8px rgba(255,184,77,.4)); }}
        /* Ocultar textos internos en inglés y poner español */
        [data-testid="stFileUploaderDropzoneInstructions"] span,
        [data-testid="stFileUploaderDropzoneInstructions"] small {{ display:none !important; }}
        [data-testid="stFileUploaderDropzoneInstructions"]::after {{
            content:"Arrastra tu archivo aquí, o explóralo — CSV o Excel"; display:block;
            font-family:{FONT_FAMILY}; color:{TEXT_MD}; font-size:13.5px; letter-spacing:.02em;
            margin-top:2px; }}
        [data-testid="stFileUploaderDropzone"] button {{ font-size:0 !important; position:relative; }}
        [data-testid="stFileUploaderDropzone"] button::after {{
            content:"Explorar"; font-size:13px; font-family:{MONO}; font-weight:700;
            letter-spacing:.06em; text-transform:uppercase; }}

        /* ── Cápsula que encierra los resultados (marco metálico sutil, distinto del fondo) ── */
        div[class*="st-key-results-capsule"] {{
            background: rgba(9,12,17,.45); border: 1px solid rgba(255,184,77,.16);
            border-radius: 22px; padding: 10px 16px 16px; margin-top: 16px;
            box-shadow: inset 0 1px 0 rgba(255,184,77,.06), 0 10px 40px rgba(0,0,0,.35); }}

        /* ── Sub-cards del builder (dona + "En tu portafolio"): metálico más claro ── */
        div[class*="st-key-donutcard_"], div[class*="st-key-holdings_"] {{
            background: linear-gradient(150deg, #212A3B 0%, #171F2E 100%);
            border: 1px solid rgba(255,184,77,.16); border-radius: 14px; padding: 12px 16px;
            box-shadow: 0 6px 20px rgba(0,0,0,.36), inset 0 1px 0 rgba(255,255,255,.06); }}
        div[class*="st-key-holdings_"] {{ margin-top: 14px; }}

        /* ── Buscador de activos: campo + tarjetas de resultado clickeables ── */
        div[class*="st-key-q_"] input {{
            background:{BG_CARD2} !important; border:1.5px solid rgba(255,184,77,.35) !important;
            border-radius:11px !important; height:50px !important; font-family:{MONO} !important;
            font-size:15px !important; }}
        div[class*="st-key-q_"] input:focus {{ border-color:{ORANGE} !important;
            box-shadow:0 0 0 3px rgba(255,184,77,.15) !important; }}
        div[class*="st-key-searchres_"] {{ margin:6px 0 2px; }}
        div[class*="st-key-add_"] button {{
            width:100% !important; text-align:left !important; justify-content:flex-start !important;
            background:{BG_CARD2} !important; border:1px solid {BORDER} !important;
            border-radius:11px !important; padding:10px 14px !important; margin-bottom:6px !important;
            font-family:{FONT_FAMILY} !important; font-weight:400 !important; text-transform:none !important;
            letter-spacing:0 !important; color:{TEXT_LO} !important; font-size:12.5px !important;
            transition: transform .16s var(--dlp-ease-out), border-color .16s var(--dlp-ease-out),
                        box-shadow .16s var(--dlp-ease-out) !important; }}
        div[class*="st-key-add_"] button:hover {{ transform: scale(1.02) !important;
            border-color:{ORANGE} !important; box-shadow:0 0 18px rgba(255,184,77,.22) !important; }}
        div[class*="st-key-add_"] button p {{ margin:0 !important; }}
        div[class*="st-key-add_"] button strong {{ color:{TEXT_HI} !important; font-family:{MONO} !important;
            font-size:16px !important; font-weight:800 !important; margin-right:6px; }}

        /* ── Tabs con fondo + borde distinto (portafolios 1/2 y resultados) ── */
        .stTabs [data-baseweb="tab"] {{ background:{BG_CARD} !important; border:1px solid {BORDER} !important;
            border-bottom:none !important; border-radius:10px 10px 0 0 !important;
            padding:9px 18px !important; margin-right:3px !important; }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background:{METAL_BG} !important; border-color:{GOLD_HOVER} !important;
            color:{ORANGE} !important; box-shadow:0 -3px 16px rgba(255,184,77,.12); }}

        /* ── Slider de horizonte: grueso, protagonista, con glow dorado ── */
        .stSlider [data-baseweb="slider"] {{ padding-top:12px !important; padding-bottom:2px !important; }}
        .stSlider [data-baseweb="slider"] > div {{ height:10px !important; border-radius:6px !important; }}
        .stSlider [data-baseweb="slider"] div[role="slider"] {{
            height:28px !important; width:28px !important;
            background:{ORANGE} !important; border:3px solid #FFE9B8 !important;
            box-shadow:0 0 0 6px rgba(255,184,77,.16), 0 0 22px rgba(255,184,77,.55),
                       0 3px 12px rgba(0,0,0,.6) !important; }}
        [data-testid="stSliderThumbValue"] {{ color:{ORANGE} !important; font-family:{MONO} !important;
            font-weight:800 !important; font-size:15px !important; }}

        /* ── Reduced motion (Apple/accesibilidad): sin movimiento vestibular ────
           colapsa bucles perpetuos y quita los desplazamientos de hover/entrada,
           conservando los cambios de opacidad/color que ayudan a comprender. */
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: .001ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: .05ms !important;
            }}
            .dlp-card:hover, .dlp-kpi:hover, .dlp-side-item:hover, .dlp-tk:hover,
            button[data-testid^="stBaseButton-primary"]:hover,
            button[data-testid^="stBaseButton-secondary"]:hover,
            div.st-key-addb button:hover,
            div.st-key-pdfgo button:hover, div.st-key-pdfdl button:hover {{ transform: none !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
