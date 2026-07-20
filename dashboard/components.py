"""Componentes visuales reutilizables que se sienten DLP.

Incluye el disclaimer obligatorio (honestidad matemática), KPI tiles, hero card
y el sidebar de historial persistente.
"""
from __future__ import annotations

import streamlit as st

from dashboard import styles as S

# Texto OBLIGATORIO del disclaimer (spec sección 3). Va VISIBLE en cada vista con números.
DISCLAIMER_TEXT = (
    "Esta simulación NO es predicción ni recomendación de inversión. "
    "Proyecta escenarios estadísticos basados en retornos históricos. "
    "El comportamiento real del mercado puede diferir significativamente. "
    "Consulta a un asesor financiero antes de tomar decisiones."
)


def fmt_money(x: float | None) -> str:
    """Formatea un número como monto en USD sin decimales."""
    if x is None:
        return "—"
    return f"${x:,.0f}"


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.0f}%"


def progress_overlay(pct: int, message: str) -> str:
    """Loader a pantalla completa (fijo + centrado): imposible de perderse sin importar
    el scroll. Anillo de progreso conic-gradient + % + mensaje. Estilos en styles.py."""
    deg = pct * 3.6
    return f"""
    <div class="dlp-loader-overlay">
      <div class="dlp-loader-panel">
        <div class="dlp-loader-ring"
             style="background:conic-gradient({S.ORANGE} {deg}deg, {S.BG_CARD2} {deg}deg);">
          <div class="dlp-loader-hole">
            <span class="pct">{pct}%</span>
            <span class="lbl">ANALIZANDO</span>
          </div>
        </div>
        <div class="dlp-loader-msg">{message}</div>
      </div>
    </div>
    """


def progress_ring(pct: int, message: str) -> str:
    """HTML de un anillo de progreso circular (conic-gradient) 0-100% con número y mensaje."""
    deg = pct * 3.6
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
                padding:46px 0 38px;">
      <div style="width:158px;height:158px;border-radius:50%;
        background:conic-gradient({S.ORANGE} {deg}deg, {S.BG_CARD2} {deg}deg);
        display:flex;align-items:center;justify-content:center;
        box-shadow:0 0 46px rgba(255,184,77,.28); transition: background .15s linear;">
        <div style="width:122px;height:122px;border-radius:50%;background:{S.BG_DEEP};
          display:flex;flex-direction:column;align-items:center;justify-content:center;">
          <span style="font-family:{S.MONO};font-size:34px;font-weight:800;color:{S.ORANGE};">{pct}%</span>
          <span style="font-family:{S.MONO};font-size:10px;color:{S.TEXT_LO};
                letter-spacing:.18em;margin-top:2px;">SIMULANDO</span>
        </div>
      </div>
      <div style="font-family:{S.MONO};text-transform:uppercase;letter-spacing:.12em;
           color:{S.TEXT_MD};font-size:13px;margin-top:20px;">{message}</div>
    </div>
    """


def spinner_ring(message: str) -> str:
    """Spinner circular indeterminado (mismo estilo que el loader, pero girando). Bien evidente."""
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:26px 0;">
      <div style="width:96px;height:96px;border-radius:50%;
        background:conic-gradient({S.ORANGE} 0deg, {S.ORANGE} 270deg, {S.BG_CARD2} 270deg);
        -webkit-mask:radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 11px));
        mask:radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 11px));
        animation: dlpSpin .8s linear infinite; box-shadow:0 0 36px rgba(255,184,77,.5);"></div>
      <div style="font-family:{S.MONO};text-transform:uppercase;letter-spacing:.14em;
           color:{S.ORANGE};font-size:14px;margin-top:18px;">{message}</div>
    </div>
    """


def card(key: str):
    """Contenedor-tarjeta premium. Usar como context manager: `with card('plan'):`."""
    return st.container(key=f"card-{key}")


def card_head(icon: str, title: str, hint: str = "") -> None:
    """Encabezado de tarjeta: icono + título mono + hint opcional a la derecha."""
    h = f"<span class='hint'>{hint}</span>" if hint else ""
    st.markdown(
        f"<div class='dlp-card-head'><span class='ic'>{icon}</span>"
        f"<span class='tx'>{title}</span>{h}</div>",
        unsafe_allow_html=True,
    )


def page_hero() -> None:
    """Hero de la página: título dorado con glow + diamante + subtítulo (estilo app madre)."""
    st.markdown(
        """
        <div class="dlp-page-hero">
          <div class="glow"></div>
          <div class="diamond">◆</div>
          <div class="title">Analista de<br>Portafolios</div>
          <div class="sub">Analiza tu portafolio y sus 10.000 futuros posibles</div>
          <div class="dlp-rule"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stepper(portafolio_ok: bool) -> None:
    """Indicador de pasos. El paso 3 se 'activa' cuando el portafolio está listo."""
    def num(done: bool, n: int) -> str:
        return "✓" if done else str(n)
    s1d, s2d, s3a = True, portafolio_ok, portafolio_ok
    st.markdown(
        f"""
        <div class="dlp-steps">
          <div class="dlp-step done"><span class="num">{num(True,1)}</span> Tu plan</div>
          <div class="dlp-step {'done' if s2d else 'active'}"><span class="num">{num(s2d,2)}</span> Tu portafolio</div>
          <div class="dlp-step {'active' if s3a else ''}"><span class="num">3</span> Proyectar</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(text: str, kind: str = "orange") -> str:
    """Devuelve el HTML de una pill de estado (orange/blue/green/ghost)."""
    return f'<span class="dlp-pill dlp-pill-{kind}">{text}</span>'


def search_menu(pid: str = ""):
    """Panel-menú elevado para los resultados del buscador (se separa del fondo)."""
    return st.container(key=f"searchmenu_{pid}")


def ticker_result_card(r: dict) -> str:
    """Tarjeta de un ticker: código (con color) a la izquierda, nombre + bolsa a la derecha."""
    color = S.BLUE if r.get("is_etf") else S.ORANGE
    kind = "ETF" if r.get("is_etf") else "Acción"
    name = (r.get("name") or "")[:42]
    return (f"<div class='dlp-tk'>"
            f"<div class='code' style='color:{color}; border-color:{color}66;'>{r['symbol']}</div>"
            f"<div class='meta'><div class='nm'>{name}</div>"
            f"<div class='ex'>{r['exchange']} · {kind}</div></div></div>")


def disclaimer_banner() -> None:
    """Banner de disclaimer visible (no escondido en footer). Llamar en CADA vista con números."""
    st.markdown(
        f"""
        <div class="dlp-disclaimer">
          <div class="head">⚠ Proyección probabilística — no es certeza</div>
          <div class="body">{DISCLAIMER_TEXT}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sample_data_notice() -> None:
    """Aviso visible de que se están usando datos de muestra (yfinance no respondió)."""
    st.markdown(
        """
        <div class="dlp-sample-warn">
          ◇ <b>Datos de muestra</b>: yfinance no respondió, así que esta proyección usa
          datos ilustrativos empaquetados — <b>no</b> cotizaciones reales en vivo.
          Vuelve a intentar más tarde para usar precios reales.
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_tile(label: str, value: str, color: str, sublabel: str = "",
             help: str | None = None, rating: dict | None = None) -> None:
    """KPI tile: accent + "?" opcional + termómetro rojo→verde con palabra (Malo…Excelente).

    `help`: badge "?" dorado con tooltip explicativo al hover.
    `rating`: dict {pos:0-1, color, word} (de core.rating) → dibuja el termómetro debajo y
    tiñe el número con el color de la calificación. Los tiles quedan de altura uniforme.
    """
    help_html = ""
    if help:
        tip = str(help).replace('"', "&quot;")
        help_html = f"<span class='dlp-kpi-help' data-tooltip=\"{tip}\">?</span>"
    vcolor = color
    meter_html = ""
    if rating:
        vcolor = rating.get("color", color)
        pos = max(0.0, min(1.0, float(rating.get("pos", 0.5)))) * 100.0
        word = rating.get("word", "")
        meter_html = (
            f"<div class='kpi-meter'><div class='kpi-meter-track'>"
            f"<span class='kpi-meter-dot' style='left:{pos:.0f}%;border-color:{vcolor};"
            f"box-shadow:0 0 9px {vcolor};'></span></div>"
            f"<div class='kpi-meter-word' style='color:{vcolor}'>{word}</div></div>")
    st.markdown(
        f"""
        <div class="dlp-kpi">
          <div class="accent" style="background:{vcolor};"></div>
          <div class="kpi-head"><span class="kpi-label">{label}</span>{help_html}</div>
          <div class="kpi-value" style="color:{vcolor};">{value}</div>
          <div class="kpi-sub">{sublabel}</div>
          {meter_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero_card(glyph: str, caption: str, meta_items: list[tuple[str, str]],
              highlight_label: str, highlight_value: str, highlight_color: str) -> None:
    """Hero card centrado: etiqueta arriba, MONTO grande al centro, meta distribuida abajo."""
    meta_html = "".join(
        f'<div class="hm"><div class="hm-label">{lbl}</div>'
        f'<div class="hm-value">{val}</div></div>'
        for lbl, val in meta_items
    )
    st.markdown(
        f"""
        <div class="dlp-hero-v2">
          <div class="hero-top"><span class="hero-glyph">{glyph}</span> {caption} · {highlight_label}</div>
          <div class="hero-number" style="color:{highlight_color};">{highlight_value}</div>
          <div class="hero-meta">{meta_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# Sentimiento del hallazgo → (color, icono)
_FINDING_STYLE = {
    "positivo": (S.GREEN, "✓"),
    "neutral": (S.BLUE, "◆"),
    "alerta": (S.RED, "⚠"),
}


def finding_card(finding: dict) -> None:
    """Tarjeta de un hallazgo: acento por sentimiento (verde/azul/rojo) + título + texto claro."""
    color, icon = _FINDING_STYLE.get(finding.get("sentiment", "neutral"), _FINDING_STYLE["neutral"])
    # Escapamos '$' para que Streamlit no interprete montos como LaTeX.
    body = (finding.get("text") or "").replace("$", "\\$")
    st.markdown(
        f"<div class='dlp-card dlp-card-left' style='border-left-color:{color};margin-bottom:10px;padding:14px 18px;'>"
        f"<div style='display:flex;align-items:baseline;gap:9px;'>"
        f"<span style='color:{color};font-size:14px;'>{icon}</span>"
        f"<b style='color:{S.TEXT_HI};font-family:{S.MONO};font-size:13.5px;letter-spacing:.03em;'>{finding.get('title','')}</b>"
        f"<span style='margin-left:auto;color:{S.TEXT_DIM};font-family:{S.MONO};font-size:10px;"
        f"text-transform:uppercase;letter-spacing:.1em;'>{finding.get('category','')}</span></div>"
        f"<div style='color:{S.TEXT_MD};font-size:14px;line-height:1.6;margin-top:8px;'>{body}</div></div>",
        unsafe_allow_html=True,
    )


def verdict_card(color: str, html: str) -> None:
    """Tarjeta de veredicto para la comparación A vs B (lectura honesta del trade-off)."""
    st.markdown(
        f"<div class='dlp-card dlp-card-left' style='border-left-color:{color};'>"
        f"<div class='kpi-label'>Veredicto</div>"
        f"<div style='color:{S.TEXT_MD};font-size:15.5px;margin-top:8px;line-height:1.6;'>{html}</div>"
        f"</div>", unsafe_allow_html=True)
