"""Componentes visuales reutilizables que se sienten DLP.

Incluye el disclaimer obligatorio (honestidad matemática), KPI tiles, hero card
y el sidebar de historial persistente.
"""
from __future__ import annotations

import re

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


def spinner_ring(message: str) -> str:
    """Spinner circular indeterminado (mismo estilo que el loader, pero girando). Bien evidente."""
    return f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:26px 0;">
      <div style="width:96px;height:96px;border-radius:50%;
        background:conic-gradient({S.ORANGE} 0deg, {S.ORANGE} 270deg, {S.BG_CARD2} 270deg);
        -webkit-mask:radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 11px));
        mask:radial-gradient(farthest-side, transparent calc(100% - 11px), #000 calc(100% - 11px));
        animation: dlpSpin .8s linear infinite;"></div>
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
    """Hero centrado con ambiente: glow respirando detrás, diamante y título metálico.
    (Restaurado a pedido del usuario — la banda de una línea quedó descartada.)"""
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


def disclaimer_banner() -> None:
    """Banner de disclaimer visible (no escondido en footer). Llamar en CADA vista con números."""
    st.markdown(
        """
        <div class="dlp-disclaimer">
          <div class="head">⚠ Proyección probabilística — no es certeza</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def legal_notice() -> None:
    """Aviso legal del pie de página. Va al final de la pantalla principal, esté o no
    hecho el análisis: deja claro que la herramienta es educativa y de uso autónomo."""
    st.markdown(
        """
        <div class="dlp-legal">
          <span class="lbl">Aviso:</span><span class="txt">esto no es asesoría de inversión
          ni recomendación de inversión de ningún tipo. Estas herramientas son exclusivamente
          para uso autónomo y educativo.</span>
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
    # Tamaño del número según su longitud → SIEMPRE en un solo renglón (se achica si es largo).
    vlen = len(str(value))
    if vlen <= 6:
        vfs = "clamp(19px, 3.8vw, 30px)"
    elif vlen <= 8:
        vfs = "clamp(16px, 3.2vw, 25px)"
    elif vlen <= 11:
        vfs = "clamp(14px, 2.7vw, 21px)"
    else:
        vfs = "clamp(12px, 2.3vw, 18px)"
    st.markdown(
        f"""
        <div class="dlp-kpi">
          <div class="accent" style="background:{vcolor};"></div>
          <div class="kpi-head"><span class="kpi-label">{label}</span>{help_html}</div>
          <div class="kpi-value" style="color:{vcolor};font-size:{vfs};">{value}</div>
          <div class="kpi-sub">{sublabel}</div>
          {meter_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def meter_stat(label: str, value: str, color: str, pos: float,
               sub: str = "", ends: tuple[str, str] = ("riesgo", "sólido")) -> None:
    """ANILLO de progreso rico (conic-gradient + glow, el lenguaje del loader) con la
    cifra en el centro, más un termómetro fino de refuerzo debajo.

    `pos` 0-1: llena el anillo y posiciona el punto (0=rojo/izq, 1=verde/der).
    """
    frac = max(0.0, min(1.0, float(pos)))
    deg = frac * 360.0
    pct = frac * 100.0
    st.markdown(
        f"""
        <div class="dlp-ring-stat">
          <div class="rs-label">{label}</div>
          <div class="rs-wrap">
            <div class="rs-ring" style="background:
                 conic-gradient({color} {deg:.0f}deg, rgba(255,255,255,.06) {deg:.0f}deg);
                 box-shadow: 0 0 34px {color}44, inset 0 1px 0 rgba(255,255,255,.05);">
              <div class="rs-hole">
                <span class="rs-value" style="color:{color};
                      text-shadow:0 0 18px {color}66;">{value}</span>
              </div>
            </div>
          </div>
          <div class="rs-sub">{sub}</div>
          <div class="ms-meter"><span class="ms-dot"
               style="left:{pct:.0f}%;background:{color};box-shadow:0 0 10px {color};"></span></div>
          <div class="ms-ends"><span>{ends[0]}</span><span>{ends[1]}</span></div>
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


def _rich(texto: str) -> str:
    """Negrita/cursiva de markdown a HTML real, para textos que se inyectan en HTML crudo."""
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", texto)


def finding_card(finding: dict) -> None:
    """Tarjeta de un hallazgo: acento por sentimiento (verde/azul/rojo) + título + texto claro."""
    color, icon = _FINDING_STYLE.get(finding.get("sentiment", "neutral"), _FINDING_STYLE["neutral"])
    # OJO: este texto va dentro de HTML CRUDO, donde Streamlit NO procesa markdown. Por eso
    # aquí NO se escapa el '$' (la barra invertida se veía literal: "\\$402,171") y la negrita
    # se convierte a <b> de verdad en vez de dejar los asteriscos a la vista.
    body = _rich(finding.get("text") or "")
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
    """Tarjeta de veredicto de la comparación: qué gana cada portafolio y qué cede."""
    st.markdown(
        f"<div class='dlp-card dlp-card-left' style='border-left-color:{color};'>"
        f"<div class='kpi-label'>Veredicto</div>"
        f"<div style='color:{S.TEXT_MD};font-size:15.5px;margin-top:8px;line-height:1.6;'>{html}</div>"
        f"</div>", unsafe_allow_html=True)
