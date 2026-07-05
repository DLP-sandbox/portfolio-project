"""Proyección de Portafolio — entry point Streamlit (embed 1:1).

Compara hasta dos portafolios (A vs B) con simulaciones Montecarlo. Proyección
probabilística, no predicción. Sin barra lateral ni persistencia (no guarda nada).
"""
from __future__ import annotations

import hmac
import random
import re
import sys
import time
from pathlib import Path

# ── Bootstrap de path ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from core import interpret, portfolio_import, presets, sequence, stress  # noqa: E402
from core.montecarlo import run_montecarlo  # noqa: E402
from dashboard import charts, components  # noqa: E402
from dashboard import styles as S  # noqa: E402
from dashboard.styles import inject_css  # noqa: E402
from data import market_data  # noqa: E402
from data import tickers as tdir  # noqa: E402

DEFAULT_A = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "weight": 60.0},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "weight": 40.0},
]
DEFAULT_B = [{"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "weight": 100.0}]
MAX_ASSETS = 8
BENCHMARK_SPECS = [("S&P 500 puro", ["SPY"], [100.0]), ("60/40", ["SPY", "BND"], [60.0, 40.0])]
PCOLOR = {"A": S.ORANGE, "B": S.BLUE}
PLABEL = {"A": "Portafolio A", "B": "Portafolio B"}


# ── Password gate (Patrón 1) ─────────────────────────────────────────────────
def _require_password() -> None:
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected or st.session_state.get("_auth_ok"):
        return
    with st.form("auth", clear_on_submit=False):
        st.markdown("### Proyección de Portafolio")
        pwd = st.text_input("pwd", type="password", label_visibility="collapsed", placeholder="Contraseña")
        ok = st.form_submit_button("Entrar", use_container_width=True, type="primary")
    if ok:
        if hmac.compare_digest((pwd or "").encode(), expected.encode()):
            st.session_state._auth_ok = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()


# ── Simulación ───────────────────────────────────────────────────────────────
def compute(inputs: dict) -> dict:
    stats = market_data.get_market_stats(inputs["tickers"], inputs["historical_window_years"])
    return run_montecarlo(
        initial_capital=inputs["initial_capital"], monthly_contribution=inputs["monthly_contribution"],
        horizon_years=inputs["horizon_years"], tickers=inputs["tickers"], weights=inputs["weights"],
        n_simulations=inputs["n_simulations"], distribution=inputs["distribution"],
        annual_fees_pct=inputs["annual_fees_pct"], annual_tax_on_gains_pct=inputs["annual_tax_on_gains_pct"],
        historical_window_years=inputs["historical_window_years"], target=inputs["target"],
        random_seed=inputs["random_seed"], market_stats=stats)


def run_benchmarks(base: dict) -> list[dict]:
    return [{"label": label, "result": compute(dict(base, tickers=tk, weights=wt))}
            for label, tk, wt in BENCHMARK_SPECS]


def _build_extras(inputs: dict, result: dict) -> dict:
    extras: dict = {}
    if inputs.get("show_stress"):
        try:
            p50 = float(np.percentile(result["final_values"], 50))
            extras["stress"] = stress.compute_stress(inputs["tickers"], inputs["weights"], p50,
                                                     inputs["historical_window_years"])
        except Exception:
            extras["stress"] = None
    if inputs.get("show_sequence"):
        try:
            stats = market_data.get_market_stats(inputs["tickers"], inputs["historical_window_years"])
            am, asd = sequence.portfolio_annual_moments(stats, inputs["weights"])
            extras["sequence"] = sequence.sequence_demo(
                inputs["initial_capital"], inputs["monthly_contribution"],
                inputs["horizon_years"], am, asd, inputs["random_seed"])
        except Exception:
            extras["sequence"] = None
    return extras


# ── Estado de portafolios (A siempre; B opcional) ────────────────────────────
def _init_portfolios() -> None:
    st.session_state.setdefault("portfolios", {"A": [dict(x) for x in DEFAULT_A]})


def set_portfolio(pid: str, symbols: list[str], weights: list[float]) -> None:
    st.session_state.portfolios[pid] = [
        {"symbol": s, "name": tdir.get_name(s), "weight": float(w)} for s, w in zip(symbols, weights)]


def _add_ticker(pid: str, symbol: str, name: str) -> None:
    pf = st.session_state.portfolios[pid]
    if any(it["symbol"] == symbol for it in pf):
        return
    if len(pf) >= MAX_ASSETS:
        st.toast(f"Máximo {MAX_ASSETS} activos.")
        return
    pf.append({"symbol": symbol, "name": name, "weight": 10.0})


def _palette_for(lead: str) -> list[str]:
    base = charts.DONUT_COLORS
    if lead in base:
        i0 = base.index(lead)
        return base[i0:] + base[:i0]
    return list(base)


# ── Campo numérico con separador de miles (comas) y SIN decimales ────────────
def _parse_num(txtk: str, rawk: str, min_v: float, max_v: float | None) -> None:
    cleaned = re.sub(r"[^0-9]", "", st.session_state.get(txtk, "") or "")
    val = float(int(cleaned)) if cleaned else 0.0
    if max_v is not None:
        val = min(val, float(max_v))
    val = max(val, float(min_v))
    st.session_state[rawk] = val
    st.session_state[txtk] = f"{val:,.0f}"   # reformatea con comas (permitido en callback)


def num_input(label: str, default: float, key: str, help: str | None = None,
              min_value: float = 0, max_value: float | None = None) -> float:
    """Casilla de número que se MUESTRA con comas de miles y sin decimales (ej: 10,000)."""
    rawk, txtk = f"{key}__raw", f"{key}__txt"
    if rawk not in st.session_state:
        st.session_state[rawk] = float(default)
        st.session_state[txtk] = f"{float(default):,.0f}"
    st.text_input(label, key=txtk, help=help,
                  on_change=_parse_num, args=(txtk, rawk, float(min_value), max_value))
    return st.session_state[rawk]


# ── Buscador + lista + dona (por portafolio) ─────────────────────────────────
def render_portfolio_builder(pid: str, capital: float) -> tuple[list[str], list[float], float]:
    pf = st.session_state.portfolios[pid]
    lead = PCOLOR[pid]
    palette = _palette_for(lead)
    if st.session_state.pop(f"_clear_{pid}", False):
        st.session_state[f"q_{pid}"] = ""

    pc1, pc2 = st.columns([3, 1])
    preset_opts = [("", "Cargar portafolio predefinido…")] + presets.list_presets()
    chosen = pc1.selectbox("Atajo: portafolio listo", options=[k for k, _ in preset_opts],
                           format_func=lambda k: dict(preset_opts)[k], key=f"preset_{pid}",
                           help="Carga un portafolio ya armado (S&P 500, 60/40, All-Weather) y "
                                "luego ajústalo a gusto.")
    pc2.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
    if pc2.button("Cargar", use_container_width=True, key=f"cargar_{pid}") and chosen:
        p = presets.get_preset(chosen)
        set_portfolio(pid, p["tickers"], p["weights"])
        st.rerun()

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        st.text_input("Buscar activo (NYSE / NASDAQ)", key=f"q_{pid}",
                      placeholder="🔍  Símbolo o nombre (ej: AAPL, Apple) y Enter",
                      help="Escribe el símbolo o el nombre de una acción o ETF y presiona Enter "
                           "para ver resultados y agregarlo a tu portafolio.")
        query = st.session_state.get(f"q_{pid}", "")
        if query:
            results = tdir.search_tickers(query, limit=6)
            with components.search_menu(pid):
                st.markdown("<div class='dlp-search-hd'>Resultados — NYSE / NASDAQ</div>",
                            unsafe_allow_html=True)
                if not results:
                    st.caption("Sin coincidencias. Prueba con otro símbolo o nombre.")
                for r in results:
                    rc1, rc2 = st.columns([6, 1])
                    rc1.markdown(components.ticker_result_card(r), unsafe_allow_html=True)
                    if rc2.button("➕", key=f"add_{pid}_{r['symbol']}", use_container_width=True):
                        _add_ticker(pid, r["symbol"], r["name"])
                        st.session_state[f"_clear_{pid}"] = True
                        st.rerun()

        st.markdown("<div class='dlp-side-title'>En tu portafolio</div>", unsafe_allow_html=True)
        if not pf:
            st.caption("Agrega al menos un activo desde el buscador.")
        total_w = sum(max(it["weight"], 0) for it in pf)
        for i, it in enumerate(pf):
            dot = palette[i % len(palette)]
            wc1, wc2, wc3 = st.columns([3, 2, 1])
            usd = (it["weight"] / total_w * capital) if total_w > 0 else 0
            wc1.markdown(
                f"<div style='padding-top:8px'><span style='color:{dot};font-size:16px'>●</span> "
                f"<b style='color:{S.TEXT_HI};font-size:15px'>{it['symbol']}</b> "
                f"<span style='color:{S.TEXT_LO};font-size:12px'>· ${usd:,.0f}</span><br>"
                f"<span style='color:{S.TEXT_LO};font-size:11px;padding-left:20px'>{it['name'][:24]}</span></div>",
                unsafe_allow_html=True)
            it["weight"] = wc2.number_input(
                "peso", value=float(it["weight"]), min_value=0.0, max_value=100.0, step=5.0,
                key=f"pw_{pid}_{it['symbol']}", label_visibility="collapsed", format="%.0f")
            if wc3.button("✕", key=f"rm_{pid}_{it['symbol']}", use_container_width=True):
                st.session_state.portfolios[pid] = [x for x in pf if x["symbol"] != it["symbol"]]
                st.rerun()
        st.caption(f"Suma de pesos: {total_w:.0f}% · se normaliza al 100% automáticamente.")

    with right:
        if pf and total_w > 0:
            st.plotly_chart(charts.allocation_donut(pf, lead_color=lead), use_container_width=True,
                            config={"displayModeBar": False}, key=f"donut_{pid}")

    symbols = [it["symbol"] for it in pf]
    weights = [it["weight"] for it in pf]
    return symbols, weights, sum(max(w, 0) for w in weights)


# ── Importar portafolios candidatos desde CSV ────────────────────────────────
def _load_candidate_into(pid: str, cand: dict) -> None:
    """Carga un candidato importado en el slot A o B usando el modelo existente."""
    symbols = [it["symbol"] for it in cand["items"]]
    weights = [float(it["weight"]) for it in cand["items"]]
    set_portfolio(pid, symbols, weights)


def render_candidate_importer(capital: float, aporte: float, horizonte: int, meta: float) -> None:
    """Expander para importar portafolios candidatos desde un CSV (formato DLP).

    Reusa el flujo ya probado: cada candidato se puede cargar en A o en B con un clic,
    y hay un botón para comparar TODOS los candidatos de una vez (ranking + overlay).
    Es aditivo: no toca la lógica de simulación ni la vista A/B.
    """
    with st.expander("⬆  Importar portafolios candidatos (CSV)"):
        st.caption("Sube el CSV de candidatos (columnas: Portafolio, Ticker, Nombre, Clase, Peso%). "
                   "Cargamos cada candidato listo para simular — sin afectar nada de lo demás.")
        up = st.file_uploader("archivo CSV", type=["csv"], key="cand_csv",
                              label_visibility="collapsed")
        if up is not None:
            try:
                raw = up.getvalue().decode("utf-8-sig", errors="replace")
                st.session_state["cand_ports"] = portfolio_import.parse_portfolios_csv(raw)
            except Exception as e:
                st.session_state.pop("cand_ports", None)
                st.error(f"No se pudo leer el CSV: {e}")

        cands = st.session_state.get("cand_ports") or []
        if not cands:
            return
        st.markdown(f"<div class='dlp-side-title'>{len(cands)} candidatos importados</div>",
                    unsafe_allow_html=True)
        for idx, cand in enumerate(cands):
            compo = " · ".join(f"{round(it['weight'])}% {it['symbol']}" for it in cand["items"][:4])
            more = " …" if len(cand["items"]) > 4 else ""
            cc1, cc2, cc3 = st.columns([3.2, 1, 1])
            cc1.markdown(
                f"<div style='padding-top:6px'><b style='color:{S.TEXT_HI};font-size:14px'>{cand['name']}</b><br>"
                f"<span style='color:{S.TEXT_LO};font-size:11px'>{len(cand['items'])} activos · {compo}{more}</span></div>",
                unsafe_allow_html=True)
            if cc2.button("→ A", key=f"cand_a_{idx}", use_container_width=True):
                _load_candidate_into("A", cand)
                st.rerun()
            if cc3.button("→ B", key=f"cand_b_{idx}", use_container_width=True):
                st.session_state.portfolios.setdefault("B", [])
                _load_candidate_into("B", cand)
                st.rerun()
        if len(cands) >= 2 and st.button(
                f"◈  Comparar los {len(cands)} candidatos — 10.000 escenarios",
                key="cand_compare_btn", use_container_width=True, type="primary"):
            st.session_state["_run_cands"] = {
                "initial_capital": capital, "monthly_contribution": aporte,
                "horizon_years": int(horizonte), "target": (meta if meta > 0 else None),
                "candidates": cands}
            st.session_state["result_A"] = None   # oculta la vista A/B para no encimar
            st.session_state["result_B"] = None


# ── Inputs (plan compartido + A/B + avanzadas) ───────────────────────────────
def render_inputs() -> dict | None:
    _init_portfolios()
    pfA = st.session_state.portfolios["A"]
    a_ok = bool(pfA) and sum(max(it["weight"], 0) for it in pfA) > 0
    components.stepper(a_ok)

    with components.card("plan"):
        components.card_head("◆", "Tu plan", "Aplica a ambos portafolios por igual")
        c1, c2 = st.columns(2)
        with c1:
            capital = num_input("Capital inicial (USD)", 10_000, "capital", min_value=0,
                                help="El dinero con el que empiezas a invertir hoy.")
        with c2:
            aporte = num_input("Aporte mensual (USD)", 500, "aporte", min_value=0,
                               help="Cuánto sumas cada mes. El hábito de aportar es lo que más mueve el resultado.")
        c3, c4 = st.columns(2)
        with c3:
            horizonte = st.slider("Horizonte (años)", min_value=1, max_value=40, value=20,
                                  help="Por cuántos años proyectas. Más tiempo = más interés compuesto y más incertidumbre.")
        with c4:
            meta = num_input("Meta final (USD, opcional)", 0, "meta", min_value=0,
                             help="Opcional: el patrimonio que te gustaría alcanzar. Verás la probabilidad de lograrlo.")

    has_b = "B" in st.session_state.portfolios
    symB: list[str] | None = None
    wB: list[float] = []
    twB = 0.0
    with components.card("portafolio"):
        if not has_b:
            components.card_head("◆", "Tu portafolio", "Busca y agrega activos del NYSE / NASDAQ")
            symA, wA, twA = render_portfolio_builder("A", capital)
        else:
            components.card_head("◆", "Compara A vs B", "Edita ambos; la simulación corre los dos")
            tA, tB = st.tabs(["🟠  Portafolio A", "🔵  Portafolio B"])
            with tA:
                symA, wA, twA = render_portfolio_builder("A", capital)
            with tB:
                if st.button("✕  Quitar Portafolio B", key="rmb"):
                    del st.session_state.portfolios["B"]
                    st.rerun()
                symB, wB, twB = render_portfolio_builder("B", capital)

    if not has_b:
        with st.container(key="addb"):
            if st.button("＋  Agregar Portafolio B para comparar", use_container_width=True):
                st.session_state.portfolios["B"] = [dict(x) for x in DEFAULT_B]
                st.rerun()

    render_candidate_importer(capital, aporte, int(horizonte), meta)

    a_ready = bool(symA) and twA > 0
    b_ready = (not has_b) or (bool(symB) and twB > 0)

    # Defaults de avanzadas
    dist_label, fees, tax = "Normal", 0.0, 0.0
    compare = retirement = show_stress = show_sequence = False
    withdrawal = 1_500.0

    if not (a_ready and b_ready):
        msg = ("Agrega un activo al Portafolio A para proyectar" if not a_ready
               else "Agrega un activo al Portafolio B (o quítalo) para proyectar")
        st.button(f"🔒  {msg}", type="primary", use_container_width=True, disabled=True)
        return None

    with st.expander("◆ Opciones avanzadas — modelo, costos, retiro, stress, benchmarks"):
        dist_label = st.radio("Modelo de retornos", ["Normal", "t-Student (colas gordas)"],
                              horizontal=True,
                              help="t-Student suma realismo a caídas y extremos de corto/mediano plazo; "
                                   "sobre 20 años i.i.d. el efecto en el patrimonio final es modesto.")
        fc1, fc2 = st.columns(2)
        fees = fc1.number_input(
            "Fees anuales (%)", min_value=0, max_value=5, value=0, step=1, format="%d",
            help="Costo anual del fondo o portafolio (comisiones + gastos). Reduce tu rendimiento.")
        tax = fc2.number_input(
            "Impuesto anual s/ ganancias (%)", min_value=0, max_value=50, value=0, step=1, format="%d",
            help="Impuesto que pagas cada año sobre las ganancias. Aproxima una cuenta gravable.")
        compare = st.checkbox(
            "Comparar también contra benchmarks (S&P 500 puro y 60/40)",
            help="Suma al gráfico el S&P 500 y una mezcla clásica 60% acciones / 40% bonos.")
        st.divider()
        retirement = st.checkbox(
            "Modo retiro (en vez de aportar, retiras)",
            help="Simula que ya no aportas sino que retiras dinero cada mes (modo jubilación).")
        withdrawal = num_input(
            "Retiro mensual (USD) — modo retiro", 1_500, "withdrawal", min_value=0,
            help="Cuánto retiras por mes cuando activas el modo retiro.")
        cs1, cs2 = st.columns(2)
        show_stress = cs1.checkbox(
            "Stress test histórico",
            help="Estima cuánto caería cada portafolio ante una crisis como 2008 o el COVID.")
        show_sequence = cs2.checkbox(
            "Secuencia de retornos",
            help="Muestra cómo el ORDEN en que llegan los buenos y malos años cambia el resultado.")

    label = "◈  Comparar A vs B — 10.000 escenarios" if has_b else "◈  Correr proyección — 10.000 escenarios"
    if not st.button(label, type="primary", use_container_width=True):
        return None

    all_syms = list(dict.fromkeys(symA + (symB or [])))
    with st.spinner("Validando tickers…"):
        valid, invalid = market_data.validate_tickers(all_syms)
    if invalid:
        st.error(f"No se encontraron en el mercado: {', '.join(invalid)}.")
        return None

    monthly_flow = -withdrawal if retirement else aporte
    base = {
        "initial_capital": capital, "monthly_contribution": monthly_flow,
        "horizon_years": int(horizonte),
        "target": (meta if (meta > 0 and not retirement) else None),
        "historical_window_years": 10, "n_simulations": 10_000,
        "distribution": "t-student" if dist_label.startswith("t-") else "normal",
        "annual_fees_pct": fees, "annual_tax_on_gains_pct": tax,
        "compare": compare, "show_stress": show_stress, "show_sequence": show_sequence,
        "random_seed": random.randrange(1_000_000_000),  # mismo seed A y B (comparación justa)
    }
    return {
        "base": base,
        "A": {"tickers": symA, "weights": [w / twA for w in wA]},
        "B": ({"tickers": symB, "weights": [w / twB for w in wB]} if has_b else None),
    }


# ── Helpers de render ────────────────────────────────────────────────────────
def _success_color(prob: float) -> str:
    return S.GREEN if prob >= 0.70 else (S.ORANGE if prob >= 0.50 else S.RED)


def _md_money(text: str) -> str:
    """Escapa '$' para que Streamlit no lo interprete como LaTeX (solo en markdown puro)."""
    return text.replace("$", "\\$")


def _b(txt, color=S.TEXT_HI) -> str:
    return f"<b style='color:{color}'>{txt}</b>"


def _lectura_card(color: str, html: str) -> None:
    st.markdown(f"<div class='dlp-card dlp-card-left' style='border-left-color:{color};'>"
                f"<div class='kpi-label'>Lectura</div>"
                f"<div style='color:{S.TEXT_MD};font-size:15px;margin-top:8px;line-height:1.55;'>"
                f"{_md_money(html)}</div></div>", unsafe_allow_html=True)


# ── Resultados de UN portafolio (reusable: single y detalle A/B) ─────────────
def render_single(result, inputs, extras, benchmarks, kp, *, with_hero=True, with_actions=True,
                  elapsed=None) -> None:
    extras = extras or {}
    fv = result["final_values"]
    p5, p25, p50, p75, p95 = (float(np.percentile(fv, q)) for q in (5, 25, 50, 75, 95))
    years = inputs["horizon_years"]
    retirement = inputs["monthly_contribution"] < 0
    flow_label = "Retiro mensual" if retirement else "Aporte mensual"
    items = [{"symbol": t, "weight": w * 100} for t, w in zip(inputs["tickers"], inputs["weights"])]

    if with_hero:
        if result["is_sample"]:
            components.sample_data_notice()
        components.hero_card(
            glyph="◈", caption="Proyección de portafolio",
            meta_items=[("Capital inicial", components.fmt_money(inputs["initial_capital"])),
                        (flow_label, components.fmt_money(abs(inputs["monthly_contribution"]))),
                        ("Horizonte", f"{years} años")],
            highlight_label=f"Mediana a {years} años",
            highlight_value=components.fmt_money(p50), highlight_color=S.ORANGE)
        components.disclaimer_banner()

    if retirement:
        ruin = result["probability_of_ruin"]
        takeaway = (f"Retirando {_b(components.fmt_money(abs(inputs['monthly_contribution'])) + ' por mes')} durante "
                    f"{_b(str(years) + ' años')}, en {_b(f'{ruin*100:.0f}%', S.RED)} de los escenarios te quedas "
                    f"sin dinero antes de tiempo. Lo más probable es terminar con {_b(components.fmt_money(p50), S.ORANGE)}.")
    else:
        takeaway = (f"En {_b(str(years) + ' años')}, lo más probable es llegar a "
                    f"{_b(components.fmt_money(p50), S.ORANGE)}. En la mitad de los escenarios terminas entre "
                    f"{_b(components.fmt_money(p25))} y {_b(components.fmt_money(p75))}; en casos extremos, entre "
                    f"{_b(components.fmt_money(p5), S.RED)} (si va mal) y "
                    f"{_b(components.fmt_money(p95), S.GREEN)} (si va bien).")

    tab_names = ["Resumen", "¿Alcanzo mi meta?", "Riesgos"]
    if benchmarks:
        tab_names.append("Comparar")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        with components.card(f"res-top-{kp}"):
            components.card_head("◆", "Tu proyección en una frase")
            st.markdown(f"<div style='font-size:16px;color:{S.TEXT_MD};line-height:1.6;margin-bottom:6px'>"
                        f"{takeaway}</div>", unsafe_allow_html=True)
            dc, kc = st.columns([1, 1.25], gap="large")
            with dc:
                st.plotly_chart(charts.allocation_donut(items), use_container_width=True,
                                config={"displayModeBar": False}, key=f"donut_res_{kp}")
            with kc:
                # Apiladas (3 filas) para que el número entre en una sola línea
                components.kpi_tile("Si va mal", components.fmt_money(p5), S.RED, "1 de 20 (P5)")
                components.kpi_tile("Lo más probable", components.fmt_money(p50), S.ORANGE, "el del medio")
                components.kpi_tile("Si va bien", components.fmt_money(p95), S.GREEN, "1 de 20 (P95)")
        with components.card(f"res-fan-{kp}"):
            components.card_head("◆", "Tus 10.000 futuros posibles", "pasa el cursor para leer cada año")
            st.plotly_chart(charts.fan_chart(result["percentiles"], result["months"], inputs["target"]),
                            use_container_width=True, config={"displayModeBar": False}, key=f"fan_{kp}")
        with components.card(f"res-interp-{kp}"):
            components.card_head("◆", "¿Qué significa esto?")
            st.markdown(_md_money(interpret.interpret_locally(result, inputs, extras.get("stress"))))

    with tabs[1]:
        with components.card(f"dist-hist-{kp}"):
            components.card_head("◆", "Distribución del patrimonio final", "dónde caen los 10.000 resultados")
            st.plotly_chart(charts.histogram_final(fv), use_container_width=True,
                            config={"displayModeBar": False}, key=f"hist_{kp}")
        if retirement:
            ruin = result["probability_of_ruin"]
            col = S.GREEN if ruin < 0.05 else S.ORANGE if ruin < 0.20 else S.RED
            with components.card(f"dist-ruin-{kp}"):
                components.card_head("◆", "Riesgo de ruina (modo retiro)")
                g, t = st.columns([1, 1])
                g.plotly_chart(charts.ruin_gauge(ruin), use_container_width=True,
                               config={"displayModeBar": False}, key=f"ruin_{kp}")
                with t:
                    _lectura_card(col, f"Retirando {components.fmt_money(abs(inputs['monthly_contribution']))}/mes, "
                                  f"tu capital se agotó antes de los {years} años en "
                                  f"<b style='color:{col}'>{ruin*100:.0f}%</b> de los escenarios.")
        elif inputs["target"]:
            prob = result["prob_target"] or 0.0
            with components.card(f"dist-meta-{kp}"):
                components.card_head("◆", "Probabilidad de alcanzar tu meta")
                g, t = st.columns([1, 1])
                g.plotly_chart(charts.success_gauge(prob, f"Meta {components.fmt_money(inputs['target'])}"),
                               use_container_width=True, config={"displayModeBar": False}, key=f"gauge_{kp}")
                with t:
                    _lectura_card(_success_color(prob),
                                  f"En <b style='color:{_success_color(prob)}'>{prob*100:.0f}%</b> de los 10.000 "
                                  f"escenarios alcanzaste {components.fmt_money(inputs['target'])} a {years} años. "
                                  f"No es garantía: los retornos futuros pueden diferir.")
        else:
            st.info("Ingresa una meta de patrimonio en 'Tu plan' para ver la probabilidad de alcanzarla.")

    with tabs[2]:
        with components.card(f"risk-metrics-{kp}"):
            components.card_head("◆", "Riesgos en detalle", "para quien quiere profundizar")
            m = st.columns(4)
            with m[0]:
                components.kpi_tile("Caída típica", components.fmt_pct(result["max_drawdown_typical"]),
                                    S.BLUE, "en un mal momento")
            with m[1]:
                components.kpi_tile("Eficiencia", f"{result['expected_sharpe']:.2f}", S.GOLD, "Sharpe")
            with m[2]:
                components.kpi_tile("Riesgo de ruina", components.fmt_pct(result["probability_of_ruin"]),
                                    S.TEXT_LO, "llega a $0")
            with m[3]:
                if retirement:
                    components.kpi_tile("Retiro por año", components.fmt_money(abs(inputs["monthly_contribution"]) * 12),
                                        S.TEXT_MD, "lo que sacas")
                else:
                    components.kpi_tile("Lo que aportas", components.fmt_money(
                        inputs["initial_capital"] + inputs["monthly_contribution"] * 12 * years),
                        S.TEXT_MD, "sin rendimiento")
        sd = extras.get("stress")
        if sd:
            with components.card(f"risk-stress-{kp}"):
                components.card_head("◆", "Stress test — eventos históricos", f"β={sd['beta']:.2f} al S&P 500")
                st.plotly_chart(charts.stress_bar(sd), use_container_width=True,
                                config={"displayModeBar": False}, key=f"stress_{kp}")
                st.caption(_md_money(f"◇ Escalado por la beta del portafolio sobre la mediana "
                           f"({components.fmt_money(sd['reference_value'])}). Magnitud de referencia, no predicción."))
        seq = extras.get("sequence")
        if seq:
            with components.card(f"risk-seq-{kp}"):
                components.card_head("◆", "Riesgo de secuencia de retornos")
                st.plotly_chart(charts.sequence_lines(seq), use_container_width=True,
                                config={"displayModeBar": False}, key=f"seq_{kp}")
                o = seq["orderings"]
                wf, bf = o["Peores años primero"]["terminal"], o["Mejores años primero"]["terminal"]
                if seq["mode"] == "acumulación":
                    st.caption(_md_money(f"Mismo set de retornos, distinto orden. En acumulación, peores años "
                               f"primero termina mejor ({components.fmt_money(wf)} vs {components.fmt_money(bf)})."))
                else:
                    st.caption(_md_money(f"En retiro, peores años primero termina peor "
                               f"({components.fmt_money(wf)} vs {components.fmt_money(bf)})."))
        if not sd and not seq:
            st.info("Activa 'Stress test' o 'Secuencia de retornos' en Opciones avanzadas para más análisis.")

    if benchmarks:
        with tabs[3]:
            scen = [{"label": "Tu portafolio", "percentiles": result["percentiles"]}]
            scen += [{"label": b["label"], "percentiles": b["result"]["percentiles"]} for b in benchmarks]
            with components.card(f"cmp-{kp}"):
                components.card_head("◆", "Tu portafolio vs benchmarks", "S&P 500 puro · 60/40")
                st.plotly_chart(charts.comparison_fan_chart(scen, result["months"], inputs["target"]),
                                use_container_width=True, config={"displayModeBar": False}, key=f"cmpfan_{kp}")

    if with_actions:
        st.divider()
        _render_pdf_button(result, inputs, benchmarks)
        if elapsed is not None:
            dist = "t-Student" if inputs["distribution"] == "t-student" else "Normal"
            st.caption(f"◇ {inputs['n_simulations']:,} escenarios · {dist} · {elapsed:.1f}s · "
                       f"ventana {inputs['historical_window_years']} años")


# ── Resultados COMPARATIVOS A vs B ───────────────────────────────────────────
def _compare_verdict(rA, iA, rB) -> tuple[str, str]:
    medA, medB = (float(np.percentile(rA["final_values"], 50)), float(np.percentile(rB["final_values"], 50)))
    ddA, ddB = rA["max_drawdown_typical"] * 100, rB["max_drawdown_typical"] * 100
    high, hcol = ("A", S.ORANGE) if medA >= medB else ("B", S.BLUE)
    low_dd, lcol = ("A", S.ORANGE) if ddA <= ddB else ("B", S.BLUE)
    m_high, m_low = (medA, medB) if high == "A" else (medB, medA)
    dd_low_val = min(ddA, ddB)
    dd_high_val = max(ddA, ddB)
    parts = [f"En la mediana, el {_b(PLABEL[high], hcol)} proyecta más "
             f"({components.fmt_money(m_high)} vs {components.fmt_money(m_low)})."]
    if low_dd == high:
        parts.append(f"Y además es el más estable (caída típica {dd_low_val:.0f}% vs {dd_high_val:.0f}%): "
                     f"luce mejor en crecimiento y en estabilidad — aunque no es garantía.")
        lead = hcol
    else:
        parts.append(f"Pero el {_b(PLABEL[low_dd], lcol)} es más estable (caída típica menor: "
                     f"{dd_low_val:.0f}% vs {dd_high_val:.0f}%). Es un trade-off entre crecimiento y "
                     f"estabilidad: depende de tu tolerancia al riesgo.")
        lead = S.GOLD
    if iA.get("target"):
        pA, pB = (rA["prob_target"] or 0) * 100, (rB["prob_target"] or 0) * 100
        bp, bpcol = ("A", S.ORANGE) if pA >= pB else ("B", S.BLUE)
        parts.append(f"Para tu meta, el {_b(PLABEL[bp], bpcol)} tiene mayor probabilidad de alcanzarla "
                     f"({max(pA, pB):.0f}% vs {min(pA, pB):.0f}%).")
    return " ".join(parts), lead


def _compo(inputs) -> str:
    """Resumen corto de composición: '60% SPY · 40% BND'."""
    pairs = sorted(zip(inputs["tickers"], inputs["weights"]), key=lambda x: -x[1])
    s = " · ".join(f"{round(w * 100)}% {t}" for t, w in pairs[:3])
    return s + (" …" if len(pairs) > 3 else "")


def _side_head(pid: str, med: float, compo: str) -> str:
    col = PCOLOR[pid]
    return (f"<div class='dlp-side'><div class='nm' style='color:{col}'>{PLABEL[pid]}</div>"
            f"<div class='big' style='color:{col}'>{components.fmt_money(med)}</div>"
            f"<div class='sub'>mediana · {compo}</div></div>")


def _metric_bars(rA, rB, iA) -> str:
    """Barras enfrentadas A (naranja) vs B (azul) por métrica, con ◆ en el ganador."""
    def q(fv, p):
        return float(np.percentile(fv, p))
    fvA, fvB = rA["final_values"], rB["final_values"]
    rows = [("Mediana", q(fvA, 50), q(fvB, 50), "high", "money"),
            ("Si va mal (P5)", q(fvA, 5), q(fvB, 5), "high", "money"),
            ("Si va bien (P95)", q(fvA, 95), q(fvB, 95), "high", "money")]
    if iA.get("target"):
        rows.append(("Prob. de alcanzar la meta", (rA["prob_target"] or 0) * 100,
                     (rB["prob_target"] or 0) * 100, "high", "pct"))
    rows += [("Caída típica (menos es mejor)", rA["max_drawdown_typical"] * 100,
              rB["max_drawdown_typical"] * 100, "low", "pct"),
             ("Eficiencia (Sharpe)", rA["expected_sharpe"], rB["expected_sharpe"], "high", "num")]

    def fmt(v, kind):
        return components.fmt_money(v) if kind == "money" else (f"{v:.0f}%" if kind == "pct" else f"{v:.2f}")

    html = ""
    for name, a, b, better, kind in rows:
        a_win = (a >= b) if better == "high" else (a <= b)
        mx = max(abs(a), abs(b)) or 1.0
        wa, wb = max(6, abs(a) / mx * 100), max(6, abs(b) / mx * 100)
        aw = " m-win" if a_win else ""
        bw = " m-win" if not a_win else ""
        html += (
            f"<div class='dlp-vsm'><div class='m-lbl'>{name}</div>"
            f"<div class='m-row'><span class='m-tag' style='color:{S.ORANGE}'>A</span>"
            f"<div class='m-track'><div class='m-fill' style='width:{wa:.0f}%;background:{S.ORANGE}'></div></div>"
            f"<span class='m-val{aw}'>{fmt(a, kind)}</span></div>"
            f"<div class='m-row'><span class='m-tag' style='color:{S.BLUE}'>B</span>"
            f"<div class='m-track'><div class='m-fill' style='width:{wb:.0f}%;background:{S.BLUE}'></div></div>"
            f"<span class='m-val{bw}'>{fmt(b, kind)}</span></div></div>")
    return html


def render_compare(rA, iA, exA, rB, iB, exB, benchmarks, elapsed=None) -> None:
    components.disclaimer_banner()
    medA = float(np.percentile(rA["final_values"], 50))
    medB = float(np.percentile(rB["final_values"], 50))
    itemsA = [{"symbol": t, "weight": w * 100} for t, w in zip(iA["tickers"], iA["weights"])]
    itemsB = [{"symbol": t, "weight": w * 100} for t, w in zip(iB["tickers"], iB["weights"])]

    # Cara a cara: A · VS · B con dona e identidad de color
    with components.card("cmp-vs"):
        components.card_head("◆", "Cara a cara", "Portafolio A vs Portafolio B")
        ca, cv, cb = st.columns([1, 0.22, 1])
        with ca:
            st.markdown(_side_head("A", medA, _compo(iA)), unsafe_allow_html=True)
            st.plotly_chart(charts.allocation_donut(itemsA, lead_color=S.ORANGE), use_container_width=True,
                            config={"displayModeBar": False}, key="vs_dA")
        with cv:
            st.markdown("<div class='dlp-vs-badge'><span>VS</span></div>", unsafe_allow_html=True)
        with cb:
            st.markdown(_side_head("B", medB, _compo(iB)), unsafe_allow_html=True)
            st.plotly_chart(charts.allocation_donut(itemsB, lead_color=S.BLUE), use_container_width=True,
                            config={"displayModeBar": False}, key="vs_dB")

    # Veredicto honesto
    verdict, lead = _compare_verdict(rA, iA, rB)
    with components.card("cmp-verdict"):
        components.card_head("◆", "Veredicto", "¿cuál proyecta mejor?")
        components.verdict_card(lead, verdict)

    # Métrica a métrica (barras enfrentadas)
    with components.card("cmp-bars"):
        components.card_head("◆", "Métrica a métrica", "◆ = mejor")
        st.markdown(_metric_bars(rA, rB, iA), unsafe_allow_html=True)

    # Proyección comparada (overlay)
    with components.card("cmp-fan"):
        components.card_head("◆", "Proyección comparada", "mediana + rango de cada portafolio")
        scen = [{"label": "Portafolio A", "percentiles": rA["percentiles"]},
                {"label": "Portafolio B", "percentiles": rB["percentiles"]}]
        if benchmarks:
            scen += [{"label": b["label"], "percentiles": b["result"]["percentiles"]} for b in benchmarks]
        st.plotly_chart(charts.comparison_fan_chart(scen, rA["months"], iA["target"]),
                        use_container_width=True, config={"displayModeBar": False}, key="cmp_fan")

    with st.expander("Ver detalle de cada portafolio"):
        dtA, dtB = st.tabs(["🟠  Detalle A", "🔵  Detalle B"])
        with dtA:
            render_single(rA, iA, exA, None, "dA", with_hero=False, with_actions=False)
        with dtB:
            render_single(rB, iB, exB, None, "dB", with_hero=False, with_actions=False)

    st.divider()
    _render_pdf_button(rA, iA, benchmarks)
    if elapsed is not None:
        dist = "t-Student" if iA["distribution"] == "t-student" else "Normal"
        st.caption(f"◇ 2 portafolios × {iA['n_simulations']:,} escenarios · {dist} · {elapsed:.1f}s · "
                   f"ventana {iA['historical_window_years']} años")


def _render_pdf_button(result, inputs, benchmarks) -> None:
    """Un solo botón amarillo: al presionarlo muestra un spinner evidente, genera el PDF y lo descarga."""
    from dashboard import pdf_report
    slot = st.empty()
    if st.session_state.get("_pdf_loading"):
        slot.markdown(components.spinner_ring("Generando tu PDF…"), unsafe_allow_html=True)
        try:
            bench = benchmarks if benchmarks is not None else run_benchmarks(inputs)
            st.session_state["pdf_bytes"] = pdf_report.generate_report(result, inputs, bench)
        except Exception:
            st.session_state["pdf_bytes"] = None
        st.session_state["_pdf_loading"] = False
        st.session_state["_pdf_just"] = True
        st.rerun()
    elif st.session_state.get("pdf_bytes"):
        st.download_button("⬇  Descargar PDF (resumen + análisis)", data=st.session_state["pdf_bytes"],
                           file_name="proyeccion_portafolio.pdf", mime="application/pdf",
                           use_container_width=True, key="pdfdl")
        if st.session_state.pop("_pdf_just", False):
            import streamlit.components.v1 as stc
            stc.html("<script>setTimeout(function(){var b=window.parent.document."
                     "querySelector('.st-key-pdfdl button'); if(b){b.click();}}, 250);</script>", height=0)
    else:
        if slot.button("▸  Generar y descargar PDF", use_container_width=True, key="pdfgo"):
            st.session_state["_pdf_loading"] = True
            st.rerun()


# ── Comparación de candidatos importados (N portafolios) ─────────────────────
def _compute_candidates(spec: dict) -> None:
    """Corre la simulación de cada candidato importado y guarda resultados en sesión.

    Mismo seed para todos → comparación justa. Cada compute() libera su matriz de paths
    (fix de memoria previo), así que correr varios en secuencia es seguro.
    """
    seed = random.randrange(1_000_000_000)
    cands = spec["candidates"][:4]   # el chart comparativo soporta hasta 4
    results: list[dict] = []
    with st.spinner(f"Corriendo 10.000 escenarios para {len(cands)} candidatos…"):
        for cand in cands:
            syms = [it["symbol"] for it in cand["items"]]
            wts = [max(float(it["weight"]), 0.0) for it in cand["items"]]
            tot = sum(wts) or 1.0
            inputs = {
                "initial_capital": spec["initial_capital"],
                "monthly_contribution": spec["monthly_contribution"],
                "horizon_years": spec["horizon_years"], "target": spec["target"],
                "historical_window_years": 10, "n_simulations": 10_000,
                "distribution": "normal", "annual_fees_pct": 0.0,
                "annual_tax_on_gains_pct": 0.0, "random_seed": seed,
                "tickers": syms, "weights": [w / tot for w in wts],
            }
            try:
                res = compute(inputs)
            except Exception:
                res = None
            results.append({"name": cand["name"], "inputs": inputs, "result": res})
    st.session_state["cand_results"] = results
    st.session_state["cand_plan"] = {"horizon_years": spec["horizon_years"], "target": spec["target"]}


def _cand_metric_rows(results: list[dict], target: float | None) -> list[dict]:
    rows = []
    for r in results:
        res = r["result"]
        fv = res["final_values"]
        rows.append({
            "name": r["name"], "result": res,
            "p50": float(np.percentile(fv, 50)), "p5": float(np.percentile(fv, 5)),
            "p95": float(np.percentile(fv, 95)), "dd": res["max_drawdown_typical"],
            "sharpe": res["expected_sharpe"],
            "prob": (res["prob_target"] or 0.0) if target else None,
        })
    return rows


def _candidates_table(rows: list[dict], target: float | None, best_name: str) -> str:
    """Tabla-ranking reusando el estilo .dlp-cmp; ◆ marca el mejor en cada métrica."""
    best_p50 = max(r["p50"] for r in rows)
    best_dd = min(r["dd"] for r in rows)
    best_sh = max(r["sharpe"] for r in rows)
    best_pr = max((r["prob"] or 0) for r in rows) if target else 0
    cols = ["Candidato", "Mediana", "Si va mal", "Si va bien", "Caída típica", "Eficiencia"]
    if target:
        cols.append("Prob. meta")
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = ""
    for r in sorted(rows, key=lambda x: -x["p50"]):
        is_best = r["name"] == best_name
        nmcol = S.ORANGE if is_best else S.TEXT_MD
        cells = [
            f"<td class='metric'><b style='color:{nmcol}'>{r['name']}</b></td>",
            f"<td class='{'win' if r['p50'] == best_p50 else ''}'>{components.fmt_money(r['p50'])}</td>",
            f"<td>{components.fmt_money(r['p5'])}</td>",
            f"<td>{components.fmt_money(r['p95'])}</td>",
            f"<td class='{'win' if r['dd'] == best_dd else ''}'>{components.fmt_pct(r['dd'])}</td>",
            f"<td class='{'win' if r['sharpe'] == best_sh else ''}'>{r['sharpe']:.2f}</td>",
        ]
        if target:
            cells.append(f"<td class='{'win' if (r['prob'] or 0) == best_pr else ''}'>{(r['prob'] or 0) * 100:.0f}%</td>")
        body += f"<tr>{''.join(cells)}</tr>"
    return f"<table class='dlp-cmp'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def render_candidate_results() -> None:
    """Muestra el ranking + veredicto + overlay de los candidatos importados."""
    all_results = st.session_state.get("cand_results") or []
    results = [r for r in all_results if r["result"] is not None]
    failed = [r["name"] for r in all_results if r["result"] is None]
    if not results:
        st.divider()
        st.error("No se pudo simular ningún candidato. Revisa que los tickers del CSV existan en el mercado.")
        return

    plan = st.session_state.get("cand_plan", {})
    target = plan.get("target")
    years = plan.get("horizon_years", results[0]["result"]["months"] // 12)

    st.divider()
    components.disclaimer_banner()
    if failed:
        st.warning("No se pudieron simular (tickers no encontrados): " + ", ".join(failed))

    rows = _cand_metric_rows(results, target)
    best = max(rows, key=lambda x: x["p50"])
    safest = min(rows, key=lambda x: x["dd"])

    with components.card("cand-verdict"):
        components.card_head("◆", "El mejor candidato", "según la proyección")
        v = (f"El candidato {_b(best['name'], S.ORANGE)} proyecta la mayor mediana a "
             f"{_b(str(years) + ' años')}: {_b(components.fmt_money(best['p50']), S.ORANGE)}. ")
        if safest["name"] == best["name"]:
            v += ("Y además es el más estable (menor caída típica): destaca tanto en crecimiento "
                  "como en estabilidad — aunque no es garantía.")
        else:
            v += (f"Pero {_b(safest['name'], S.BLUE)} es el más estable (caída típica "
                  f"{components.fmt_pct(safest['dd'])} vs {components.fmt_pct(best['dd'])}): hay un "
                  f"trade-off entre crecimiento y estabilidad según tu tolerancia al riesgo.")
        if target:
            bestprob = max(rows, key=lambda x: (x["prob"] or 0))
            v += (f" Para tu meta, el de mayor probabilidad de alcanzarla es "
                  f"{_b(bestprob['name'], S.GOLD)} ({(bestprob['prob'] or 0) * 100:.0f}%).")
        components.verdict_card(S.GOLD, _md_money(v))

    with components.card("cand-board"):
        components.card_head("◆", "Ranking de candidatos", "◆ = mejor en cada métrica")
        st.markdown(_candidates_table(rows, target, best["name"]), unsafe_allow_html=True)
        st.caption("Ordenados por mediana proyectada. 'Caída típica' y 'Eficiencia (Sharpe)' miden "
                   "el riesgo: menos caída y más Sharpe es mejor.")

    with components.card("cand-fan"):
        components.card_head("◆", "Proyección comparada", "mediana + rango P5–P95 de cada candidato")
        scen = [{"label": r["name"], "percentiles": r["result"]["percentiles"]} for r in rows]
        st.plotly_chart(charts.comparison_fan_chart(scen, results[0]["result"]["months"], target),
                        use_container_width=True, config={"displayModeBar": False}, key="cand_fan_chart")

    st.caption("◇ Consejo: usa los botones → A / → B del importador para analizar un candidato en "
               "profundidad (histograma, stress test, PDF, etc.).")


# ── App ──────────────────────────────────────────────────────────────────────
def _loader_msg(pct: int) -> str:
    if pct < 30:
        return "Bajando datos de mercado…"
    if pct < 60:
        return "Corriendo 10.000 simulaciones…"
    if pct < 85:
        return "Midiendo riesgos y percentiles…"
    return "Armando tu proyección…"


def main() -> None:
    st.set_page_config(page_title="Proyección de Portafolio", page_icon="◈",
                       layout="centered", initial_sidebar_state="collapsed")
    inject_css()
    S.disable_context_menu()  # bloquea el menú de clic derecho en toda la app
    _require_password()
    components.page_hero()

    spec = render_inputs()

    # Comparación de candidatos importados (flujo independiente del A/B)
    run_cands = st.session_state.pop("_run_cands", None)
    if run_cands is not None:
        _compute_candidates(run_cands)

    if spec is not None:
        st.session_state["cand_results"] = None   # una corrida A/B oculta la de candidatos
        base = spec["base"]
        inputs_A = dict(base, **spec["A"])
        inputs_B = dict(base, **spec["B"]) if spec["B"] else None

        target = random.uniform(9.0, 15.0)
        t0 = time.perf_counter()
        loader = st.empty()
        loader.markdown(components.progress_ring(0, "Preparando tu proyección…"), unsafe_allow_html=True)
        result_A = compute(inputs_A)
        result_B = compute(inputs_B) if inputs_B else None
        benchmarks = run_benchmarks(inputs_A) if base["compare"] else None
        extras_A = _build_extras(inputs_A, result_A)
        extras_B = _build_extras(inputs_B, result_B) if inputs_B else None
        remaining = max(target - (time.perf_counter() - t0), 3.0)
        steps = max(int(remaining / 0.09), 24)
        for i in range(steps + 1):
            loader.markdown(components.progress_ring(round(i / steps * 100), _loader_msg(round(i / steps * 100))),
                            unsafe_allow_html=True)
            time.sleep(remaining / steps)
        loader.empty()
        st.session_state.update(
            inputs_A=inputs_A, result_A=result_A, extras_A=extras_A,
            inputs_B=inputs_B, result_B=result_B, extras_B=extras_B, benchmarks=benchmarks,
            elapsed=time.perf_counter() - t0,
            pdf_bytes=None, _pdf_loading=False, _pdf_just=False)  # PDF se genera al click

    if st.session_state.get("result_A") is not None:
        st.divider()
        if st.session_state.get("result_B") is not None:
            render_compare(st.session_state.result_A, st.session_state.inputs_A, st.session_state.extras_A,
                           st.session_state.result_B, st.session_state.inputs_B, st.session_state.extras_B,
                           st.session_state.benchmarks, st.session_state.elapsed)
        else:
            render_single(st.session_state.result_A, st.session_state.inputs_A, st.session_state.extras_A,
                          st.session_state.benchmarks, "A", elapsed=st.session_state.elapsed)

    if st.session_state.get("cand_results"):
        render_candidate_results()


if __name__ == "__main__":
    main()
