"""Analista de Portafolios — entry point Streamlit (embed 1:1).

Compara hasta dos portafolios (A vs B) con simulaciones Montecarlo. Proyección
probabilística, no predicción. Sin barra lateral ni persistencia (no guarda nada).
"""
from __future__ import annotations

import hmac
import os
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
from streamlit_searchbox import st_searchbox  # noqa: E402  (buscador en vivo de tickers)

from core import insights, interpret, portfolio_import, presets, rating, sequence, stress  # noqa: E402
from core.montecarlo import run_montecarlo  # noqa: E402
from dashboard import charts, components  # noqa: E402
from dashboard import styles as S  # noqa: E402
from dashboard.styles import inject_css  # noqa: E402
from data import market_data  # noqa: E402
from data import tickers as tdir  # noqa: E402

DEFAULT_A = [{"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "weight": 100.0}]
DEFAULT_B = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "weight": 60.0},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "weight": 40.0},
]
MAX_ASSETS = 8
BENCHMARK_SPECS = [("S&P 500 puro", ["SPY"], [100.0]), ("60/40", ["SPY", "BND"], [60.0, 40.0])]

# Acceso Fase 2: el link con ?fase2=1 (o ?f2) muestra una portada con clave. El link
# normal (sin el parámetro) entra directo, sin cambios. La clave se puede configurar con
# el secret/env FASE2_PASSWORD; si no está, se usa el default de abajo (cambiable).
FASE2_QUERY_KEYS = ("fase2", "f2")
DEFAULT_FASE2_PASSWORD = "bienvenidofase2"
PCOLOR = {"A": S.ORANGE, "B": S.BLUE}
PLABEL = {"A": "Portafolio 1", "B": "Portafolio 2"}


# ── Password gate (Patrón 1) ─────────────────────────────────────────────────
def _require_password() -> None:
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected or st.session_state.get("_auth_ok"):
        return
    with st.form("auth", clear_on_submit=False):
        st.markdown("### Analista de Portafolios")
        pwd = st.text_input("pwd", type="password", label_visibility="collapsed", placeholder="Contraseña")
        ok = st.form_submit_button("Entrar", use_container_width=True, type="primary")
    if ok:
        if hmac.compare_digest((pwd or "").encode(), expected.encode()):
            st.session_state._auth_ok = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()


# ── Acceso Fase 2 (link diferenciado con clave) ──────────────────────────────
def _fase2_mode() -> bool:
    """True si la URL trae el parámetro de Fase 2 (ej: ?fase2=1 o ?f2).

    El link normal (sin el parámetro) NO se ve afectado: entra directo como hoy.
    """
    try:
        qp = st.query_params
    except Exception:
        return False
    return any(k in qp for k in FASE2_QUERY_KEYS)


def _fase2_password() -> str:
    """Clave de Fase 2: secret/env FASE2_PASSWORD si está definida; si no, el default."""
    val = None
    try:
        val = st.secrets.get("FASE2_PASSWORD")
    except Exception:
        val = None
    if not val:
        val = os.environ.get("FASE2_PASSWORD")
    return val or DEFAULT_FASE2_PASSWORD


def _require_fase2_access() -> None:
    """Portada 'Recurso exclusivo — Fase 2' con clave, SOLO en el link diferenciado.

    - Link normal (sin ?fase2): esta función no hace nada → acceso directo como siempre.
    - Link Fase 2 (?fase2=1): muestra una portada estética que pide la clave y no deja
      pasar hasta que sea correcta. Validación en tiempo constante (hmac.compare_digest)
      y desbloqueo por sesión (_fase2_ok).

    Rendimiento: la portada se dibuja dentro de un st.empty(); si la clave es correcta,
    lo vaciamos y hacemos `return` para que la app se renderice en EL MISMO run. Así se
    evita el st.rerun() extra (que hacía cargar dos veces) y el menú aparece de una.
    """
    if not _fase2_mode() or st.session_state.get("_fase2_ok"):
        return
    expected = _fase2_password()

    gate = st.empty()   # contenedor de la portada: lo vaciamos si la clave es correcta
    with gate.container():
        st.markdown(
            f"""
            <div class="dlp-page-hero" style="padding-top:26px;">
              <div class="glow"></div>
              <div class="diamond" style="font-size:30px;">🔒</div>
              <div class="title">Recurso exclusivo<br>Fase 2</div>
              <div class="sub">Acceso restringido · ingresa tu clave</div>
              <div class="dlp-rule"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _, mid, _ = st.columns([1, 2.2, 1])
        with mid:
            st.markdown(
                f"<div class='dlp-card dlp-card-left' style='border-left-color:{S.GOLD};text-align:center;'>"
                f"<div style='color:{S.TEXT_MD};font-size:15px;line-height:1.6;'>"
                f"Introduce la clave de acceso a la fase 2"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            with st.form("fase2_auth", clear_on_submit=False):
                pwd = st.text_input("clave", label_visibility="collapsed",
                                    placeholder="Clave de acceso Fase 2")
                ok = st.form_submit_button("🔓  Desbloquear Fase 2", use_container_width=True,
                                           type="primary")
            wrong = ok and not (expected and hmac.compare_digest((pwd or "").encode(), expected.encode()))
            if wrong:
                st.error("Clave incorrecta. Verifica e inténtalo de nuevo.")
            st.markdown(
                f"<div style='text-align:center;color:{S.TEXT_DIM};font-size:12px;margin-top:12px;"
                f"font-family:{S.MONO};letter-spacing:.05em;line-height:1.6;'>◇ Si aún no tienes la clave, "
                f"tu asesor DLP te la entregará cuando comience tu Fase 2.</div>",
                unsafe_allow_html=True,
            )

    if ok and not wrong:
        st.session_state["_fase2_ok"] = True
        gate.empty()   # borra la portada; el resto de main() renderiza la app en este run
        return
    st.stop()


# ── Simulación ───────────────────────────────────────────────────────────────
def compute(inputs: dict) -> dict:
    stats = market_data.get_market_stats(inputs["tickers"], inputs["historical_window_years"])
    result = run_montecarlo(
        initial_capital=inputs["initial_capital"], monthly_contribution=inputs["monthly_contribution"],
        horizon_years=inputs["horizon_years"], tickers=inputs["tickers"], weights=inputs["weights"],
        n_simulations=inputs["n_simulations"], distribution=inputs["distribution"],
        annual_fees_pct=inputs["annual_fees_pct"], annual_tax_on_gains_pct=inputs["annual_tax_on_gains_pct"],
        historical_window_years=inputs["historical_window_years"], target=inputs["target"],
        random_seed=inputs["random_seed"], market_stats=stats)
    # Análisis de alto valor (métricas + hallazgos en lenguaje natural). Todo escalar/pequeño:
    # sale de μ/Σ/pesos y de final_values (no usa la matriz paths → sin presión de memoria).
    try:
        result["analysis"] = insights.analyze(stats, inputs["tickers"], inputs["weights"], result, inputs)
    except Exception:
        result["analysis"] = None
    return result


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
def _ticker_search(query: str):
    """Función de búsqueda en vivo para el st_searchbox: devuelve (etiqueta, símbolo)."""
    results = tdir.search_tickers((query or "").strip(), limit=8)
    return [(f"{r['symbol']}   ·   {r['name'][:28]}   ·   {r['exchange']} · "
             f"{tdir.classify_type(r['symbol'], r['name'], r.get('is_etf', False))}", r["symbol"])
            for r in results]


def render_portfolio_builder(pid: str, capital: float) -> tuple[list[str], list[float], float]:
    pf = st.session_state.portfolios[pid]
    lead = PCOLOR[pid]
    palette = _palette_for(lead)
    total_w = sum(max(it["weight"], 0) for it in pf)

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        # Buscador EN VIVO (por tecla): escribe símbolo o nombre y aparecen los resultados;
        # al elegir uno se añade. clear_on_submit limpia el campo para la siguiente búsqueda.
        selected = st_searchbox(_ticker_search, placeholder="Buscar ticker…",
                                key=f"q_{pid}", clear_on_submit=True, debounce=180)
        if not selected:
            st.session_state.pop(f"_added_{pid}", None)
        elif selected != st.session_state.get(f"_added_{pid}"):
            st.session_state[f"_added_{pid}"] = selected     # guarda contra re-añadir en reruns
            _add_ticker(pid, selected, tdir.get_name(selected))
            st.rerun()
    with right:
        with st.container(key=f"donutcard_{pid}"):
            if pf and total_w > 0:
                st.plotly_chart(charts.allocation_donut(pf, lead_color=lead), use_container_width=True,
                                config={"displayModeBar": False}, key=f"donut_{pid}")
            else:
                st.markdown("<div style='padding:44px 8px;text-align:center;color:#7A8898;"
                            "font-family:JetBrains Mono,monospace;font-size:12.5px;'>"
                            "Elige activos para ver<br>la composición</div>", unsafe_allow_html=True)

    # "En tu portafolio" — ancho completo de la tarjeta, en una sub-card metálica.
    with st.container(key=f"holdings_{pid}"):
        st.markdown("<div class='dlp-side-title' style='margin-top:2px'>En tu portafolio</div>",
                    unsafe_allow_html=True)
        if not pf:
            st.caption("Aún no has agregado activos — búscalos arriba.")
        for i, it in enumerate(pf):
            dot = palette[i % len(palette)]
            wc1, wc2, wc3 = st.columns([3, 2, 1])
            usd = (it["weight"] / total_w * capital) if total_w > 0 else 0
            wc1.markdown(
                f"<div style='padding-top:8px'><span style='color:{dot};font-size:16px'>●</span> "
                f"<b style='color:{S.TEXT_HI};font-size:15px'>{it['symbol']}</b> "
                f"<span style='color:{S.TEXT_LO};font-size:12px'>· ${usd:,.0f}</span><br>"
                f"<span style='color:{S.TEXT_LO};font-size:11px;padding-left:20px'>{it['name'][:28]}</span></div>",
                unsafe_allow_html=True)
            it["weight"] = wc2.number_input(
                "peso", value=float(it["weight"]), min_value=0.0, max_value=100.0, step=5.0,
                key=f"pw_{pid}_{it['symbol']}", label_visibility="collapsed", format="%.0f")
            if wc3.button("✕", key=f"rm_{pid}_{it['symbol']}", use_container_width=True):
                st.session_state.portfolios[pid] = [x for x in pf if x["symbol"] != it["symbol"]]
                st.rerun()

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
    with st.expander("☁  Subir portafolio con archivo"):
        st.markdown(
            f"<div style='display:flex;align-items:baseline;gap:8px;'>"
            f"<span style='color:{S.TEXT_MD};font-size:13px;flex:1;'>Sube un archivo (CSV o Excel) "
            f"con tus portafolios — columnas: Portafolio, Ticker, Nombre, Clase, Peso%.</span>"
            f"<span style='color:{S.TEXT_DIM};font-family:{S.MONO};font-size:10.5px;"
            f"white-space:nowrap;'>◇ máximo 3 portafolios por archivo</span></div>",
            unsafe_allow_html=True)
        up = st.file_uploader(
            "Subir portafolios a analizar", type=None, key="cand_csv", label_visibility="collapsed",
            help="Formatos: CSV o Excel (.xlsx). El diálogo abre en 'todos los archivos'.")
        if up is not None:
            try:
                st.session_state["cand_ports"] = portfolio_import.parse_portfolios(up.name, up.getvalue())
            except Exception as e:
                st.session_state.pop("cand_ports", None)
                st.error(f"No se pudo leer el archivo: {e}")

        cands = st.session_state.get("cand_ports") or []
        if not cands:
            return
        n = len(cands)
        st.markdown(f"<div class='dlp-side-title'>{n} portafolio{'s' if n != 1 else ''} "
                    f"importado{'s' if n != 1 else ''}</div>", unsafe_allow_html=True)
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
        # Botón adaptativo: funciona con 1, 2 o 3 portafolios.
        btn_label = "◈  Analizar el portafolio" if n == 1 else f"◈  Analizar los {n} portafolios"
        if st.button(btn_label, key="cand_compare_btn", use_container_width=True, type="primary"):
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
            components.card_head("◆", "Tu portafolio", "Busca y agrega activos")
            symA, wA, twA = render_portfolio_builder("A", capital)
        else:
            components.card_head("◆", "Compara dos portafolios", "Edita ambos; se analizan los dos")
            tA, tB = st.tabs([f"  {PLABEL['A']}  ", f"  {PLABEL['B']}  "])
            with tA:
                symA, wA, twA = render_portfolio_builder("A", capital)
            with tB:
                if st.button("✕  Quitar este portafolio", key="rmb"):
                    del st.session_state.portfolios["B"]
                    st.rerun()
                symB, wB, twB = render_portfolio_builder("B", capital)

    if not has_b:
        with st.container(key="addb"):
            if st.button("＋  Añadir nuevo portafolio", use_container_width=True):
                st.session_state.portfolios["B"] = [dict(x) for x in DEFAULT_B]
                st.rerun()

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

    # Botón principal "Analizar" arriba; "Opciones avanzadas" como expander DEBAJO.
    # (Los widgets del expander se ejecutan antes del gate `if not clicked`, así que sus
    #  valores locales quedan listos al construir el spec — sin session_state extra.)
    label = "◈  Analizar los dos portafolios" if has_b else "◈  Analizar"
    clicked = st.button(label, type="primary", use_container_width=True)

    # "Subir portafolio con archivo" — entre Analizar y Opciones avanzadas.
    render_candidate_importer(capital, aporte, int(horizonte), meta)

    with st.expander("Opciones avanzadas"):
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

    if not clicked:
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


# ── Panel de análisis de alto valor (hallazgos + métricas) ───────────────────
def render_analysis_panel(result, inputs, kp) -> None:
    """Hallazgos en lenguaje natural + métricas de alto valor. Siempre visible.

    Reusable en portafolio único, en el detalle A/B y por candidato importado.
    """
    analysis = result.get("analysis")
    if not analysis:
        st.info("El análisis detallado no está disponible para esta corrida.")
        return
    s, o, findings = analysis["structure"], analysis["outcomes"], analysis["findings"]
    retirement = inputs["monthly_contribution"] < 0

    # 1) DIVERSIFICACIÓN Y CONCENTRACIÓN — lo primero de todo.
    with components.card(f"an-div-{kp}"):
        components.card_head("◆", "Diversificación y concentración", "¿está bien repartido?")
        g, k = st.columns([1, 1.15], gap="large")
        with g:
            st.plotly_chart(charts.diversification_meter(s["wavg_corr"]), use_container_width=True,
                            config={"displayModeBar": False}, key=f"an_div_{kp}")
        with k:
            components.kpi_tile("Apuestas independientes", f"{s['eff_bets']:.1f}", S.BLUE,
                                f"de {s['n_assets']} activos",
                                help="Cuántas apuestas realmente distintas tienes. Si tus activos se "
                                     "mueven juntos, muchos nombres equivalen a pocas apuestas reales.",
                                rating=rating.rate("eff_bets", s["eff_bets"]))
            components.kpi_tile("Mayor posición", components.fmt_pct(s["max_weight"]), S.ORANGE,
                                s["max_weight_symbol"],
                                help="Qué porcentaje del portafolio está en tu activo más grande. "
                                     "Mucho en uno solo = más vulnerable a que a ese le vaya mal.",
                                rating=rating.rate("concentration", s["max_weight"]))

    # 2) DE DÓNDE VIENE TU RIESGO — arriba de los hallazgos para que se note.
    if len(s["assets"]) >= 2:
        with components.card(f"an-risk-{kp}"):
            components.card_head("◆", "De dónde viene tu riesgo", "peso vs contribución al riesgo")
            st.plotly_chart(charts.risk_vs_weight_bar(s["assets"]), use_container_width=True,
                            config={"displayModeBar": False}, key=f"an_rvw_{kp}")
            st.caption("Barra naranja (riesgo) más larga que la azul (peso) = ese activo pesa en tus "
                       "altibajos más de lo que su tamaño sugiere.")

    # 3) LOS CINCO HALLAZGOS CLAVE — solo los 5 más importantes.
    with components.card(f"an-find-{kp}"):
        components.card_head("◆", "Los cinco hallazgos clave", "lo que más importa, en claro")
        for fd in findings[:5]:
            components.finding_card(fd)

    # 4) RETORNO, RIESGO Y LO QUE PUEDES PERDER — tiles con termómetro.
    with components.card(f"an-metrics-{kp}"):
        components.card_head("◆", "Retorno, riesgo y lo que puedes perder")
        m = st.columns(3)
        with m[0]:
            components.kpi_tile("Retorno esperado", components.fmt_pct(s["ann_return"]), S.GREEN,
                                "al año (promedio)",
                                help="Rendimiento anual promedio esperado según el histórico. Es un "
                                     "promedio: años individuales pueden ser mucho mejores o peores.",
                                rating=rating.rate("return", s["ann_return"]))
        with m[1]:
            components.kpi_tile("Volatilidad", "±" + components.fmt_pct(s["ann_vol"]), S.ORANGE,
                                "vaivén al año",
                                help="Cuánto sube y baja normalmente en un año. Más volatilidad = más "
                                     "nervios, pero suele venir con más retorno potencial.",
                                rating=rating.rate("volatility", s["ann_vol"]))
        with m[2]:
            components.kpi_tile("Eficiencia", f"{result['expected_sharpe']:.2f}", S.GOLD,
                                "Sharpe (>1 bueno)",
                                help="Sharpe: cuánto retorno obtienes por cada unidad de riesgo. "
                                     "Más alto es mejor; por encima de 1 se considera bueno.",
                                rating=rating.rate("sharpe", result["expected_sharpe"]))
        if not retirement:
            m2 = st.columns(3)
            with m2[0]:
                pl = o["prob_loss"] or 0.0
                components.kpi_tile("Prob. de pérdida", components.fmt_pct(pl), S.RED,
                                    "menos de lo aportado",
                                    help="En qué porcentaje de escenarios terminas con menos dinero "
                                         "del que aportaste en total. Es el riesgo de acabar en rojo.",
                                    rating=rating.rate("prob_loss", pl))
            with m2[1]:
                inv = o["invested"] or 1.0
                ratio = (o["median_real"] / inv) if inv > 0 else 1.0
                components.kpi_tile("En dinero de hoy", components.fmt_money(o["median_real"]), S.BLUE,
                                    "mediana real (infl. 3%)",
                                    help="Tu mediana ajustada por inflación (3%/año): lo que realmente "
                                         "podrás comprar. El número grande a futuro engaña.",
                                    rating=rating.rating(max(0.0, min(1.0, (ratio - 1.0) / 2.0))))
            with m2[2]:
                pb = o["prob_beat_savings"] or 0.0
                components.kpi_tile("Supera ahorro 4%", components.fmt_pct(pb), S.GREEN,
                                    "de los escenarios",
                                    help="Con qué frecuencia este portafolio le gana a un ahorro "
                                         "seguro al 4% anual. Es el premio por aceptar el vaivén.",
                                    rating=rating.rate("prob_beat", pb))


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

    tab_names = ["Resumen", "Análisis", "¿Alcanzo mi meta?", "Riesgos"]
    if benchmarks:
        tab_names.append("Comparar")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        # 1) Proyección primero de todo — con línea gris "Aportado" vs "Invertido".
        with components.card(f"res-fan-{kp}"):
            components.card_head("◆", f"Proyección a {years} años",
                                 "pasa el cursor: aportado vs invertido")
            st.plotly_chart(
                charts.fan_chart(result["percentiles"], result["months"], inputs["target"],
                                 initial_capital=inputs["initial_capital"],
                                 monthly_contribution=inputs["monthly_contribution"]),
                use_container_width=True, config={"displayModeBar": False}, key=f"fan_{kp}")
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
                components.kpi_tile("Si va mal", components.fmt_money(p5), S.RED, "1 de 20 (P5)",
                                    help="Percentil 5: solo 1 de cada 20 escenarios terminó peor que esto. "
                                         "Es tu 'si va mal' razonable, no el peor caso absoluto.",
                                    rating=rating.rating(0.13, "Pesimista"))
                components.kpi_tile("Lo más probable", components.fmt_money(p50), S.ORANGE, "el del medio",
                                    help="La mediana: la mitad de los escenarios terminó por encima y la "
                                         "mitad por debajo. El resultado más representativo.",
                                    rating=rating.rating(0.5, "Central"))
                components.kpi_tile("Si va bien", components.fmt_money(p95), S.GREEN, "1 de 20 (P95)",
                                    help="Percentil 95: solo 1 de cada 20 escenarios terminó mejor que esto. "
                                         "Tu 'si va bien' razonable, no el mejor caso absoluto.",
                                    rating=rating.rating(0.87, "Optimista"))
        with components.card(f"res-interp-{kp}"):
            components.card_head("◆", "¿Qué significa esto?")
            st.markdown(_md_money(interpret.interpret_locally(result, inputs, extras.get("stress"))))

    with tabs[1]:
        render_analysis_panel(result, inputs, kp)

    with tabs[2]:
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
        # Interpretación en lenguaje natural (haya o no meta) — indistinguible de IA.
        with components.card(f"meta-interp-{kp}"):
            components.card_head("◆", "¿Qué dice esta gráfica?")
            st.markdown(_md_money(interpret.interpret_goal(result, inputs)))

    with tabs[3]:
        with components.card(f"risk-metrics-{kp}"):
            components.card_head("◆", "Riesgos en detalle", "para quien quiere profundizar")
            m = st.columns(4)
            with m[0]:
                components.kpi_tile("Caída típica", components.fmt_pct(result["max_drawdown_typical"]),
                                    S.BLUE, "en un mal momento",
                                    help="Cuánto suele caer tu inversión desde su punto más alto hasta el "
                                         "más bajo. Hay que aguantarla sin vender en pánico.",
                                    rating=rating.rate("drawdown", result["max_drawdown_typical"]))
            with m[1]:
                components.kpi_tile("Eficiencia", f"{result['expected_sharpe']:.2f}", S.GOLD, "Sharpe",
                                    help="Sharpe: retorno obtenido por cada unidad de riesgo. Más alto "
                                         "es mejor; por encima de 1 se considera bueno.",
                                    rating=rating.rate("sharpe", result["expected_sharpe"]))
            with m[2]:
                components.kpi_tile("Riesgo de ruina", components.fmt_pct(result["probability_of_ruin"]),
                                    S.TEXT_LO, "llega a $0",
                                    help="En qué porcentaje de escenarios el capital llega a cero. Con "
                                         "aportes suele ser ~0%; cobra sentido en modo retiro.",
                                    rating=rating.rate("ruin", result["probability_of_ruin"]))
            with m[3]:
                if retirement:
                    components.kpi_tile("Retiro por año", components.fmt_money(abs(inputs["monthly_contribution"]) * 12),
                                        S.TEXT_MD, "lo que sacas",
                                        help="Cuánto retiras en total cada año (retiro mensual × 12).",
                                        rating=rating.rating(0.5, "Referencia"))
                else:
                    components.kpi_tile("Lo que aportas", components.fmt_money(
                        inputs["initial_capital"] + inputs["monthly_contribution"] * 12 * years),
                        S.TEXT_MD, "sin rendimiento",
                        help="Tu capital inicial más todos tus aportes a lo largo del horizonte, "
                             "sin contar el rendimiento del mercado. Es lo que sale de tu bolsillo.",
                        rating=rating.rating(0.5, "Referencia"))
        with components.card(f"risk-interp-{kp}"):
            components.card_head("◆", "Lectura de tus riesgos")
            st.markdown(_md_money(interpret.interpret_risks(result, inputs, result.get("analysis"))))
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
        with tabs[4]:
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
    # Métricas estructurales de alto valor (de core.insights): concentración y diversificación
    sA = (rA.get("analysis") or {}).get("structure")
    sB = (rB.get("analysis") or {}).get("structure")
    if sA and sB:
        rows += [("Concentración: mayor posición (menos es mejor)",
                  sA["max_weight"] * 100, sB["max_weight"] * 100, "low", "pct"),
                 ("Diversificación: correlación media (menos es mejor)",
                  sA["wavg_corr"] * 100, sB["wavg_corr"] * 100, "low", "pct")]

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
    cands = spec["candidates"][:3]   # máximo 3 portafolios
    n = len(cands)
    results: list[dict] = []
    loader = st.empty()               # mismo overlay a pantalla completa que la corrida A/B
    for j, cand in enumerate(cands):
        loader.markdown(components.progress_overlay(
            round(j / max(n, 1) * 100),
            f"Analizando portafolio {j + 1} de {n}…"), unsafe_allow_html=True)
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
        # Guardamos la composición (activos + pesos + nombres) para mostrarla luego.
        # Es una lista chica de strings/números: no impacta la memoria.
        results.append({"name": cand["name"], "inputs": inputs, "result": res,
                        "items": [dict(it) for it in cand["items"]]})
    loader.markdown(components.progress_overlay(100, "Armando el análisis…"), unsafe_allow_html=True)
    loader.empty()
    st.session_state["cand_results"] = results
    st.session_state["cand_plan"] = {"horizon_years": spec["horizon_years"], "target": spec["target"]}


def _cand_metric_rows(results: list[dict], target: float | None) -> list[dict]:
    rows = []
    for r in results:
        res = r["result"]
        fv = res["final_values"]
        # Composición: usa los items guardados; si faltaran, se reconstruye desde inputs.
        items = r.get("items")
        if not items:
            inp = r.get("inputs", {})
            items = [{"symbol": t, "name": tdir.get_name(t), "weight": w * 100.0}
                     for t, w in zip(inp.get("tickers", []), inp.get("weights", []))]
        rows.append({
            "name": r["name"], "result": res, "items": items,
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


def _candidate_composition_html(items: list[dict]) -> str:
    """Lista de activos de un candidato: punto de color (igual que la dona) + símbolo +
    nombre + peso %. Los pesos se normalizan a 100% para que sumen exacto."""
    total = sum(max(float(it.get("weight", 0)), 0.0) for it in items) or 1.0
    html = ""
    for i, it in enumerate(items):
        color = charts.DONUT_COLORS[i % len(charts.DONUT_COLORS)]
        pct = max(float(it.get("weight", 0)), 0.0) / total * 100.0
        name = (it.get("name") or "")[:26]
        html += (
            f"<div style='display:flex;align-items:center;gap:9px;padding:5px 0;"
            f"border-bottom:1px solid {S.BORDER};'>"
            f"<span style='color:{color};font-size:13px;'>●</span>"
            f"<b style='color:{S.TEXT_HI};font-family:{S.MONO};font-size:13px;min-width:56px;'>{it['symbol']}</b>"
            f"<span style='color:{S.TEXT_LO};font-size:12px;flex:1;'>{name}</span>"
            f"<b style='color:{S.TEXT_MD};font-family:{S.MONO};font-size:13.5px;'>{pct:.0f}%</b></div>")
    return html


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
    if failed:
        st.warning("No se pudieron simular (tickers no encontrados): " + ", ".join(failed))

    # Un solo portafolio → vista de análisis completa (sin ranking/comparación).
    if len(results) == 1:
        r0 = results[0]
        components.hero_card(
            glyph="◈", caption=f"Análisis · {r0['name']}",
            meta_items=[("Capital inicial", components.fmt_money(r0["inputs"]["initial_capital"])),
                        ("Aporte mensual", components.fmt_money(abs(r0["inputs"]["monthly_contribution"]))),
                        ("Horizonte", f"{years} años")],
            highlight_label=f"Mediana a {years} años",
            highlight_value=components.fmt_money(float(np.percentile(r0["result"]["final_values"], 50))),
            highlight_color=S.ORANGE)
        render_single(r0["result"], r0["inputs"], {}, None, "cand1",
                      with_hero=False, with_actions=True)
        return

    components.disclaimer_banner()
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

    with components.card("cand-compo"):
        components.card_head("◆", "Composición de cada candidato", "qué activos tiene y con qué peso")
        for idx, r in enumerate(sorted(rows, key=lambda x: -x["p50"])):
            items = r["items"]
            is_best = r["name"] == best["name"]
            nmcol = S.ORANGE if is_best else S.TEXT_HI
            tag = " · el de mayor mediana" if is_best else ""
            st.markdown(
                f"<div style='margin:6px 0 4px;'><b style='color:{nmcol};font-family:{S.MONO};"
                f"font-size:15px;letter-spacing:.04em;'>{r['name']}</b>"
                f"<span style='color:{S.TEXT_LO};font-size:12px;'> · {len(items)} activos{tag}</span></div>",
                unsafe_allow_html=True)
            dc, lc = st.columns([1, 1.3], gap="large")
            with dc:
                st.plotly_chart(charts.allocation_donut(items), use_container_width=True,
                                config={"displayModeBar": False}, key=f"cand_compo_donut_{idx}")
            with lc:
                st.markdown(_candidate_composition_html(items), unsafe_allow_html=True)
            if idx < len(rows) - 1:
                st.divider()

    # Hallazgos + "de dónde viene el riesgo" por candidato (mismo motor que el modo único)
    with components.card("cand-analysis"):
        components.card_head("◆", "Análisis por candidato", "hallazgos clave + de dónde viene el riesgo")
        for idx, r in enumerate(sorted(rows, key=lambda x: -x["p50"])):
            analysis = r["result"].get("analysis")
            is_best = r["name"] == best["name"]
            nmcol = S.ORANGE if is_best else S.TEXT_HI
            st.markdown(
                f"<div style='margin:8px 0 6px;'><b style='color:{nmcol};font-family:{S.MONO};"
                f"font-size:15px;letter-spacing:.04em;'>{r['name']}</b></div>",
                unsafe_allow_html=True)
            if not analysis:
                st.caption("Análisis no disponible para este candidato.")
            else:
                for fd in analysis["findings"][:4]:
                    components.finding_card(fd)
                if len(analysis["structure"]["assets"]) >= 2:
                    st.plotly_chart(charts.risk_vs_weight_bar(analysis["structure"]["assets"]),
                                    use_container_width=True, config={"displayModeBar": False},
                                    key=f"cand_rvw_{idx}")
            if idx < len(rows) - 1:
                st.divider()

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
    st.set_page_config(page_title="Analista de Portafolios", page_icon="◈",
                       layout="centered", initial_sidebar_state="collapsed")
    inject_css()
    S.disable_context_menu()  # bloquea el menú de clic derecho en toda la app
    _require_fase2_access()   # portada con clave SOLO en el link ?fase2 (el normal no cambia)
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
        loader.markdown(components.progress_overlay(0, "Preparando tu análisis…"), unsafe_allow_html=True)
        result_A = compute(inputs_A)
        result_B = compute(inputs_B) if inputs_B else None
        benchmarks = run_benchmarks(inputs_A) if base["compare"] else None
        extras_A = _build_extras(inputs_A, result_A)
        extras_B = _build_extras(inputs_B, result_B) if inputs_B else None
        remaining = max(target - (time.perf_counter() - t0), 3.0)
        steps = max(int(remaining / 0.09), 24)
        for i in range(steps + 1):
            loader.markdown(components.progress_overlay(round(i / steps * 100), _loader_msg(round(i / steps * 100))),
                            unsafe_allow_html=True)
            time.sleep(remaining / steps)
        loader.empty()
        st.session_state.update(
            inputs_A=inputs_A, result_A=result_A, extras_A=extras_A,
            inputs_B=inputs_B, result_B=result_B, extras_B=extras_B, benchmarks=benchmarks,
            elapsed=time.perf_counter() - t0,
            pdf_bytes=None, _pdf_loading=False, _pdf_just=False)  # PDF se genera al click

    if st.session_state.get("result_A") is not None:
        with st.container(key="results-capsule"):   # cápsula metálica que encierra los resultados
            if st.session_state.get("result_B") is not None:
                render_compare(st.session_state.result_A, st.session_state.inputs_A, st.session_state.extras_A,
                               st.session_state.result_B, st.session_state.inputs_B, st.session_state.extras_B,
                               st.session_state.benchmarks, st.session_state.elapsed)
            else:
                render_single(st.session_state.result_A, st.session_state.inputs_A, st.session_state.extras_A,
                              st.session_state.benchmarks, "A", elapsed=st.session_state.elapsed)

    if st.session_state.get("cand_results"):
        with st.container(key="results-capsule2"):
            render_candidate_results()


if __name__ == "__main__":
    main()
