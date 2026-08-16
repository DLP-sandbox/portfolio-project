"""Sistema de diseño DLP — mismos tokens que L-DLP-Analysis-CLIENTES.

Filosofía heredada de la app madre: "Obsidiana + oro antiguo — los neutros hacen el 90%
del trabajo, un solo acento usado con avaricia, verde/rojo SOLO con significado
financiero". La elevación se logra con capas de superficie (no con bordes), las líneas
son hairlines de bajísimo contraste y el movimiento es corto y sin neón. Inter para la
interfaz, JetBrains Mono (con tabular-nums) para las cifras.

Los NOMBRES de las constantes se mantienen estables: todo el resto de la app
(app.py, charts.py, components.py, pdf_report.py) hereda la estética por referencia.
"""
from __future__ import annotations

import streamlit as st

# ── Superficies: elevación por capas de fondo ───────────────────────────────
BG_DEEP = "#0A0B0D"      # --bg
BG_SUNK = "#0D0F12"      # --surface-0 (zonas hundidas)
BG_CARD = "#101216"      # --surface-1 (cards base, fondo de gráficas)
BG_CARD2 = "#15181D"     # --surface-2 (elevado / hover)
BG_ELEV = "#1B1F25"      # --surface-3 (nivel más alto: tooltips, popovers)
BG_CTA = "#101216"

# ── Acento único: oro antiguo (calmo, caro) ─────────────────────────────────
ORANGE = "#E2B25C"       # --accent
GOLD = "#F0C878"         # --accent-hi
ORANGE_DK = "#C08E3B"    # --accent-deep
GOLD_DEEP = "#C08E3B"

# ── Semánticos: exclusivos para significado financiero ──────────────────────
GREEN = "#3DD68C"        # --pos
GREEN_DK = "#2FB675"
RED = "#F1495F"          # --neg
RED_DK = "#D13C50"
BLUE = "#6FA3E0"         # --info
BLUE_DK = "#5588C4"

# Aviso legal del pie (tarjeta azul oscuro con letra gris pequeña)
LEGAL_BG = "#0C1826"     # azul noche, se apoya sobre el fondo sin gritar
LEGAL_EDGE = "rgba(111,163,224,0.20)"
LEGAL_LBL = "#7E8794"    # "AVISO:" un punto más claro para que se lea primero
LEGAL_TXT = "#6B7481"    # gris oscuro: discreto pero legible sobre el azul
PURPLE = "#9D8CE0"       # --purple (dato categórico)

# ── Serie categórica de DATOS (no de UI) ─────────────────────────────────────
# Validada con el validador del skill dataviz contra la superficie #101216
# (banda OKLCH 0.48–0.67, separación CVD y visión normal, contraste ≥3:1).
# ORDEN DOCUMENTADO del skill: NO reordenar sin re-validar — el orden es el
# mecanismo de seguridad para daltonismo, no cosmética.
SERIES = ["#3987E5", "#D95926", "#199E70", "#C98500", "#D55181", "#008300", "#9085E9", "#E66767"]
SERIES_A = "#C98500"     # oro de marca re-escalonado a la banda oscura → identidad portafolio A
SERIES_B = "#3987E5"     # azul → portafolio B
SERIES_C = "#D55181"     # magenta → portafolio C (púrpura vs azul falla all-pairs: ΔE 9,8)
SERIES_OTROS = "#5E6570" # cola agrupada de la dona
BENCH_NEUTRAL = "#8D949E"  # benchmark S&P: es referencia, no competidor — gris con guiones


# ── Texto: rampa de 4 pasos (se acabó la sopa de grises) ────────────────────
TEXT_HI = "#F2F3F5"      # --text-hi
TEXT_MD = "#C9CDD3"      # --text
TEXT_SOFT = "#C9CDD3"
TEXT_LO = "#8D949E"      # --text-2
TEXT_DIM = "#5E6570"     # --text-3

# ── Líneas: hairlines de bajísimo contraste, nunca gris puro ────────────────
BORDER = "#232830"       # --border-solid
BORDER_SOFT = "#232830"
HAIRLINE = "rgba(255,255,255,0.06)"
HAIRLINE_2 = "rgba(255,255,255,0.10)"
# Se conservan los nombres GOLD_* (los consume el CSS) pero ahora son hairlines
# neutros o acento muy diluido: el oro se usa con avaricia.
GOLD_HAIR = "rgba(255,255,255,0.06)"
GOLD_LINE = "rgba(255,255,255,0.06)"
GOLD_EDGE = "rgba(255,255,255,0.10)"
GOLD_HOVER = "rgba(226,178,92,0.35)"

# Gridlines de las gráficas: rejilla casi invisible (Tufte)
GRID_HAIR = "rgba(255,255,255,0.05)"
GRID_ZERO = "rgba(255,255,255,0.08)"

# Fondo plano + un único lavado de oro casi imperceptible arriba (ver inject_css)
APP_BG = BG_DEEP
CARD_BG = BG_CARD
# "METAL_*" conserva el nombre por compatibilidad, pero ya no es metálico: es la
# superficie-1 con brillo interior superior (una sola luz cenital).
METAL_BG = BG_CARD
METAL_BORDER = HAIRLINE
METAL_SHADOW = "0 4px 14px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)"

# Sombras y radios del sistema
SHADOW_1 = "0 1px 2px rgba(0,0,0,0.35)"
SHADOW_2 = "0 4px 14px rgba(0,0,0,0.35)"
SHADOW_3 = "0 16px 40px rgba(0,0,0,0.5)"
INSET_HI = "inset 0 1px 0 rgba(255,255,255,0.04)"
R_XS, R_SM, R_MD, R_LG = "4px", "6px", "10px", "14px"

FONT_FAMILY = "'Inter', -apple-system, 'Segoe UI', system-ui, sans-serif"
MONO = "'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace"


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

        /* ═══ DESIGN TOKENS — espejo exacto de L-DLP-Analysis-CLIENTES ═══════
           Obsidiana + oro antiguo: los neutros hacen el 90% del trabajo, un solo
           acento usado con avaricia, verde/rojo SOLO con significado financiero. */
        :root {{
            --bg: {BG_DEEP};
            --surface-0: {BG_SUNK}; --surface-1: {BG_CARD};
            --surface-2: {BG_CARD2}; --surface-3: {BG_ELEV};
            --hairline: {HAIRLINE}; --hairline-2: {HAIRLINE_2}; --border-solid: {BORDER};
            --text-hi: {TEXT_HI}; --text: {TEXT_MD}; --text-2: {TEXT_LO}; --text-3: {TEXT_DIM};
            --accent: {ORANGE};      --accent-rgb: 226,178,92;
            --accent-hi: {GOLD};     --accent-hi-rgb: 240,200,120;
            --accent-deep: {ORANGE_DK};
            --pos: {GREEN};  --pos-rgb: 61,214,140;
            --neg: {RED};    --neg-rgb: 241,73,95;
            --info: {BLUE};  --info-rgb: 111,163,224;
            --purple: {PURPLE};
            --r-xs: {R_XS}; --r-sm: {R_SM}; --r-md: {R_MD}; --r-lg: {R_LG};
            --shadow-1: {SHADOW_1}; --shadow-2: {SHADOW_2}; --shadow-3: {SHADOW_3};
            --inset-hi: {INSET_HI};
            --dlp-ease-out: cubic-bezier(0.23, 1, 0.32, 1);
            --dlp-ease-io:  cubic-bezier(0.77, 0, 0.175, 1);
            --dur-1: 120ms; --dur-2: 180ms; --dur-3: 240ms;
        }}

        [data-testid="stVerticalBlock"] {{ gap: .7rem; }}

        /* ── Animaciones: sin neón, con física ─────────────────── */
        @keyframes dlpFadeUp {{ from {{opacity:0; transform:translateY(10px);}} to {{opacity:1; transform:translateY(0);}} }}
        @keyframes dlpFadeIn {{ from {{opacity:0;}} to {{opacity:1;}} }}
        @keyframes dlpBreathe {{ 0%,100% {{opacity:1;}} 50% {{opacity:.86;}} }}
        @keyframes dlpPulseGlow {{ 0%,100% {{opacity:1;}} 50% {{opacity:.86;}} }}
        @keyframes dlpPulse {{
            0%,100% {{ box-shadow:0 0 0 1px rgba(var(--accent-rgb),.22); }}
            50%     {{ box-shadow:0 0 0 1px rgba(var(--accent-rgb),.40); }}
        }}
        @keyframes dlpShimmer {{ 0% {{background-position:-200% 0;}} 100% {{background-position:200% 0;}} }}
        @keyframes dlpSpin {{ from {{transform:rotate(45deg);}} to {{transform:rotate(405deg);}} }}
        @keyframes dlpScanLine {{ 0% {{transform:translateX(-100%);}} 100% {{transform:translateX(100%);}} }}

        /* ── Base ─────────────────────────────────────────────── */
        html, body {{ background: var(--bg) !important; }}
        /* Lienzo raíz: fondo + cuadrícula de puntos (textura de terminal). Al ser el
           background del propio lienzo, vive en la capa MÁS BAJA: tarjetas, gráficas,
           menús y cualquier elemento con fondo la tapan por naturaleza — los puntos
           solo se ven donde de verdad hay fondo vacío. */
        [data-testid="stAppViewContainer"] {{
            background-color: var(--bg) !important;
            background-image: radial-gradient(circle,
                rgba(255, 255, 255, 0.10) 1.2px, transparent 1.35px) !important;
            background-size: 17px 17px !important;
            background-attachment: fixed !important;
        }}
        /* .stApp no debe pintar fondo opaco: taparía la cuadrícula del lienzo. */
        .stApp {{ background: transparent !important; }}
        html, body, [data-testid="stAppViewContainer"] {{
            color: var(--text) !important;
            font-family: {FONT_FAMILY} !important;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
        }}
        /* Un único lavado de oro casi imperceptible en la parte superior */
        [data-testid="stAppViewContainer"]::before {{
            content: ''; position: fixed; top: -30vh; left: 50%;
            width: 120vw; height: 60vh; transform: translateX(-50%);
            background: radial-gradient(ellipse at center, rgba(var(--accent-rgb),0.035) 0%, transparent 65%);
            pointer-events: none; z-index: 0;
        }}
        ::selection {{ background: rgba(var(--accent-rgb),0.28); color: var(--text-hi); }}
        :focus-visible {{ outline: 2px solid rgba(var(--accent-rgb),0.55) !important; outline-offset: 2px !important; }}
        /* Cifras que no bailan */
        .kpi-value, .kpi-meter-word, .dlp-hero-v2 .hero-number, .dlp-side .big,
        .dlp-cmp td, .dlp-vsm .m-val, [data-testid="stMetricValue"] {{
            font-variant-numeric: tabular-nums; font-feature-settings: "tnum";
        }}
        [data-testid="stMain"] {{ background: transparent !important; }}
        /* fill-mode "backwards" (no "both"): con "both" el transform final quedaba
           aplicado PARA SIEMPRE y eso convierte al contenedor en el marco de referencia
           de cualquier position:fixed hijo — el loader dejaba de anclarse a la pantalla
           y scrolleaba con la página. "backwards" da una entrada idéntica frame a frame,
           pero al terminar suelta el transform y el overlay queda fijo de verdad
           (mismo comportamiento que DLP Analyzer, cuyo contenedor no se anima). */
        .block-container {{ padding-top: .45rem; padding-bottom: 1rem; max-width: 1240px;
            padding-left: 1.25rem; padding-right: 1.25rem;
            animation: dlpFadeUp var(--dur-3) var(--dlp-ease-out) backwards; }}
        section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{ display: none !important; }}
        /* Titulares en Inter, sentence-case (fuera el uppercase mono generalizado) */
        h1, h2, h3, h4, h5 {{
            font-family: {FONT_FAMILY} !important; color: var(--text-hi);
            text-transform: none; letter-spacing: -0.01em; font-weight: 600;
        }}
        #MainMenu, footer, header {{ visibility: hidden; display: none !important; }}
        [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}

        /* ── Scrollbar ────────────────────────────────────────── */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg); }}
        ::-webkit-scrollbar-thumb {{ background: var(--surface-3); border-radius: var(--r-xs); }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(var(--accent-rgb),0.35); }}

        /* ── Divisores: hairline neutro ───────────────────────── */
        hr {{ border-color: var(--hairline) !important; margin: 16px 0 !important; }}

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
            background: {CARD_BG}; border: 1px solid rgba(var(--accent-rgb),.30); border-radius: 20px;
            padding: 36px 48px;
            box-shadow: 0 24px 70px rgba(0,0,0,.65), 0 0 0 1px rgba(var(--accent-rgb),.08),
                        0 0 70px rgba(var(--accent-rgb),.14);
        }}
        .dlp-loader-ring {{
            width: 150px; height: 150px; border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 48px rgba(var(--accent-rgb),.30); transition: background .12s linear;
        }}
        .dlp-loader-hole {{
            width: 116px; height: 116px; border-radius: 50%; background: {BG_DEEP};
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }}
        .dlp-loader-hole .pct {{ font-family: {MONO}; font-size: 34px; font-weight: 800; color: {ORANGE};
            filter: drop-shadow(0 0 12px rgba(var(--accent-rgb),.4)); }}
        .dlp-loader-hole .lbl {{ font-family: {MONO}; font-size: 10px; letter-spacing: .20em;
            color: {TEXT_LO}; margin-top: 3px; }}
        .dlp-loader-msg {{ font-family: {MONO}; text-transform: uppercase; letter-spacing: .14em;
            color: {TEXT_MD}; font-size: 13px; animation: dlpBreathe 2.4s ease-in-out infinite; }}

        /* ── Hero de página (mismo tratamiento que .alpha-hero) ─ */
        .dlp-page-hero {{ position: relative; text-align: center; padding: 10px 0 2px;
            margin-bottom: 4px; animation: dlpFadeUp .8s ease-out both; }}
        .dlp-page-hero .glow {{
            position:absolute; top:-30px; left:50%; transform:translateX(-50%);
            width:min(640px, 72vw); height:230px; pointer-events:none; filter: blur(18px);
            background: radial-gradient(ellipse at center, rgba(var(--accent-rgb),.20), rgba(var(--accent-rgb),0) 70%);
            animation: dlpBreathe 4.5s ease-in-out infinite;
        }}
        .dlp-page-hero .diamond {{
            color:{GOLD}; font-size:21px; line-height:1; display:inline-block;
            filter: drop-shadow(0 0 14px rgba(var(--accent-hi-rgb),.6)); margin-bottom: 4px;
        }}
        /* Título METÁLICO: degradado oro sobre el propio texto (patrón alpha-hero-brand) */
        .dlp-page-hero .title {{
            font-family:{FONT_FAMILY}; font-weight:750; font-size:37px; line-height:1.08;
            letter-spacing:-0.02em; margin: 4px 0 8px;
            background: linear-gradient(160deg, #F7E3B4 0%, {GOLD} 30%, {ORANGE} 62%, {ORANGE_DK} 100%);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            filter: drop-shadow(0 2px 14px rgba(var(--accent-rgb),.28));
        }}
        .dlp-page-hero .sub {{
            font-family:{FONT_FAMILY}; color:var(--text-2); font-size:14px; font-weight:400;
        }}
        .dlp-rule {{ height:1px; max-width:120px; margin:14px auto 4px;
            background: linear-gradient(90deg, transparent, {ORANGE}, transparent);
            box-shadow: 0 0 10px rgba(var(--accent-rgb),.5); }}

        /* ── Hero de resultados (v2): monto grande centrado, meta distribuida ── */
        .dlp-hero-v2 {{ text-align:center; background:
            radial-gradient(600px 220px at 50% -40px, rgba(var(--accent-rgb),.10), rgba(0,0,0,0) 70%), {METAL_BG};
            border:1px solid {ORANGE}; border-radius:18px; padding:24px 30px 20px; margin-bottom:18px;
            box-shadow: {METAL_SHADOW}, 0 0 50px rgba(var(--accent-rgb),.10);
            animation: dlpFadeUp .5s var(--dlp-ease-out) both; }}
        .dlp-hero-v2 .hero-top {{ font-family:{MONO}; text-transform:uppercase; letter-spacing:.14em;
            font-size:11.5px; color:{TEXT_LO}; }}
        .dlp-hero-v2 .hero-top .hero-glyph {{ color:{GOLD}; filter:drop-shadow(0 0 8px rgba(var(--accent-hi-rgb),.5)); }}
        .dlp-hero-v2 .hero-number {{ font-family:{MONO}; font-weight:800; line-height:1.02;
            font-size:clamp(38px, 8.5vw, 60px); margin:6px 0 2px;
            filter: drop-shadow(0 4px 26px rgba(var(--accent-rgb),.22)); }}
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
            box-shadow: {METAL_SHADOW}, 0 0 26px rgba(var(--accent-rgb),.07); }}
        .dlp-card2 {{ background:{BG_CARD2}; }}
        /* Acento izquierdo dorado — igual que .analysis-card / .agent-header */
        .dlp-card-left {{ border-left:3px solid {ORANGE}; }}

        /* ── KPI tile (stat tile): superficie metálica + borde dorado + termómetro + "?" ── */
        .dlp-kpi {{ position:relative; display:flex; flex-direction:column;
            background:var(--surface-1); border:1px solid var(--hairline); border-radius:var(--r-md);
            padding:16px 17px 15px; min-height:178px; height:100%; overflow:visible;
            box-shadow: var(--inset-hi);
            transition: transform .2s var(--dlp-ease-out), border-color .2s var(--dlp-ease-out),
                        box-shadow .2s var(--dlp-ease-out);
            animation: dlpFadeUp .45s var(--dlp-ease-out) both; }}
        .dlp-kpi:hover {{ transform: translateY(-2px); border-color: var(--hairline-2);
            box-shadow: var(--shadow-2), var(--inset-hi); }}
        .dlp-kpi .accent {{ position:absolute; top:0; left:0; right:0; height:4px;
            border-radius:13px 13px 0 0; opacity:.95; }}
        .dlp-kpi .kpi-head {{ display:flex; align-items:center; gap:8px; }}
        .dlp-kpi .kpi-label {{ color:var(--text-2); font-family:{FONT_FAMILY}; font-size:12px; font-weight:500;
            text-transform:none; letter-spacing:0; line-height:1.25; flex:1; min-width:0; }}
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
            width:17px; height:17px; border-radius:50%; background:rgba(var(--accent-rgb),.10);
            border:1px solid rgba(var(--accent-rgb),.45); color:{ORANGE}; font-size:11px; font-weight:800;
            font-family:{FONT_FAMILY}; cursor:help; position:relative; flex-shrink:0;
            transition: all .2s var(--dlp-ease-out); }}
        .dlp-kpi-help:hover {{ background:rgba(var(--accent-rgb),.22); border-color:{ORANGE}; color:{GOLD};
            transform:scale(1.12); }}
        .dlp-kpi-help::after {{ content:attr(data-tooltip); position:absolute; bottom:calc(100% + 9px);
            right:-6px; background:linear-gradient(135deg,{BG_CARD2},{BG_ELEV}); color:{TEXT_MD};
            padding:11px 13px; border-radius:9px; border:1px solid rgba(var(--accent-rgb),.35);
            border-bottom:2px solid {ORANGE}; white-space:normal; width:238px; font-size:12.5px;
            font-weight:400; font-family:{FONT_FAMILY}; line-height:1.5; letter-spacing:0;
            text-transform:none; text-align:left; z-index:9999; pointer-events:none;
            box-shadow:0 12px 32px rgba(0,0,0,.7);
            opacity:0; transform:translateY(4px); transition: opacity .2s ease, transform .2s ease; }}
        .dlp-kpi-help:hover::after {{ opacity:1; transform:translateY(0); }}

        /* ── Disclaimer ───────────────────────────────────────── */
        /* ═══ EL ARMADOR ES EL PROTAGONISTA ══════════════════════════════ */
        div[class*="st-key-card-portafolio"] {{
            background: linear-gradient(180deg, rgba(var(--accent-rgb),.075) 0%,
                                                rgba(var(--accent-rgb),.02) 46%, #0E1014 100%) !important;
            border: 1px solid rgba(var(--accent-rgb),.30) !important;
            box-shadow: {INSET_HI}, 0 8px 30px rgba(0,0,0,.45),
                        0 0 40px rgba(var(--accent-rgb),.07) !important;
        }}
        /* La dona vive en un panel-instrumento hundido con halo dorado */
        div[class*="st-key-donutcard_"] {{
            background: radial-gradient(ellipse at 50% 38%, #0B0D11 0%, #07080B 100%) !important;
            border: 1px solid rgba(var(--accent-rgb),.22) !important; border-radius: 14px !important;
            padding: 10px 12px !important;
            box-shadow: inset 0 2px 14px rgba(0,0,0,.55), 0 0 26px rgba(var(--accent-rgb),.08) !important;
        }}
        /* Filas de activos: sub-panel hundido, hairline entre filas */
        div[class*="st-key-holdings_"] {{
            background: {BG_SUNK} !important; border: 1px solid {HAIRLINE_2} !important;
            border-radius: 12px !important; padding: 10px 14px !important; margin-top: 10px !important;
            box-shadow: {INSET_HI} !important;
        }}
        /* Montos en mono dorado: se leen como dinero */
        div[class*="st-key-pw_"] input {{
            font-family: {MONO} !important; font-weight: 700 !important;
            color: {GOLD} !important; letter-spacing: .02em;
        }}
        /* Buscador: foco con anillo dorado */
        div[class*="st-key-q_"] input:focus {{
            border-color: rgba(var(--accent-rgb),.65) !important;
            box-shadow: 0 0 0 3px rgba(var(--accent-rgb),.18), 0 0 18px rgba(var(--accent-rgb),.15) !important;
        }}

        /* Ring-stat: anillo conic con glow, DENTRO del panel-instrumento (mismo
           tratamiento que las donas: fondo hundido, borde dorado, reflejo). */
        .dlp-ring-stat {{ padding: 12px 14px 10px; position: relative;
            background: radial-gradient(ellipse at 50% 32%, #0B0D11 0%, #07080B 100%);
            border: 1px solid rgba(var(--accent-rgb),.22); border-radius: 14px;
            box-shadow: inset 0 2px 14px rgba(0,0,0,.55), 0 0 26px rgba(var(--accent-rgb),.08); }}
        .dlp-ring-stat::after {{
            content:""; position:absolute; top:0; left:6%; width:88%; height:36%;
            border-radius: 14px 14px 50% 50%;
            background: radial-gradient(ellipse at 50% 0%,
                rgba(255,255,255,.05) 0%, rgba(255,255,255,0) 72%);
            pointer-events:none; }}
        .dlp-ring-stat .rs-wrap {{ position: relative; }}
        .dlp-ring-stat .rs-wrap::before {{
            content:""; position:absolute; left:50%; top:50%;
            width:150px; height:150px; transform:translate(-50%,-50%);
            border-radius:50%;
            border:1px solid rgba(var(--accent-rgb),.50);
            box-shadow: 0 0 22px rgba(var(--accent-rgb),.30),
                        0 0 3px rgba(var(--accent-hi-rgb),.55);
            pointer-events:none; }}
        .dlp-ring-stat .rs-label {{ color:{TEXT_LO}; font-family:{MONO}; font-size:10.5px;
            font-weight:700; text-transform:uppercase; letter-spacing:.12em; }}
        .dlp-ring-stat .rs-wrap {{ display:flex; justify-content:center; margin:12px 0 8px; }}
        .dlp-ring-stat .rs-ring {{ width:132px; height:132px; border-radius:50%;
            display:flex; align-items:center; justify-content:center;
            transition: background .3s linear; }}
        .dlp-ring-stat .rs-hole {{ width:102px; height:102px; border-radius:50%;
            background: radial-gradient(circle at 50% 42%, #101216 0%, #0A0B0D 100%);
            display:flex; align-items:center; justify-content:center;
            box-shadow: inset 0 2px 10px rgba(0,0,0,.6); }}
        .dlp-ring-stat .rs-value {{ font-family:{MONO}; font-weight:800; font-size:27px;
            letter-spacing:-0.02em; }}
        .dlp-ring-stat .rs-sub {{ color:{TEXT_LO}; font-size:11.5px; margin:2px 0 8px; text-align:center; }}
        .dlp-ring-stat .ms-meter {{ position:relative; height:12px; display:flex; align-items:center; }}
        .dlp-ring-stat .ms-meter::before {{ content:""; width:100%; height:6px; border-radius:99px;
            background: linear-gradient(90deg, {RED} 0%, #E5C05C 50%, {GREEN} 100%); opacity:.5; }}
        .dlp-ring-stat .ms-dot {{ position:absolute; top:50%; width:12px; height:12px;
            border-radius:50%; transform:translate(-50%,-50%); border:2px solid {BG_CARD}; }}
        .dlp-ring-stat .ms-ends {{ display:flex; justify-content:space-between;
            color:{TEXT_DIM}; font-family:{MONO}; font-size:9.5px; margin-top:3px;
            text-transform:uppercase; letter-spacing:.08em; }}

        /* ═══ DONA SOFISTICADA ═══════════════════════════════════════════
           Porciones que se EXPANDEN al hover (transform-box las escala desde su
           propio centro), con brillo; el contenedor lleva sombra clara + halo
           dorado + reflejo de vidrio; y el chart entra con scaleIn en CADA
           cambio de datos (añadir/quitar activo o cambiar montos re-monta el
           nodo → la animación se repite sola). */
        div[class*="st-key-donutcard_"] .js-plotly-plot {{
            filter: drop-shadow(0 10px 26px rgba(0,0,0,.55))
                    drop-shadow(0 0 20px rgba(var(--accent-rgb),.12));
            animation: dlpDonutIn .5s var(--dlp-ease-out) backwards;
        }}
        @keyframes dlpDonutIn {{
            from {{ opacity:0; transform: scale(.93) rotate(-4deg); }}
            to   {{ opacity:1; transform: scale(1) rotate(0deg); }}
        }}
        div[class*="st-key-donutcard_"] {{ position:relative; }}
        /* Reflejo de vidrio del panel (arriba, suave) */
        div[class*="st-key-donutcard_"]::after {{
            content:""; position:absolute; top:0; left:6%; width:88%; height:42%;
            border-radius: 14px 14px 50% 50%;
            background: radial-gradient(ellipse at 50% 0%,
                rgba(255,255,255,.05) 0%, rgba(255,255,255,0) 72%);
            pointer-events:none;
        }}
        /* Popup de las donas: la caja se mide a 13.5 y el texto se pinta a 11.5 →
           nunca vuelve a cortarse por alto ni por ancho, en ninguna porción. */
        div[class*="st-key-donut"] .hoverlayer .hovertext text,
        div[class*="st-key-vs_d"] .hoverlayer .hovertext text,
        div[class*="st-key-cand_compo_donut"] .hoverlayer .hovertext text {{
            font-size: 11.5px !important;
        }}

        /* ── ANILLOS DE LA DONA: borde exterior dorado con glow doble, borde
           interior en el filo del agujero, y un BARRIDO DE REFLEJO sobre la
           banda circular (conic blanco enmascarado al anillo). El pie mide
           Ø144px (height 200 − márgenes 28), agujero Ø≈89. ─────────────── */
        div[class*="st-key-donutcard_"] .js-plotly-plot {{ position:relative; }}
        div[class*="st-key-donutcard_"] .js-plotly-plot::before {{
            content:""; position:absolute; left:50%; top:50%;
            width:152px; height:152px; transform:translate(-50%,-50%);
            border-radius:50%;
            border:1px solid rgba(var(--accent-rgb),.50);
            box-shadow: 0 0 22px rgba(var(--accent-rgb),.30),
                        0 0 3px rgba(var(--accent-hi-rgb),.55),
                        inset 0 0 14px rgba(var(--accent-rgb),.12);
            pointer-events:none; z-index:4;
        }}
        div[class*="st-key-donutcard_"] .js-plotly-plot::after {{
            content:""; position:absolute; left:50%; top:50%;
            width:150px; height:150px; transform:translate(-50%,-50%);
            border-radius:50%;
            /* barrido de reflejo + filo interior del agujero (dos capas) */
            background:
                conic-gradient(from 215deg,
                    rgba(255,255,255,.14) 0deg, rgba(255,255,255,.03) 52deg,
                    rgba(255,255,255,0) 95deg, rgba(255,255,255,0) 300deg,
                    rgba(255,255,255,.08) 338deg, rgba(255,255,255,.14) 360deg),
                radial-gradient(circle, rgba(0,0,0,0) 0 42px,
                    rgba(var(--accent-hi-rgb),.35) 43px 44px, rgba(0,0,0,0) 45px);
            -webkit-mask: radial-gradient(circle,
                transparent 0 42px, #000 43px 74px, transparent 75px);
                    mask: radial-gradient(circle,
                transparent 0 42px, #000 43px 74px, transparent 75px);
            pointer-events:none; z-index:5;
        }}
        .stPlotlyChart g.slice path.surface {{
            transform-box: fill-box; transform-origin: center;
            /* Saturación contenida: elegancia de terminal, no videojuego */
            filter: saturate(.80) brightness(.94);
            transition: transform .16s var(--dlp-ease-out), filter .16s var(--dlp-ease-out);
        }}
        @media (hover: hover) and (pointer: fine) {{
            .stPlotlyChart g.slice:hover path.surface {{
                transform: scale(1.055);
                filter: saturate(.9) brightness(1.10) drop-shadow(0 0 12px rgba(255,255,255,.14));
            }}
        }}
        /* La barra apilada por tipo de activo, en el mismo registro apagado */
        div[class*="st-key-class_"] .js-plotly-plot {{ filter: saturate(.78) brightness(.95); }}

        /* ═══ BUSCADOR: borde ROTANDO con destello (conic + máscara de anillo) ═══ */
        @property --dlpang {{ syntax: "<angle>"; initial-value: 0deg; inherits: false; }}
        div[class*="st-key-q_"] {{ position:relative; border-radius:13px; }}
        div[class*="st-key-q_"]::before {{
            content:""; position:absolute; inset:-2px; border-radius:15px; padding:2px;
            background: conic-gradient(from var(--dlpang),
                rgba(var(--accent-rgb),0) 0deg,  rgba(var(--accent-rgb),0) 258deg,
                rgba(var(--accent-rgb),.55) 300deg, rgba(255,255,255,.9) 318deg,
                rgba(var(--accent-rgb),.55) 336deg, rgba(var(--accent-rgb),0) 360deg);
            -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
            -webkit-mask-composite: xor; mask-composite: exclude;
            animation: dlpRotBorder 4.6s linear infinite;
            pointer-events:none; z-index:1;
        }}
        @keyframes dlpRotBorder {{ to {{ --dlpang: 360deg; }} }}

        /* Panel-instrumento genérico (mismo lenguaje que la dona, sin anillos):
           sectores, tipo de activo y tacómetro de diversificación. */
        div[class*="st-key-instru_"] {{
            background: radial-gradient(ellipse at 50% 30%, #0B0D11 0%, #07080B 100%) !important;
            border: 1px solid rgba(var(--accent-rgb),.22) !important; border-radius: 14px !important;
            padding: 10px 12px !important;
            position: relative;
            box-shadow: inset 0 2px 14px rgba(0,0,0,.55), 0 0 26px rgba(var(--accent-rgb),.08) !important;
        }}
        div[class*="st-key-instru_"]::after {{
            content:""; position:absolute; top:0; left:6%; width:88%; height:38%;
            border-radius: 14px 14px 50% 50%;
            background: radial-gradient(ellipse at 50% 0%,
                rgba(255,255,255,.05) 0%, rgba(255,255,255,0) 72%);
            pointer-events:none;
        }}

        /* Aire entre los % del stress y la lectura */
        div[class*="st-key-card-risk-stress"] .dlp-card {{ margin-top: 12px !important; }}

        /* Métrica-a-métrica en 2 columnas (compare) + scroll propio de la tabla-ranking */
        .dlp-vsm-grid {{ display:grid; grid-template-columns:1fr 1fr; column-gap:26px; }}
        @media (max-width: 899px) {{ .dlp-vsm-grid {{ grid-template-columns:1fr; }} }}
        .dlp-table-scroll {{ overflow-x:auto; }}
        .dlp-table-scroll::-webkit-scrollbar {{ height:6px; }}

        /* Meter-stat: cifra héroe + termómetro fino (sustituye a los gauges de 240px) */
        .dlp-meter-stat {{ padding: 6px 4px 2px; }}
        .dlp-meter-stat .ms-label {{ color:{TEXT_LO}; font-family:{MONO}; font-size:10.5px;
            font-weight:700; text-transform:uppercase; letter-spacing:.12em; }}
        .dlp-meter-stat .ms-value {{ font-family:{MONO}; font-weight:800; font-size:44px;
            line-height:1.05; letter-spacing:-0.02em; margin:6px 0 2px; }}
        .dlp-meter-stat .ms-sub {{ color:{TEXT_LO}; font-size:12px; margin-bottom:10px; }}
        .dlp-meter-stat .ms-meter {{ position:relative; height:14px; display:flex; align-items:center; }}
        .dlp-meter-stat .ms-meter::before {{ content:""; width:100%; height:8px; border-radius:99px;
            background: linear-gradient(90deg, {RED} 0%, #E5C05C 50%, {GREEN} 100%);
            opacity:.5; }}
        .dlp-meter-stat .ms-dot {{ position:absolute; top:50%; width:13px; height:13px;
            border-radius:50%; transform:translate(-50%,-50%);
            border:2px solid {BG_CARD};
            transition:left var(--dur-3) var(--dlp-ease-out); }}
        .dlp-meter-stat .ms-ends {{ display:flex; justify-content:space-between;
            color:{TEXT_DIM}; font-family:{MONO}; font-size:9.5px; margin-top:4px;
            text-transform:uppercase; letter-spacing:.08em; }}

        /* Chip fino de cumplimiento: mismo texto exacto, sin aspecto de alerta de error */
        .dlp-disclaimer {{ display:flex; justify-content:center; margin:2px 0 10px;
            animation: dlpFadeUp .45s ease both; }}
        .dlp-disclaimer .head {{ display:inline-flex; align-items:center; gap:7px;
            color:{RED}; background:rgba(var(--neg-rgb),.07);
            border:1px solid rgba(var(--neg-rgb),.35); border-radius:999px;
            padding:4px 14px; font-family:{MONO}; font-size:10.5px; font-weight:700;
            text-transform:uppercase; letter-spacing:.08em; }}
        .dlp-disclaimer .body {{ color:{TEXT_MD}; font-size:14px; line-height:1.5; }}
        .dlp-sample-warn {{ background:rgba(var(--accent-hi-rgb),.08); border:1px solid rgba(var(--accent-hi-rgb),.45);
            border-left:5px solid {GOLD}; border-radius:10px; padding:12px 16px; margin:10px 0;
            color:{TEXT_MD}; font-size:13.5px; }}

        /* Aviso legal del pie: azul oscuro, letra gris pequeña. Deliberadamente
           discreto — cierra la página sin competir con el análisis. */
        .dlp-legal {{ background:{LEGAL_BG}; border:1px solid {LEGAL_EDGE}; border-radius:12px;
            padding:9px 14px; margin:10px 0 4px; }}
        .dlp-legal .lbl {{ color:{LEGAL_LBL}; font-family:{MONO}; font-size:11px; font-weight:700;
            text-transform:uppercase; letter-spacing:.10em; margin-right:6px; }}
        .dlp-legal .txt {{ color:{LEGAL_TXT}; font-size:11.5px; line-height:1.55; }}

        /* ── Botones ──────────────────────────────────────────── */
        /* CTA primario "Analizar": color SÓLIDO + borde nítido dorado + glow en el borde que
           llama la atención (estático premium, sin pulse perpetuo) + feedback al presionar. */
        button[data-testid^="stBaseButton-primary"] {{
            background: linear-gradient(135deg, {GOLD} 0%, {ORANGE} 55%, {ORANGE_DK} 100%) !important;
            color: #0A0B0D !important; font-weight: 800 !important;
            border: 1px solid rgba(var(--accent-hi-rgb),.65) !important;
            border-radius: 12px !important; padding: 13px 22px !important;
            font-family: {MONO} !important; text-transform: uppercase; letter-spacing: .07em;
            box-shadow: 0 6px 26px rgba(var(--accent-rgb),.30),
                        inset 0 1px 0 rgba(255,255,255,.35),
                        inset 0 -8px 18px rgba(0,0,0,.18) !important;
            transition: transform var(--dur-1) var(--dlp-ease-out),
                        box-shadow var(--dur-2) var(--dlp-ease-out),
                        filter var(--dur-2) var(--dlp-ease-out) !important;
        }}
        button[data-testid^="stBaseButton-primary"]:hover {{
            filter: brightness(1.07); transform: translateY(-1px);
            box-shadow: 0 10px 34px rgba(var(--accent-rgb),.42),
                        inset 0 1px 0 rgba(255,255,255,.4),
                        inset 0 -8px 18px rgba(0,0,0,.15) !important;
        }}
        button[data-testid^="stBaseButton-primary"]:hover {{
            background: var(--accent-hi) !important; transform: translateY(-1px);
            box-shadow: var(--shadow-2), inset 0 1px 0 rgba(255,255,255,.2) !important; }}
        button[data-testid^="stBaseButton-primary"]:active {{ transform: scale(.97); }}
        button[data-testid^="stBaseButton-primary"]:disabled {{
            background:{BG_CARD2} !important; color:{TEXT_DIM} !important;
            box-shadow:none !important; animation:none; opacity:1 !important;
            border:1px dashed {BORDER} !important;
        }}
        /* Secundario: superficie sólida azul-gris + borde nítido */
        button[data-testid^="stBaseButton-secondary"] {{
            background:var(--surface-2) !important; color:var(--text) !important;
            border:1px solid var(--hairline) !important; border-radius:var(--r-sm) !important;
            font-family:{FONT_FAMILY} !important; font-weight:500 !important; letter-spacing:0;
            text-transform:none; padding:11px 18px !important;
            transition: transform .16s var(--dlp-ease-out), border-color .16s var(--dlp-ease-out),
                        color .16s var(--dlp-ease-out), box-shadow .16s var(--dlp-ease-out);
        }}
        button[data-testid^="stBaseButton-secondary"]:hover {{
            border-color:rgba(var(--accent-rgb),.45) !important; color:var(--accent) !important;
            background:var(--surface-3) !important; }}
        button[data-testid^="stBaseButton-secondary"]:active {{ transform: scale(.97); }}

        /* Inputs */
        .stTextInput input, .stNumberInput input {{
            background:{BG_CARD2} !important; color:{TEXT_HI} !important;
            border:1px solid {BORDER} !important; border-radius:9px !important; }}
        .stTextInput input:focus, .stNumberInput input:focus {{
            border-color:{ORANGE} !important; box-shadow:0 0 0 2px rgba(var(--accent-rgb),.15) !important; }}

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {{ gap:6px; }}
        .stTabs [data-baseweb="tab"] {{ font-family:{MONO}; text-transform:uppercase;
            letter-spacing:.06em; font-size:13px; }}
        .stTabs [aria-selected="true"] {{ color:{ORANGE} !important; }}

        /* ── Cards vía keyed containers: st.container(key="card-…") ── */
        div[class*="st-key-card-"] {{
            background: linear-gradient(180deg, #13161C 0%, {BG_CARD} 58%, #0E1014 100%);
            border: 1px solid {METAL_BORDER}; border-radius: 18px;
            padding: 8px 16px 14px; margin-bottom: 14px;
            box-shadow: {METAL_SHADOW};
            transition: border-color .2s var(--dlp-ease-out);
        }}
        div[class*="st-key-card-"]:hover {{ border-color: rgba(var(--accent-rgb),.26); }}
        .dlp-card-head {{ display:flex; align-items:center; gap:10px; margin: 6px 0 12px;
            border-bottom:1px solid {BORDER}; padding-bottom:9px; }}
        .dlp-card-head .ic {{
            display:inline-flex; align-items:center; justify-content:center;
            width:26px; height:26px; border-radius:8px; flex:0 0 auto; font-size:11px; color:{GOLD};
            background: linear-gradient(135deg, rgba(var(--accent-rgb),.28) 0%, rgba(var(--accent-rgb),.07) 100%);
            border:1px solid rgba(var(--accent-rgb),.38);
            box-shadow: 0 3px 12px rgba(var(--accent-rgb),.16), inset 0 1px 0 rgba(255,255,255,.10); }}
        .dlp-card-head .tx {{ font-family:{FONT_FAMILY}; font-weight:600; text-transform:none;
            letter-spacing:-0.01em; color:var(--text-hi); font-size:16px; font-weight:650; }}
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

        /* ── Tooltips de ayuda (?) — popover con color para que se note ── */
        [data-testid="stTooltipContent"] {{
            background:{BG_CARD2} !important; color:{TEXT_MD} !important;
            border:1px solid rgba(var(--accent-rgb),.55) !important; border-radius:10px !important;
            box-shadow:0 10px 34px rgba(0,0,0,.5) !important; font-size:13px !important;
            line-height:1.5 !important; }}
        [data-testid="stTooltipHoverTarget"] svg, svg[data-testid="stTooltipIcon"] {{
            color:{ORANGE} !important; fill:{ORANGE} !important; }}

        /* ── Botón "Agregar Portafolio B" (azul, evidente, sin pulse) ── */
        div.st-key-addb button {{
            background: rgba(var(--info-rgb),.10) !important; color:{BLUE} !important;
            border:1.5px dashed rgba(var(--info-rgb),.7) !important; border-radius:12px !important;
            padding:9px 16px !important; font-family:{MONO} !important; font-weight:800 !important;
            text-transform:uppercase; letter-spacing:.08em; animation:none !important; }}
        div.st-key-addb button {{ transition: transform .16s var(--dlp-ease-out), background .16s var(--dlp-ease-out); }}
        div.st-key-addb button:hover {{ background: rgba(var(--info-rgb),.18) !important;
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
        .dlp-vs-badge {{ display:flex; align-items:center; justify-content:center;
            min-height:0; height:100%; }}
        .dlp-vs-badge span {{ width:48px; height:48px; border-radius:50%; border:1.5px solid {GOLD};
            color:{GOLD}; font-family:{MONO}; font-weight:800; font-size:14px; letter-spacing:.06em;
            display:flex; align-items:center; justify-content:center;
            box-shadow:0 0 20px rgba(var(--accent-hi-rgb),.30); background:rgba(var(--accent-hi-rgb),.06); }}

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
                        0 0 9px rgba(var(--accent-rgb),.12); }}
        .dlp-vsm .m-val {{ font-family:{MONO}; font-size:13.5px; color:{TEXT_LO};
            min-width:104px; text-align:right; }}
        .dlp-vsm .m-val.m-win {{ color:{TEXT_HI}; font-weight:800; }}
        .dlp-vsm .m-val.m-win::after {{ content:" ◆"; font-size:9px; }}

        /* ── Botón de PDF: amarillo, grande y llamativo (genera + descarga) ── */
        div.st-key-pdfgo button, div.st-key-pdfdl button {{
            background: var(--surface-2) !important;
            color:var(--accent) !important; border:1px solid rgba(var(--accent-rgb),.35) !important;
            border-radius:var(--r-md) !important;
            font-family:{FONT_FAMILY} !important; font-weight:600 !important; text-transform:none;
            letter-spacing:0; font-size:15px !important; padding:15px 24px !important;
            box-shadow: var(--inset-hi) !important;
            transition: transform .16s var(--dlp-ease-out); }}
        div.st-key-pdfgo button:hover, div.st-key-pdfdl button:hover {{ transform: translateY(-2px); }}
        div.st-key-pdfgo button:active, div.st-key-pdfdl button:active {{ transform: scale(.97); }}

        /* ── File uploader: español + nube dorada (traduce el UI interno de Streamlit) ── */
        [data-testid="stFileUploaderDropzone"] {{
            background:{BG_CARD2} !important; border:1.5px dashed rgba(var(--accent-rgb),.42) !important;
            border-radius:12px !important; transition: border-color .18s var(--dlp-ease-out); }}
        [data-testid="stFileUploaderDropzone"]:hover {{ border-color:{ORANGE} !important; }}
        [data-testid="stFileUploaderDropzone"] svg {{ fill:{ORANGE} !important; color:{ORANGE} !important;
            filter: drop-shadow(0 0 8px rgba(var(--accent-rgb),.4)); }}
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
            background: rgba(13,15,18,.45); border: 1px solid rgba(var(--accent-rgb),.16);
            border-radius: 18px; padding: 10px 14px 14px; margin-top: 14px;
            box-shadow: inset 0 1px 0 rgba(var(--accent-rgb),.06), 0 10px 40px rgba(0,0,0,.35); }}

        /* ── Sub-cards del builder (dona + "En tu portafolio"): metálico más claro ── */
        div[class*="st-key-donutcard_"], div[class*="st-key-holdings_"] {{
            background: linear-gradient(150deg, #1B1F25 0%, #15181D 100%);
            border: 1px solid rgba(var(--accent-rgb),.16); border-radius: 14px; padding: 12px 16px;
            box-shadow: 0 6px 20px rgba(0,0,0,.36), inset 0 1px 0 rgba(255,255,255,.06); }}
        div[class*="st-key-holdings_"] {{ margin-top: 14px; }}

        /* ── Buscador de activos: campo + tarjetas de resultado clickeables ── */
        div[class*="st-key-q_"] input {{
            background:{BG_CARD2} !important; border:1.5px solid rgba(var(--accent-rgb),.35) !important;
            border-radius:11px !important; height:50px !important; font-family:{MONO} !important;
            font-size:15px !important; }}
        div[class*="st-key-q_"] input:focus {{ border-color:{ORANGE} !important;
            box-shadow:0 0 0 3px rgba(var(--accent-rgb),.15) !important; }}
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
            border-color:{ORANGE} !important; box-shadow:0 0 18px rgba(var(--accent-rgb),.22) !important; }}
        div[class*="st-key-add_"] button p {{ margin:0 !important; }}
        div[class*="st-key-add_"] button strong {{ color:{TEXT_HI} !important; font-family:{MONO} !important;
            font-size:16px !important; font-weight:800 !important; margin-right:6px; }}

        /* ── Tabs con fondo + borde distinto (portafolios 1/2 y resultados) ── */
        .stTabs [data-baseweb="tab"] {{ background:{BG_CARD} !important; border:1px solid {BORDER} !important;
            border-bottom:none !important; border-radius:10px 10px 0 0 !important;
            padding:9px 18px !important; margin-right:3px !important; }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background:{METAL_BG} !important; border-color:{GOLD_HOVER} !important;
            color:{ORANGE} !important; box-shadow:0 -3px 16px rgba(var(--accent-rgb),.12); }}

        /* ── Barra de secciones (Resumen/Análisis/…): CENTRADA, estilo pestañas premium ── */
        /* Centrado robusto: el stRadio y sus wrappers ocupan el 100% del ancho, así que
           se centra el CONTENIDO en cada nivel de la cadena (no el contenedor). */
        div[class*="st-key-sectbar_"] {{ margin:2px 0 14px; align-items:center !important;
            position:relative; }}
        /* Separador dorado con brillo BAJO la barra: ::after absoluto dentro del margen
           que ya existe — no ocupa espacio, nada se mueve un píxel. */
        div[class*="st-key-sectbar_"]::after {{
            content:""; position:absolute; left:8%; right:8%; bottom:-7px; height:1px;
            background: linear-gradient(90deg,
                rgba(var(--accent-rgb),0) 0%, rgba(var(--accent-rgb),.45) 18%,
                rgba(var(--accent-rgb),.65) 50%, rgba(var(--accent-rgb),.45) 82%,
                rgba(var(--accent-rgb),0) 100%);
            box-shadow: 0 0 8px rgba(var(--accent-rgb),.4), 0 0 2px rgba(var(--accent-rgb),.55);
            pointer-events:none; }}
        div[class*="st-key-sectbar_"] [data-testid="stRadio"],
        div[class*="st-key-sectbar_"] [data-testid="stRadio"] > div {{
            width:100% !important; display:flex !important; justify-content:center !important; }}
        /* El carril = píldora contenedora */
        div[class*="st-key-sectbar_"] [role="radiogroup"] {{
            display:inline-flex !important; justify-content:center; flex-wrap:nowrap; gap:3px;
            margin:0 auto !important; width:auto !important; max-width:100%;
            background:{BG_CARD}; border:1px solid {HAIRLINE_2}; border-radius:14px; padding:5px;
            box-shadow: {INSET_HI}, {SHADOW_1}; }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label {{
            margin:0 !important; padding:8px 12px !important; border-radius:10px !important;
            white-space:nowrap !important; display:flex !important; align-items:center;
            border:1px solid transparent !important; background:transparent !important;
            cursor:pointer;
            transition: background var(--dur-2) var(--dlp-ease-out),
                        border-color var(--dur-2) var(--dlp-ease-out),
                        box-shadow var(--dur-2) var(--dlp-ease-out); }}
        /* El radio NATIVO se oculta DE VERDAD (todas las variantes del DOM BaseWeb) */
        div[class*="st-key-sectbar_"] [role="radiogroup"] label > div:first-child,
        div[class*="st-key-sectbar_"] [role="radiogroup"] label > span:first-child {{
            display:none !important; }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label input[type="radio"] {{
            appearance:none !important; -webkit-appearance:none !important;
            position:absolute !important; opacity:0 !important;
            width:0 !important; height:0 !important; margin:0 !important; padding:0 !important;
            border:0 !important; background:none !important; pointer-events:none !important; }}
        /* Etiqueta + punto PROPIO dibujado (no el del radio) */
        div[class*="st-key-sectbar_"] [role="radiogroup"] label p {{
            font-family:{MONO} !important; font-size:11px !important; font-weight:700 !important;
            text-transform:uppercase; letter-spacing:.05em;
            color:{TEXT_DIM} !important; margin:0 !important;
            display:flex; align-items:center; white-space:nowrap !important;
            transition: color var(--dur-2) var(--dlp-ease-out); }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label p::before {{
            content:""; width:8px; height:8px; border-radius:50%;
            border:1.5px solid rgba(255,255,255,.25); background:transparent;
            margin-right:7px; flex:0 0 auto;
            transition: background var(--dur-2) var(--dlp-ease-out),
                        border-color var(--dur-2) var(--dlp-ease-out),
                        box-shadow var(--dur-2) var(--dlp-ease-out); }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label:hover {{
            background:rgba(var(--accent-rgb),.06) !important; }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label:hover p {{ color:{TEXT_MD} !important; }}
        /* ACTIVA: borde dorado + halo + punto "donut" encendido */
        div[class*="st-key-sectbar_"] [role="radiogroup"] label:has(input:checked) {{
            background:rgba(var(--accent-rgb),.07) !important;
            border-color:rgba(var(--accent-rgb),.55) !important;
            box-shadow: 0 0 16px rgba(var(--accent-rgb),.16), {INSET_HI} !important; }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label:has(input:checked) p {{
            color:{ORANGE} !important; }}
        div[class*="st-key-sectbar_"] [role="radiogroup"] label:has(input:checked) p::before {{
            background:{ORANGE}; border-color:{ORANGE};
            box-shadow: 0 0 8px rgba(var(--accent-rgb),.55), inset 0 0 0 2px rgba(10,11,13,.55); }}

        /* ── Slider de horizonte: grueso, protagonista, con glow dorado ── */
        .stSlider [data-baseweb="slider"] {{ padding-top:12px !important; padding-bottom:2px !important; }}
        .stSlider [data-baseweb="slider"] > div {{ height:10px !important; border-radius:6px !important; }}
        .stSlider [data-baseweb="slider"] div[role="slider"] {{
            height:28px !important; width:28px !important;
            background:{ORANGE} !important; border:3px solid #F0C878 !important;
            box-shadow:0 0 0 6px rgba(var(--accent-rgb),.16), 0 0 22px rgba(var(--accent-rgb),.55),
                       0 3px 12px rgba(0,0,0,.6) !important; }}
        [data-testid="stSliderThumbValue"] {{ color:{ORANGE} !important; font-family:{MONO} !important;
            font-weight:800 !important; font-size:15px !important; }}

        /* ── Reduced motion (Apple/accesibilidad): sin movimiento vestibular ────
           colapsa bucles perpetuos y quita los desplazamientos de hover/entrada,
           conservando los cambios de opacidad/color que ayudan a comprender. */
        /* ── Responsive de las filas-pareja (namespace st-key-pair-*) ─────────
           Streamlit solo apila columnas en ~640px; entre 640 y 900 quedarían
           apretujadas. Grid real a 1 columna, con min-width:0 para que Plotly
           no desborde el carril. Solo afecta a los contenedores pair-. */
        @media (max-width: 899px) {{
            [data-testid="stHorizontalBlock"]:has([class*="st-key-pair-"]),
            div[class*="st-key-pair-"] [data-testid="stHorizontalBlock"] {{
                display: grid !important;
                grid-template-columns: 1fr !important;
                gap: 10px !important;
            }}
            div[class*="st-key-pair-"] [data-testid="stColumn"] {{
                width: 100% !important; min-width: 0 !important; flex: none !important;
            }}
        }}


        /* ═══ F7 · CAPA DE MOVIMIENTO Y TEXTURA (patrones Analyzer) ═════════ */

        /* Entrada de tarjetas: fadeUp corto con fill BACKWARDS (suelta el transform
           al terminar — jamás un containing block permanente). */
        div[class*="st-key-card-"] {{
            animation: dlpFadeUp .42s var(--dlp-ease-out) backwards;
            position: relative;
        }}
        /* Cascada por columna en las filas-pareja y de KPIs (tope 320ms) */
        [data-testid="stColumn"]:nth-child(2) div[class*="st-key-card-"],
        [data-testid="stColumn"]:nth-child(2) .dlp-kpi {{ animation-delay: 60ms; }}
        [data-testid="stColumn"]:nth-child(3) div[class*="st-key-card-"],
        [data-testid="stColumn"]:nth-child(3) .dlp-kpi {{ animation-delay: 120ms; }}
        [data-testid="stColumn"]:nth-child(4) .dlp-kpi {{ animation-delay: 180ms; }}

        /* Glow de esquina al hover (6%: casi nada, se nota) + lift de 1px.
           Solo con puntero fino: en táctil no hay hover fantasma. */
        div[class*="st-key-card-"]::after {{
            content:""; position:absolute; top:0; right:0; width:150px; height:150px;
            background: radial-gradient(circle at top right, var(--accent) 0%, transparent 65%);
            border-top-right-radius: 18px; opacity:0;
            transition: opacity .35s var(--dlp-ease-out); pointer-events:none;
        }}
        @media (hover: hover) and (pointer: fine) {{
            div[class*="st-key-card-"] {{
                transition: border-color var(--dur-2) var(--dlp-ease-out),
                            transform var(--dur-2) var(--dlp-ease-out),
                            box-shadow var(--dur-2) var(--dlp-ease-out);
            }}
            div[class*="st-key-card-"]:hover {{
                transform: translateY(-1px);
                box-shadow: {INSET_HI}, {SHADOW_2};
            }}
            div[class*="st-key-card-"]:hover::after {{ opacity:.06; }}
        }}
        @media (hover: none) {{
            div[class*="st-key-card-"]:hover, .dlp-kpi:hover {{ transform:none; }}
        }}


        /* Tooltip del "?": en la primera columna se abre hacia la DERECHA
           (hacia adentro del iframe, no hacia afuera). */
        [data-testid="stColumn"]:first-child .dlp-kpi-help::after {{
            right:auto; left:-8px;
        }}

        @media (prefers-reduced-motion: reduce) {{
            div[class*="st-key-card-"], div[class*="st-key-card-"]:hover {{ transform:none !important; }}
            div[class*="st-key-q_"]::before {{ animation:none !important; }}
            div[class*="st-key-donutcard_"] .js-plotly-plot {{ animation:none !important; }}
            .stPlotlyChart g.slice:hover path.surface {{ transform:none !important; }}
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
