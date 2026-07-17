"""Constructores de charts Plotly con la estética DLP.

Firma visual de la casa: la línea principal usa la técnica de glow triple
(3 capas: glow exterior + glow interior + línea sólida).
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from dashboard import styles as S


def _apply_growth_scale(fig: go.Figure, series: list, y_title: str = "Patrimonio (USD)") -> None:
    """Escala el eje Y a logarítmica cuando hay crecimiento compuesto fuerte y todos
    los valores son positivos.

    Motivo: en escala lineal el interés compuesto se ve plano al principio y se dispara
    solo al final, y no deja leer el rendimiento a lo largo del tiempo. En escala log una
    tasa de crecimiento constante es una recta, así la trayectoria y las diferencias entre
    portafolios se ven en TODOS los años. NO cambia ningún dato: solo la escala visual del
    eje (el hover sigue mostrando los montos exactos).

    Si algún valor es ≤0 (p. ej. ruina en modo retiro) o el rango es chico, se deja lineal.
    """
    arrs = [np.asarray(a, dtype=float).ravel() for a in series if a is not None]
    flat = np.concatenate(arrs) if arrs else np.array([])
    flat = flat[np.isfinite(flat)]
    if flat.size and flat.min() > 0 and (flat.max() / flat.min()) >= 4.0:
        # 'D2' → marcas 1-2-5 por década (10k, 20k, 50k, 100k…); '~s' → sufijos $10k / $1M
        fig.update_yaxes(type="log", tickprefix="$", tickformat="~s", dtick="D2",
                         title=f"{y_title} · escala log")
    else:
        fig.update_yaxes(tickprefix="$", tickformat=",.0f", title=y_title)


def _apply_dlp_layout(fig: go.Figure, x_title: str, y_title: str, height: int = 460) -> go.Figure:
    """Layout dark común a todos los charts DLP (mismo tratamiento que DLP Analyzer).

    Superficie #0F1419 (= la card CSS) para que figura y contenedor se fundan en una
    sola pieza; grid hairline gris que no compite con los datos; tipografía JetBrains
    Mono y tooltip oscuro con borde oro — la firma visual de la app madre.
    """
    fig.update_layout(
        height=height,
        paper_bgcolor=S.BG_CARD,
        plot_bgcolor=S.BG_CARD,
        font=dict(family=S.MONO, color=S.TEXT_MD, size=12),
        margin=dict(l=96, r=30, t=34, b=55),
        hovermode="x unified",
        showlegend=False,
        hoverlabel=dict(bgcolor=S.BG_CARD2, bordercolor=S.GOLD_HOVER,
                        font=dict(family=S.MONO, color=S.TEXT_MD, size=11)),
    )
    axis = dict(
        gridcolor=S.GRID_HAIR, zerolinecolor=S.GRID_ZERO,
        linecolor=S.GRID_HAIR, tickfont=dict(color=S.TEXT_LO),
        title_font=dict(color=S.TEXT_LO, size=13), title_standoff=16,
    )
    fig.update_xaxes(title=x_title, **axis)
    fig.update_yaxes(title=y_title, **axis)
    return fig


def _add_band(fig: go.Figure, x, lower, upper, fillcolor: str) -> None:
    """Banda sombreada entre `lower` y `upper`."""
    fig.add_trace(go.Scatter(x=x, y=upper, mode="lines", line=dict(width=0),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=lower, mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=fillcolor,
                             hoverinfo="skip", showlegend=False))


def _add_glow_line(fig: go.Figure, x, y, color: str, glow_rgba: tuple[str, str]) -> None:
    """Línea con glow triple (firma visual DLP)."""
    # Capa 1: glow exterior
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines",
                             line=dict(color=glow_rgba[0], width=24, shape="spline", smoothing=0.5),
                             hoverinfo="skip", showlegend=False))
    # Capa 2: glow interior
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines",
                             line=dict(color=glow_rgba[1], width=12, shape="spline", smoothing=0.5),
                             hoverinfo="skip", showlegend=False))
    # Capa 3: línea principal (sin hover propio — el hover unificado va aparte)
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="Mediana",
                             line=dict(color=color, width=5, shape="spline", smoothing=0.5),
                             hoverinfo="skip", showlegend=False))


def fan_chart(percentiles: dict, n_months: int, target: float | None = None) -> go.Figure:
    """Abanico de escenarios: bandas P5-P95 y P25-P75 + mediana con glow.

    `percentiles`: dict con claves P5/P25/P50/P75/P95 → arrays de largo n_months+1.
    """
    x = np.arange(n_months + 1) / 12.0  # eje X en años
    fig = go.Figure()

    # Banda externa P5-P95 (alpha 0.15) y banda interna P25-P75 (alpha 0.30)
    _add_band(fig, x, percentiles["P5"], percentiles["P95"], "rgba(255,184,77,0.15)")
    _add_band(fig, x, percentiles["P25"], percentiles["P75"], "rgba(255,184,77,0.30)")

    # Mediana con glow triple
    _add_glow_line(fig, x, percentiles["P50"], S.ORANGE,
                   ("rgba(255,184,77,0.18)", "rgba(255,184,77,0.35)"))

    # Trazas invisibles para hover unificado en tiempo real (máx / mediana / mín).
    # Orden P5→P50→P95 para que en el tooltip queden de menor a mayor.
    for name, key, col in [("Pesimista (P5)", "P5", S.RED),
                           ("Mediana (P50)", "P50", S.ORANGE),
                           ("Optimista (P95)", "P95", S.GREEN)]:
        fig.add_trace(go.Scatter(
            x=x, y=percentiles[key], mode="lines", name=name, showlegend=False,
            line=dict(width=0, color=col),
            hovertemplate=f"<b>{name}</b>: $%{{y:,.0f}}<extra></extra>"))

    # Línea de meta (verde) si el usuario la ingresó
    if target:
        fig.add_hline(y=target, line=dict(color=S.GREEN, width=2, dash="dash"),
                      annotation_text="Meta", annotation_position="top left",
                      annotation_font=dict(color=S.GREEN, size=12))

    _apply_dlp_layout(fig, "Años", "Patrimonio (USD)", height=340)
    # Escala Y log si hay crecimiento compuesto fuerte (lee mejor todos los años, no solo el final)
    _apply_growth_scale(fig, [percentiles["P5"], percentiles["P95"]])
    # Línea guía vertical + año formateado para leer el abanico con el cursor
    fig.update_xaxes(hoverformat=".1f", showspikes=True, spikemode="across",
                     spikethickness=1, spikedash="dot", spikecolor="rgba(255,184,77,0.55)")
    fig.update_layout(hoverlabel=dict(bgcolor=S.BG_CARD2, bordercolor=S.GOLD_HOVER,
                                      font=dict(family=S.MONO, color=S.TEXT_HI)))
    return fig


def histogram_final(final_values: np.ndarray, bins: int = 60, plain_labels: bool = False) -> go.Figure:
    """Distribución del patrimonio final: barras coloreadas por percentil
    (rojo abajo / naranja medio / verde arriba) + líneas P5 / mediana / P95.

    `plain_labels=True` usa etiquetas en lenguaje simple (para el PDF)."""
    p5, p50, p95 = np.percentile(final_values, [5, 50, 95])
    counts, edges = np.histogram(final_values, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2.0

    colors = np.where(centers <= p5, S.RED,
                      np.where(centers >= p95, S.GREEN, S.ORANGE))

    fig = go.Figure(go.Bar(
        x=centers, y=counts, marker=dict(color=colors, line=dict(width=0)),
        width=(edges[1] - edges[0]) * 0.92,
        hovertemplate="$%{x:,.0f}<br>%{y} escenarios<extra></extra>",
    ))

    lbl = (["Peor 5%", "Típico", "Mejor 5%"] if plain_labels else ["P5", "Mediana", "P95"])
    for value, color, label in [(p5, S.RED, lbl[0]), (p50, S.ORANGE, lbl[1]), (p95, S.GREEN, lbl[2])]:
        fig.add_vline(x=value, line=dict(color=color, width=2, dash="dash"),
                      annotation_text=label, annotation_position="top",
                      annotation_font=dict(color=color, size=12))

    _apply_dlp_layout(fig, "Patrimonio final (USD)", "Cantidad de escenarios", height=300)
    fig.update_xaxes(tickprefix="$", tickformat=",.0f")
    fig.update_layout(bargap=0.02, hovermode="x")
    return fig


def success_gauge(prob: float, target_label: str = "") -> go.Figure:
    """Gauge de probabilidad de alcanzar la meta. Verde ≥70%, naranja 50-70%, rojo <50%."""
    pct = max(0.0, min(1.0, prob)) * 100.0
    color = S.GREEN if prob >= 0.70 else (S.ORANGE if prob >= 0.50 else S.RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "valueformat": ".0f",
                "font": {"size": 46, "color": color, "family": S.MONO}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": S.TEXT_LO,
                     "tickfont": {"color": S.TEXT_LO, "size": 11, "family": S.MONO}},
            "bar": {"color": color, "thickness": 0.32},
            "bgcolor": S.BG_CARD2,
            "borderwidth": 0,
            "steps": [
                {"range": [0, 50], "color": "rgba(255,59,92,0.12)"},
                {"range": [50, 70], "color": "rgba(255,184,77,0.12)"},
                {"range": [70, 100], "color": "rgba(0,255,136,0.12)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "value": pct},
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(
        height=240, paper_bgcolor=S.BG_CARD,
        font=dict(family=S.MONO, color=S.TEXT_MD),
        margin=dict(l=30, r=30, t=20, b=10),
        title=dict(text=target_label, font=dict(color=S.TEXT_LO, size=13), x=0.5, y=0.02),
    )
    return fig


# (color principal, (glow exterior, glow interior), fill de banda) por escenario
_COMPARE_STYLES = [
    (S.ORANGE, ("rgba(255,184,77,0.16)", "rgba(255,184,77,0.32)"), "rgba(255,184,77,0.08)"),
    (S.BLUE, ("rgba(74,158,255,0.16)", "rgba(74,158,255,0.32)"), "rgba(74,158,255,0.08)"),
    (S.GOLD, ("rgba(255,215,64,0.16)", "rgba(255,215,64,0.32)"), "rgba(255,215,64,0.08)"),
    (S.GREEN, ("rgba(0,255,136,0.14)", "rgba(0,255,136,0.30)"), "rgba(0,255,136,0.07)"),
]


def comparison_fan_chart(scenarios: list[dict], n_months: int, target: float | None = None) -> go.Figure:
    """Compara hasta 3 portafolios: medianas con glow + banda P5-P95 tenue, colores distintos.

    `scenarios`: lista de dicts {"label": str, "percentiles": dict}. Mismo patrón glow.
    """
    x = np.arange(n_months + 1) / 12.0
    fig = go.Figure()
    for i, sc in enumerate(scenarios[:4]):
        color, glow, band_fill = _COMPARE_STYLES[i % len(_COMPARE_STYLES)]
        p = sc["percentiles"]
        # Banda P5-P95 tenue
        fig.add_trace(go.Scatter(x=x, y=p["P95"], mode="lines", line=dict(width=0),
                                 hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=x, y=p["P5"], mode="lines", line=dict(width=0),
                                 fill="tonexty", fillcolor=band_fill,
                                 hoverinfo="skip", showlegend=False))
        # Mediana con glow (2 capas + línea)
        fig.add_trace(go.Scatter(x=x, y=p["P50"], mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=glow[0], width=18, shape="spline", smoothing=0.5)))
        fig.add_trace(go.Scatter(x=x, y=p["P50"], mode="lines", hoverinfo="skip", showlegend=False,
                                 line=dict(color=glow[1], width=9, shape="spline", smoothing=0.5)))
        fig.add_trace(go.Scatter(x=x, y=p["P50"], mode="lines", name=sc["label"],
                                 line=dict(color=color, width=4, shape="spline", smoothing=0.5),
                                 hovertemplate=f"{sc['label']}<br>Año %{{x:.1f}}: $%{{y:,.0f}}<extra></extra>"))
    if target:
        fig.add_hline(y=target, line=dict(color=S.GREEN, width=2, dash="dash"),
                      annotation_text="Meta", annotation_position="top left",
                      annotation_font=dict(color=S.GREEN, size=12))

    _apply_dlp_layout(fig, "Años", "Patrimonio (USD)", height=340)
    # Escala Y log si hay crecimiento compuesto fuerte: hace visible la trayectoria y las
    # diferencias entre portafolios en TODOS los años, no solo en el tramo final.
    bounds: list = []
    for sc in scenarios[:4]:
        bounds.append(sc["percentiles"]["P5"])
        bounds.append(sc["percentiles"]["P95"])
    _apply_growth_scale(fig, bounds)
    fig.update_layout(showlegend=True, legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        bgcolor="rgba(0,0,0,0)", font=dict(color=S.TEXT_MD, size=12)))
    return fig


# Colores distintos por slice del portafolio (el primero es el brand)
DONUT_COLORS = [S.ORANGE, S.BLUE, S.GREEN, S.GOLD, "#B388FF", "#21D4C0", "#FF6FB5", S.TEXT_LO]


def allocation_donut(items: list[dict], lead_color: str | None = None) -> go.Figure:
    """Dona de la composición del portafolio. `items`: [{symbol, weight}, ...].

    `lead_color`: si se pasa, la paleta arranca por ese color (identidad A=naranja / B=azul)
    y el número del centro toma ese color.
    """
    labels = [it["symbol"] for it in items]
    values = [max(float(it.get("weight", 0)), 0.0) for it in items]
    base = DONUT_COLORS
    if lead_color and lead_color in base:
        i0 = base.index(lead_color)
        base = base[i0:] + base[:i0]
    colors = [base[i % len(base)] for i in range(len(items))]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.62, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color=S.BG_CARD, width=3)),
        textinfo="label+percent", textposition="outside",
        textfont=dict(family=S.MONO, color=S.TEXT_MD, size=13),
        hovertemplate="%{label}: %{percent}<extra></extra>",
    ))
    n = len(items)
    fig.add_annotation(text=f"<b>{n}</b><br><span style='font-size:11px'>activo{'s' if n != 1 else ''}</span>",
                       showarrow=False,
                       font=dict(family=S.MONO, color=(lead_color or S.TEXT_HI), size=24))
    fig.update_layout(height=260, paper_bgcolor=S.BG_CARD, plot_bgcolor=S.BG_CARD,
                      showlegend=False, margin=dict(l=16, r=16, t=16, b=16),
                      font=dict(family=S.MONO, color=S.TEXT_MD),
                      hoverlabel=dict(bgcolor=S.BG_CARD2, bordercolor=S.GOLD_HOVER,
                                      font=dict(family=S.MONO, color=S.TEXT_MD)))
    return fig


def stress_bar(stress: dict) -> go.Figure:
    """Barras horizontales: caída estimada del portafolio ante cada evento histórico."""
    evs = stress["events"]
    names = [e["name"] for e in evs]
    dd = [e["portfolio_drawdown"] * 100 for e in evs]
    vals = [e["value_after"] for e in evs]
    fig = go.Figure(go.Bar(
        y=names, x=dd, orientation="h",
        marker=dict(color=S.RED, line=dict(width=0)),
        text=[f"−{d:.0f}%  →  ${v:,.0f}" for d, v in zip(dd, vals)],
        textposition="auto", textfont=dict(color=S.TEXT_HI, size=12, family=S.MONO),
        hovertemplate="%{y}: −%{x:.0f}%<extra></extra>",
    ))
    _apply_dlp_layout(fig, "Caída estimada de tu portafolio (%)", "", height=300)
    fig.update_yaxes(autorange="reversed", automargin=True)
    fig.update_layout(hovermode="y", margin=dict(l=180, r=30, t=30, b=55))
    return fig


def sequence_lines(sequence: dict) -> go.Figure:
    """3 trayectorias de patrimonio con el mismo set de retornos en distinto orden."""
    fig = go.Figure()
    colors = [S.BLUE, S.ORANGE, S.GOLD]
    for (name, data), col in zip(sequence["orderings"].items(), colors):
        path = data["path"]
        x = list(range(len(path)))
        fig.add_trace(go.Scatter(
            x=x, y=path, mode="lines",
            name=f"{name} → ${data['terminal']:,.0f}",
            line=dict(color=col, width=3.5, shape="spline", smoothing=0.4),
            hovertemplate=f"{name}<br>Año %{{x}}: $%{{y:,.0f}}<extra></extra>"))
    _apply_dlp_layout(fig, "Años", "Patrimonio (USD)", height=320)
    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    fig.update_layout(showlegend=True, legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
        bgcolor="rgba(0,0,0,0)", font=dict(color=S.TEXT_MD, size=12)))
    return fig


def ruin_gauge(prob_ruin: float) -> go.Figure:
    """Gauge de probabilidad de ruina (modo retiro). Verde <5%, naranja 5-20%, rojo >20%."""
    pct = max(0.0, min(1.0, prob_ruin)) * 100.0
    color = S.GREEN if prob_ruin < 0.05 else (S.ORANGE if prob_ruin < 0.20 else S.RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": "%", "valueformat": ".0f",
                "font": {"size": 46, "color": color, "family": S.MONO}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": S.TEXT_LO,
                     "tickfont": {"color": S.TEXT_LO, "size": 11, "family": S.MONO}},
            "bar": {"color": color, "thickness": 0.32},
            "bgcolor": S.BG_CARD2, "borderwidth": 0,
            "steps": [
                {"range": [0, 5], "color": "rgba(0,255,136,0.12)"},
                {"range": [5, 20], "color": "rgba(255,184,77,0.12)"},
                {"range": [20, 100], "color": "rgba(255,59,92,0.12)"},
            ],
            "threshold": {"line": {"color": color, "width": 3}, "value": pct},
        },
        domain={"x": [0, 1], "y": [0, 1]},
    ))
    fig.update_layout(height=240, paper_bgcolor=S.BG_CARD,
                      font=dict(family=S.MONO, color=S.TEXT_MD),
                      margin=dict(l=30, r=30, t=20, b=10),
                      title=dict(text="Probabilidad de ruina", font=dict(color=S.TEXT_LO, size=13),
                                 x=0.5, y=0.02))
    return fig
