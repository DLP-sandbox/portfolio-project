"""Sistema de diseño DLP — paleta exacta + CSS premium con animaciones.

Estética alineada a DLP Market Analyzer (app madre): tipografía mono en mayúsculas para
los títulos/labels, hero dorado con glow, botones que brillan, pills de estado y
micro-animaciones de buen gusto (fade-up, pulse, shimmer). El cuerpo de texto largo
queda en Helvetica Neue para legibilidad.
"""
from __future__ import annotations

import streamlit as st

# ── Paleta (hex literales del spec — no aproximar) ───────────────────────────
BG_DEEP = "#080B0F"
BG_CARD = "#141920"
BG_CARD2 = "#1A2030"
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
TEXT_HI = "#FFFFFF"
TEXT_MD = "#E4E7EC"
TEXT_LO = "#7A8898"
TEXT_DIM = "#5A6878"
BORDER = "#1E2530"

FONT_FAMILY = "Helvetica Neue, Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, 'SF Mono', 'Roboto Mono', monospace"


def color_for_percentile(kind: str) -> str:
    return {"median": ORANGE, "optimistic": GREEN, "pessimistic": RED}[kind]


def inject_css() -> None:
    """Inyecta el CSS global premium. Llamar una vez al inicio de app.py."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&display=swap');

        /* ── Animaciones ──────────────────────────────────────── */
        @keyframes dlpFadeUp {{ from {{opacity:0; transform:translateY(16px);}} to {{opacity:1; transform:translateY(0);}} }}
        @keyframes dlpBreathe {{ 0%,100% {{opacity:.55;}} 50% {{opacity:1;}} }}
        @keyframes dlpPulse {{
            0%,100% {{ box-shadow:0 0 0 1px rgba(255,184,77,.5), 0 8px 28px rgba(255,165,0,.22); }}
            50% {{ box-shadow:0 0 0 1px rgba(255,184,77,.85), 0 12px 44px rgba(255,165,0,.45); }}
        }}
        @keyframes dlpShimmer {{ 0% {{background-position:0% 50%;}} 100% {{background-position:200% 50%;}} }}
        @keyframes dlpSpin {{ from {{transform:rotate(45deg);}} to {{transform:rotate(405deg);}} }}

        /* ── Base ─────────────────────────────────────────────── */
        .stApp {{ background:
            radial-gradient(1200px 500px at 50% -200px, rgba(255,184,77,.06), rgba(8,11,15,0) 60%),
            {BG_DEEP}; font-family: {FONT_FAMILY}; }}
        /* Embed cuadrado 1:1 (~800px): contenido centrado y compacto */
        .block-container {{ padding-top: .8rem; padding-bottom: 2rem; max-width: 780px;
            animation: dlpFadeUp .5s ease both; }}
        section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{ display: none !important; }}
        h1, h2, h3, h4, h5 {{
            font-family: {MONO} !important; color: {TEXT_HI};
            text-transform: uppercase; letter-spacing: .06em; font-weight: 700;
        }}
        #MainMenu, footer {{ visibility: hidden; }}
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}

        /* ── Hero de página ───────────────────────────────────── */
        .dlp-page-hero {{ position: relative; text-align: center; padding: 8px 0 4px; }}
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
        .dlp-page-hero .title {{
            font-family:{MONO}; font-weight:800; font-size:38px; line-height:1.0;
            text-transform:uppercase; letter-spacing:.01em; margin: 2px 0 6px;
            background: linear-gradient(90deg, #FFE7A8 0%, #FFB84D 40%, #FFA500 60%, #FFE7A8 100%);
            background-size: 200% auto; -webkit-background-clip:text; background-clip:text;
            -webkit-text-fill-color:transparent;
            filter: drop-shadow(0 4px 26px rgba(255,184,77,.22));
            animation: dlpShimmer 7s linear infinite;
        }}
        .dlp-page-hero .sub {{
            font-family:{MONO}; color:{TEXT_LO}; text-transform:uppercase;
            letter-spacing:.28em; font-size:13px;
        }}
        .dlp-rule {{ height:1px; max-width:120px; margin:14px auto 6px;
            background: linear-gradient(90deg, transparent, {ORANGE}, transparent); }}

        /* ── Stepper ──────────────────────────────────────────── */
        .dlp-steps {{ display:flex; gap:12px; justify-content:center; margin:14px 0 20px; flex-wrap:wrap; }}
        .dlp-step {{
            display:flex; align-items:center; gap:10px; padding:9px 18px; border-radius:12px;
            background:{BG_CARD}; border:1px solid {BORDER}; font-family:{MONO};
            font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:{TEXT_LO};
            transition: all .25s ease;
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
            border-radius:8px; padding:9px 12px; margin-bottom:8px; transition: all .18s ease; }}
        .dlp-side-item:hover {{ border-color:rgba(255,184,77,.4); transform: translateX(2px); }}
        .dlp-side-item .lbl {{ color:{TEXT_MD}; font-size:13px; font-weight:600; }}
        .dlp-side-item .meta {{ color:{TEXT_LO}; font-size:11px; margin-top:2px; }}

        /* ── Cards ────────────────────────────────────────────── */
        .dlp-card {{ background:{BG_CARD}; border:1px solid {BORDER}; border-radius:14px;
            padding:20px 22px; margin-bottom:16px; transition: all .18s ease;
            animation: dlpFadeUp .45s ease both; }}
        .dlp-card:hover {{ border-color: rgba(255,184,77,.30); transform: translateY(-2px); }}
        .dlp-card2 {{ background:{BG_CARD2}; }}
        .dlp-card-left {{ border-left:5px solid {ORANGE}; }}

        /* ── Hero card (resultados) ───────────────────────────── */
        .dlp-hero {{ background:
            radial-gradient(700px 200px at 0% 0%, rgba(255,184,77,.06), rgba(20,25,32,0) 60%), {BG_CARD};
            border:1px solid {ORANGE}; border-radius:16px; padding:26px 30px; margin-bottom:18px;
            display:flex; align-items:center; justify-content:space-between;
            box-shadow:0 0 50px rgba(255,184,77,.07); animation: dlpFadeUp .5s ease both; }}
        .dlp-hero .glyph {{ font-size:74px; font-weight:800; line-height:1; font-family:{MONO};
            background:linear-gradient(135deg,{ORANGE},{ORANGE_DK}); -webkit-background-clip:text;
            -webkit-text-fill-color:transparent; background-clip:text;
            filter: drop-shadow(0 0 18px rgba(255,184,77,.35)); }}
        .dlp-hero .meta-label {{ color:{TEXT_LO}; font-family:{MONO}; font-size:11px;
            text-transform:uppercase; letter-spacing:.10em; }}
        .dlp-hero .meta-value {{ color:{TEXT_HI}; font-size:20px; font-weight:700; }}

        /* ── KPI tile ─────────────────────────────────────────── */
        .dlp-kpi {{ position:relative; background:{BG_CARD}; border:1px solid {BORDER};
            border-radius:12px; padding:22px 18px 18px; min-height:150px; overflow:hidden;
            transition: all .18s ease; animation: dlpFadeUp .45s ease both; }}
        .dlp-kpi:hover {{ transform: translateY(-3px); border-color: rgba(255,184,77,.25); }}
        .dlp-kpi .accent {{ position:absolute; top:0; left:0; right:0; height:5px; }}
        .dlp-kpi .kpi-label {{ color:{TEXT_LO}; font-family:{MONO}; font-size:12px; font-weight:700;
            text-transform:uppercase; letter-spacing:.10em; }}
        .dlp-kpi .kpi-value {{ font-family:{MONO}; font-size:36px; font-weight:800; line-height:1.15;
            margin:10px 0 4px; }}
        .dlp-kpi .kpi-sub {{ color:{TEXT_LO}; font-size:13px; }}

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
        button[data-testid^="stBaseButton-primary"] {{
            background: linear-gradient(180deg, #FFD884 0%, {ORANGE} 50%, {ORANGE_DK} 100%) !important;
            color:#1A1206 !important; font-family:{MONO} !important; font-weight:800 !important;
            text-transform:uppercase; letter-spacing:.10em; border:none !important;
            border-radius:12px !important; padding:14px 20px !important;
            box-shadow:0 0 0 1px rgba(255,184,77,.5), 0 8px 28px rgba(255,165,0,.22) !important;
            animation: dlpPulse 2.8s ease-in-out infinite; transition: transform .16s ease;
        }}
        button[data-testid^="stBaseButton-primary"]:hover {{ transform: translateY(-2px); }}
        button[data-testid^="stBaseButton-primary"]:disabled {{
            background:{BG_CARD2} !important; color:{TEXT_DIM} !important;
            box-shadow:none !important; animation:none; opacity:1 !important;
            border:1px dashed {BORDER} !important;
        }}
        button[data-testid^="stBaseButton-secondary"] {{
            background:{BG_CARD2} !important; color:{TEXT_MD} !important;
            border:1px solid {BORDER} !important; border-radius:10px !important;
            font-family:{MONO} !important; font-weight:700 !important; letter-spacing:.06em;
            text-transform:uppercase; transition: all .16s ease;
        }}
        button[data-testid^="stBaseButton-secondary"]:hover {{
            border-color:{ORANGE} !important; color:{ORANGE} !important; transform: translateY(-1px); }}

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
            background: linear-gradient(180deg, #151A22 0%, #10151B 100%);
            border: 1px solid {BORDER}; border-radius: 18px;
            padding: 10px 26px 22px; margin-bottom: 18px;
            box-shadow: 0 14px 44px rgba(0,0,0,.38);
            transition: border-color .2s ease;
        }}
        div[class*="st-key-card-"]:hover {{ border-color: rgba(255,184,77,.20); }}
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
            transition: all .15s ease; }}
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
        div.st-key-addb button:hover {{ background: rgba(74,158,255,.18) !important;
            transform: translateY(-1px); }}

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
            overflow:hidden; }}
        .dlp-vsm .m-fill {{ height:100%; border-radius:8px; }}
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
            animation: dlpPulse 2.4s ease-in-out infinite; transition: transform .16s ease; }}
        div.st-key-pdfgo button:hover, div.st-key-pdfdl button:hover {{ transform: translateY(-2px); }}
        </style>
        """,
        unsafe_allow_html=True,
    )
