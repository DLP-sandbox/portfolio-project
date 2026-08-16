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

DEFAULT_A = [{"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "weight": 10_000.0}]
DEFAULT_B = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "weight": 6_000.0},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "weight": 4_000.0},
]
MAX_ASSETS = 20
BENCHMARK_SPECS = [("S&P 500", ["SPY"], [100.0])]   # benchmark único, SIEMPRE activo


@st.cache_resource(show_spinner=False)
def _prewarm_once():
    """Calienta kaleido UNA vez por proceso, en segundo plano y sin bloquear el arranque.

    El servicio ya no se duerme, así que el proceso vive: pagando aquí el arranque del
    renderizador (~6s) el primer análisis deja de costarlo. `cache_resource` garantiza
    que se lance una sola vez aunque haya muchas sesiones.
    """
    import threading

    def _run():
        try:
            from dashboard import pdf_report

            pdf_report.prewarm()
        except Exception:
            pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t

# Acceso Fase 2: el link con ?fase2=1 (o ?f2) muestra una portada con clave. El link
# normal (sin el parámetro) entra directo, sin cambios. La clave se puede configurar con
# el secret/env FASE2_PASSWORD; si no está, se usa el default de abajo (cambiable).
FASE2_QUERY_KEYS = ("fase2", "f2")
DEFAULT_FASE2_PASSWORD = "bienvenidofase2"
PCOLOR = {"A": S.SERIES_A, "B": S.SERIES_B, "C": S.SERIES_C}  # identidades de DATOS validadas (all-pairs)
PLABEL = {"A": "Portafolio 1", "B": "Portafolio 2", "C": "Portafolio 3"}
PIDS = ("A", "B", "C")          # orden fijo de slots
MAX_PORTFOLIOS = 3


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
    # extras["sequence"] eliminado: se calculaba y NUNCA se renderizaba (ni en la app ni
    # en el PDF). El flag "show_sequence" sigue existiendo en base para no mover firmas.
    return extras


# ── Estado de portafolios: ÚNICA fuente de verdad (slots A/B/C, máximo 3) ────
# Todo método de entrada (manual o archivo) llena estos slots; el botón "Analizar"
# corre el MISMO pipeline sobre ellos. Así el análisis nunca depende del método.
def _init_portfolios() -> None:
    st.session_state.setdefault("portfolios", {"A": [dict(x) for x in DEFAULT_A]})
    st.session_state.setdefault("portfolio_names", {})


def _active_pids() -> list[str]:
    """Slots con portafolio, en orden fijo A→B→C."""
    pfs = st.session_state.get("portfolios", {})
    return [p for p in PIDS if p in pfs]


def _pname(pid: str) -> str:
    """Nombre visible del portafolio: el del archivo si lo hay, si no 'Portafolio N'."""
    return (st.session_state.get("portfolio_names", {}) or {}).get(pid) or PLABEL.get(pid, pid)


def _free_pid() -> str | None:
    """Primer slot libre (o None si ya hay 3)."""
    pfs = st.session_state.get("portfolios", {})
    return next((p for p in PIDS if p not in pfs), None)


def _clear_amount_widgets(pid: str, symbol: str | None = None) -> None:
    """Borra el estado de las casillas de dinero de un portafolio (o de un activo).

    `money_input` solo inicializa su valor si la clave NO existe, y el armador
    sincroniza los montos DESDE esas claves. Si quedan huérfanas, mandan ellas: al
    importar un archivo, un activo que ya estuviera en pantalla conservaba su monto
    viejo (el SPY de $10.000 por defecto se comía el 51% de una cartera importada al
    5%), y al quitar y volver a añadir un activo reaparecía el importe anterior.
    """
    pref = f"pw_{pid}_{symbol}__" if symbol else f"pw_{pid}_"
    for k in [k for k in list(st.session_state.keys())
              if k.startswith(pref) and (k.endswith("__raw") or k.endswith("__txt"))]:
        st.session_state.pop(k, None)


def set_portfolio(pid: str, symbols: list[str], weights: list[float]) -> None:
    # Reemplazo completo del portafolio: los montos que manda el llamador son la
    # verdad, así que se limpia el estado de las casillas para que se reinicialicen.
    _clear_amount_widgets(pid)
    st.session_state.portfolios[pid] = [
        {"symbol": s, "name": tdir.get_name(s), "weight": float(w)} for s, w in zip(symbols, weights)]


def _add_ticker(pid: str, symbol: str, name: str) -> None:
    pf = st.session_state.portfolios[pid]
    if any(it["symbol"] == symbol for it in pf):
        return
    if len(pf) >= MAX_ASSETS:
        st.toast(f"Máximo {MAX_ASSETS} activos.")
        return
    pf.append({"symbol": symbol, "name": name, "weight": 1_000.0})  # monto inicial en $


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


def money_input(default: float, key: str, label: str = "capital") -> float:
    """Casilla de DINERO: muestra siempre '$4,500' (miles, sin decimales) y no tiene tope.

    Reusa el mismo patrón de `num_input` (raw + texto formateado) para que el valor se lea
    como dinero mientras se escribe. La fuente de verdad es `st.session_state[key+'__raw']`.
    """
    rawk, txtk = f"{key}__raw", f"{key}__txt"
    if rawk not in st.session_state:
        st.session_state[rawk] = float(default)
        st.session_state[txtk] = f"${float(default):,.0f}"
    st.text_input(label, key=txtk, label_visibility="collapsed",
                  on_change=_parse_money, args=(txtk, rawk))
    return float(st.session_state[rawk])


def _parse_money(txtk: str, rawk: str) -> None:
    """Normaliza lo escrito a un monto y lo reformatea como '$1,234' (sin límite superior)."""
    cleaned = re.sub(r"[^0-9]", "", st.session_state.get(txtk, "") or "")
    val = float(int(cleaned)) if cleaned else 0.0
    st.session_state[rawk] = val
    st.session_state[txtk] = f"${val:,.0f}"


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
    results = tdir.search_tickers_all((query or "").strip(), limit=8)
    return [(f"{r['symbol']}   ·   {r['name'][:28]}   ·   {r['exchange']} · "
             f"{tdir.classify_type(r['symbol'], r['name'], r.get('is_etf', False))}", r["symbol"])
            for r in results]


def render_portfolio_builder(pid: str) -> tuple[list[str], list[float], float]:
    pf = st.session_state.portfolios[pid]
    lead = PCOLOR[pid]
    palette = _palette_for(lead)
    # FIX: el widget es la fuente de verdad. Sincronizamos cada monto desde session_state
    # ANTES de calcular el total y los porcentajes; si no, ambos van un rerun por detrás
    # de lo que el usuario acaba de escribir (bug: $3.000 mostraba 5%).
    for it in pf:
        rawk = f"pw_{pid}_{it['symbol']}__raw"
        if rawk in st.session_state:
            it["weight"] = float(st.session_state[rawk])
    total_w = sum(max(it["weight"], 0) for it in pf)

    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        # Buscador EN VIVO (por tecla): escribe símbolo o nombre y aparecen los resultados;
        # al elegir uno se añade. clear_on_submit limpia el campo para la siguiente búsqueda.
        selected = st_searchbox(
            _ticker_search, placeholder="Buscar ticker…  (símbolo o nombre)",
            key=f"q_{pid}", clear_on_submit=True, debounce=180,
            style_overrides={
                "clear": {"fill": "#8D949E"},
                "dropdown": {"fill": "#E2B25C"},
                "searchbox": {
                    "control": {"backgroundColor": "#1A1F27",
                                "border": "1px solid rgba(255,255,255,0.16)",
                                "borderRadius": "12px", "boxShadow": "none"},
                    "input": {"color": "#F2F3F5"},
                    "placeholder": {"color": "#9AA1AB"},
                    "singleValue": {"color": "#F2F3F5"},
                    "menuList": {"backgroundColor": "#12151B",
                                 "border": "1px solid rgba(226,178,92,0.30)"},
                    "option": {"backgroundColor": "#12151B", "color": "#C9CDD3",
                               "highlightColor": "rgba(226,178,92,0.14)"},
                },
            })
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

    # "En tu portafolio" — DENTRO de la columna izquierda, bajo el buscador: el bento
    # aprovecha el alto de la dona en vez de dejar la izquierda vacía.
    with left, st.container(key=f"holdings_{pid}"):
        hc1, hc2, hc3 = st.columns([3, 2, 1])
        hc1.markdown("<div class='dlp-side-title' style='margin:0'>En tu portafolio</div>",
                     unsafe_allow_html=True)
        hc2.markdown(f"<div style='color:{S.TEXT_LO};font-family:{S.MONO};font-size:11px;"
                     f"text-transform:uppercase;letter-spacing:.08em;'>Capital invertido $</div>",
                     unsafe_allow_html=True)
        if not pf:
            st.caption("Aún no has agregado activos — búscalos arriba.")
        for i, it in enumerate(pf):
            dot = palette[i % len(palette)]
            wc1, wc2, wc3 = st.columns([3, 2, 1])
            share = (it["weight"] / total_w * 100.0) if total_w > 0 else 0.0
            wc1.markdown(
                f"<div style='padding-top:8px'><span style='color:{dot};font-size:16px'>●</span> "
                f"<b style='color:{S.TEXT_HI};font-size:15px'>{it['symbol']}</b> "
                f"<span style='color:{S.TEXT_LO};font-size:12px'>· {share:.0f}%</span><br>"
                f"<span style='color:{S.TEXT_LO};font-size:11px;padding-left:20px'>{it['name'][:28]}</span></div>",
                unsafe_allow_html=True)
            # Capital invertido en ESTE activo: se ve como dinero ($4,500) y no tiene tope.
            with wc2:
                it["weight"] = money_input(float(it["weight"]), f"pw_{pid}_{it['symbol']}")
            if wc3.button("✕", key=f"rm_{pid}_{it['symbol']}", use_container_width=True):
                st.session_state.portfolios[pid] = [x for x in pf if x["symbol"] != it["symbol"]]
                _clear_amount_widgets(pid, it["symbol"])  # si vuelve, entra limpio
                st.rerun()

        if total_w > 0:
            st.caption(f"◇ Capital total invertido en este portafolio: **${total_w:,.0f}**")

    symbols = [it["symbol"] for it in pf]
    weights = [it["weight"] for it in pf]
    return symbols, weights, sum(max(w, 0) for w in weights)


# ── Subir portafolios desde archivo (CSV/Excel) ──────────────────────────────
def _load_portfolio_into(pid: str, cand: dict) -> None:
    """Carga un portafolio parseado en un slot, conservando su nombre del archivo."""
    symbols = [it["symbol"] for it in cand["items"]]
    # El archivo trae PORCENTAJES; el modelo ahora trabaja en dólares. Se escalan sobre una
    # base de $10.000 (25% → $2.500): conserva las proporciones y da montos editables.
    pcts = [max(float(it["weight"]), 0.0) for it in cand["items"]]
    total = sum(pcts) or 1.0
    amounts = [p / total * 10_000.0 for p in pcts]
    set_portfolio(pid, symbols, amounts)
    st.session_state.setdefault("portfolio_names", {})[pid] = cand.get("name") or PLABEL[pid]


def render_candidate_importer() -> None:
    """Sube un archivo (CSV/Excel) y CARGA sus portafolios en los slots visibles.

    No tiene botón propio de análisis: los portafolios quedan arriba y se analizan con el
    botón principal "Analizar" — el mismo pipeline que el armado manual.
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
        if up is None:
            st.session_state.pop("_loaded_file", None)
            return

        # Guard: cargar solo cuando el archivo cambia (si no, pisaría ediciones en cada rerun).
        stamp = f"{getattr(up, 'file_id', '')}|{up.name}|{up.size}"
        if st.session_state.get("_loaded_file") != stamp:
            try:
                cands = portfolio_import.parse_portfolios(up.name, up.getvalue())
            except Exception as e:
                st.session_state["_loaded_file"] = stamp
                st.session_state.pop("cand_ports", None)
                st.error(f"No se pudo leer el archivo: {e}")
                return
            # Reemplaza los slots: lo que ves arriba es exactamente lo que se analizará.
            st.session_state["portfolios"] = {}
            st.session_state["portfolio_names"] = {}
            for pid, cand in zip(PIDS, cands[:MAX_PORTFOLIOS]):
                _load_portfolio_into(pid, cand)
            st.session_state["cand_ports"] = cands
            st.session_state["_loaded_file"] = stamp
            st.rerun()

        cands = st.session_state.get("cand_ports") or []
        if not cands:
            return
        n = min(len(cands), MAX_PORTFOLIOS)
        st.success(f"✓ {n} portafolio{'s' if n != 1 else ''} cargado{'s' if n != 1 else ''} arriba. "
                   f"Pulsa **Analizar** para ver el análisis completo.")
        for cand in cands[:MAX_PORTFOLIOS]:
            compo = " · ".join(f"{round(it['weight'])}% {it['symbol']}" for it in cand["items"][:4])
            more = " …" if len(cand["items"]) > 4 else ""
            st.markdown(
                f"<div style='padding:3px 0'><b style='color:{S.TEXT_HI};font-size:13.5px'>{cand['name']}</b> "
                f"<span style='color:{S.TEXT_LO};font-size:11px'>· {len(cand['items'])} activos · "
                f"{compo}{more}</span></div>", unsafe_allow_html=True)


# ── Inputs (plan compartido + A/B + avanzadas) ───────────────────────────────
def render_inputs() -> dict | None:
    _init_portfolios()
    with components.card("plan"):
        components.card_head("◆", "Tu plan", "el capital sale de lo que inviertes en cada activo")
        # 3 columnas: se acabó el tercio muerto que dejaba el slider a media fila
        c1, c2, c3 = st.columns(3, gap="medium")
        with c1:
            aporte = num_input("Aporte mensual (USD)", 500, "aporte", min_value=0,
                               help="Cuánto sumas cada mes. El hábito de aportar es lo que más mueve el resultado.")
        with c2:
            meta = num_input("Meta final (USD, opcional)", 0, "meta", min_value=0,
                             help="Opcional: el patrimonio que te gustaría alcanzar. Verás la probabilidad de lograrlo.")
        with c3:
            horizonte = st.slider("Horizonte (años)", min_value=1, max_value=40, value=20,
                                  help="Por cuántos años proyectas. Más tiempo = más interés compuesto y más incertidumbre.")


    pids = _active_pids()
    built: dict[str, tuple[list[str], list[float], float]] = {}
    with components.card("portafolio"):
        if len(pids) == 1:
            components.card_head("◆", "Tu portafolio", "Busca y agrega activos")
            built[pids[0]] = render_portfolio_builder(pids[0])
        else:
            components.card_head("◆", f"Compara {len(pids)} portafolios",
                                 "Edítalos; se analizan todos")
            tabs = st.tabs([f"  {_pname(p)}  " for p in pids])
            for tab, pid in zip(tabs, pids):
                with tab:
                    if st.button("✕  Quitar este portafolio", key=f"rm_pf_{pid}"):
                        st.session_state.portfolios.pop(pid, None)
                        st.session_state.get("portfolio_names", {}).pop(pid, None)
                        st.rerun()
                    built[pid] = render_portfolio_builder(pid)

    if len(pids) < MAX_PORTFOLIOS:
        with st.container(key="addb"):
            if st.button("＋  Añadir nuevo portafolio", use_container_width=True):
                slot = _free_pid()
                if slot:
                    st.session_state.portfolios[slot] = [dict(x) for x in DEFAULT_B]
                    st.rerun()

    # Defaults de avanzadas (stress, secuencia y benchmark S&P 500 SIEMPRE activos)
    dist_label, fees, tax = "Normal", 0.0, 0.0
    retirement = False
    withdrawal = 1_500.0

    not_ready = [p for p in pids if not (built[p][0] and built[p][2] > 0)]
    if not_ready:
        st.button(f"🔒  Agrega un activo a {_pname(not_ready[0])} para analizar",
                  type="primary", use_container_width=True, disabled=True)
        return None

    # Botón principal ÚNICO "Analizar"; "Opciones avanzadas" como expander DEBAJO.
    # (Los widgets del expander se ejecutan antes del gate `if not clicked`, así que sus
    #  valores locales quedan listos al construir el spec — sin session_state extra.)
    label = "◈  Analizar" if len(pids) == 1 else f"◈  Analizar los {len(pids)} portafolios"
    clicked = st.button(label, type="primary", use_container_width=True)

    # "Subir portafolio con archivo" — entre Analizar y Opciones avanzadas.
    # Pareja [importar archivo | opciones avanzadas]: dos utilidades secundarias que
    # no merecen una fila completa cada una. Bajo 900px el namespace pair- las apila.
    with st.container(key="pair-utils"):
        uc1, uc2 = st.columns(2, gap="medium")
    with uc1:
        render_candidate_importer()

    with uc2, st.expander("Opciones avanzadas"):
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
        st.divider()
        retirement = st.checkbox(
            "Modo retiro (en vez de aportar, retiras)",
            help="Simula que ya no aportas sino que retiras dinero cada mes (modo jubilación).")
        withdrawal = num_input(
            "Retiro mensual (USD) — modo retiro", 1_500, "withdrawal", min_value=0,
            help="Cuánto retiras por mes cuando activas el modo retiro.")

    if not clicked:
        return None

    # La validación de tickers se hace en main() BAJO el overlay de carga (así se nota que
    # la app reaccionó desde el clic, sin quedarse "estancada" con un spinner chiquito).
    monthly_flow = -withdrawal if retirement else aporte
    base = {
        "initial_capital": 0.0, "monthly_contribution": monthly_flow,  # lo fija cada portafolio
        "horizon_years": int(horizonte),
        "target": (meta if (meta > 0 and not retirement) else None),
        "historical_window_years": 10, "n_simulations": 10_000,
        "distribution": "t-student" if dist_label.startswith("t-") else "normal",
        "annual_fees_pct": fees, "annual_tax_on_gains_pct": tax,
        "compare": True, "show_stress": True, "show_sequence": True,
        "random_seed": random.randrange(1_000_000_000),  # mismo seed A y B (comparación justa)
    }
    portfolios = []
    for pid in pids:
        syms, ws, tw = built[pid]
        # El capital inicial de CADA portafolio es la suma de lo invertido en sus activos.
        portfolios.append({"pid": pid, "name": _pname(pid), "tickers": syms,
                           "weights": [w / tw for w in ws], "initial_capital": float(tw),
                           "amounts": list(ws)})
    return {"base": base, "portfolios": portfolios}


# ── Helpers de render ────────────────────────────────────────────────────────
def _success_color(prob: float) -> str:
    return S.GREEN if prob >= 0.70 else (S.ORANGE if prob >= 0.50 else S.RED)


def _md_money(text: str) -> str:
    """Escapa '$' para que Streamlit no lo interprete como LaTeX.

    SOLO para markdown puro (`st.markdown("texto")`). Dentro de HTML crudo NO debe
    usarse: ahí Streamlit no procesa markdown y la barra invertida se vería literal
    ("\\$876,208" en pantalla), que es justo lo que pasaba en el veredicto de varios
    portafolios y en la lectura del modo retiro.
    """
    return text.replace("$", "\\$")


def _b(txt, color=S.TEXT_HI) -> str:
    return f"<b style='color:{color}'>{txt}</b>"


def _lectura_card(color: str, html: str) -> None:
    st.markdown(f"<div class='dlp-card dlp-card-left' style='border-left-color:{color};'>"
                f"<div class='kpi-label'>Lectura</div>"
                f"<div style='color:{S.TEXT_MD};font-size:15px;margin-top:8px;line-height:1.55;'>"
                f"{html}</div></div>", unsafe_allow_html=True)


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
        # Arriba: tacómetro (izq., compacto) + análisis (der.). Abajo: los 3 indicadores en fila.
        g, an = st.columns([1, 1.25], gap="medium")
        with g:
            _corr = float(s["wavg_corr"])
            _dcol = S.GREEN if _corr < 0.45 else (S.ORANGE if _corr < 0.75 else S.RED)
            components.meter_stat("Correlación media del portafolio", f"{_corr:.2f}", _dcol,
                                  pos=1.0 - max(0.0, min(_corr, 1.0)),
                                  sub="0 = motores independientes · 1 = todo se mueve junto",
                                  ends=("todo junto", "independientes"))
        with an:
            st.markdown(
                f"<div class='dlp-card dlp-card-left dlp-analysis-box' style='border-left-color:{S.ORANGE};'>"
                f"<div class='kpi-label'>¿Qué significa esto?</div>"
                f"<div class='body'>{interpret.interpret_diversification(s)}</div></div>",
                unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3, gap="small")
        with k1:
            components.kpi_tile("Apuestas independientes", f"{s['eff_bets']:.1f}", S.BLUE,
                                f"de {s['n_assets']} activos",
                                help="Cuántas apuestas realmente distintas tienes. Si tus activos se "
                                     "mueven juntos, muchos nombres equivalen a pocas apuestas reales.",
                                rating=rating.rate("eff_bets", s["eff_bets"]))
        with k2:
            components.kpi_tile("Mayor posición", components.fmt_pct(s["max_weight"]), S.ORANGE,
                                s["max_weight_symbol"],
                                help="Qué porcentaje del portafolio está en tu activo más grande. "
                                     "Mucho en uno solo = más vulnerable a que a ese le vaya mal.",
                                rating=rating.rate("concentration", s["max_weight"]))
        with k3:
            components.kpi_tile("Efecto diversificación", f"{s['diversification_ratio']:.2f}×",
                                S.GREEN, "estabilidad ganada",
                                help="Cuánto más estable es el conjunto que sus piezas por separado. "
                                     "1.00× = no ganas nada al mezclar; 1.30× o más = la mezcla "
                                     "amortigua de verdad los golpes.",
                                rating=rating.rate("div_ratio", s["diversification_ratio"]))

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
        _f5 = findings[:5]
        with st.container(key=f"pair-find-{kp}"):
            fcol1, fcol2 = st.columns(2, gap="small")
        for _i, fd in enumerate(_f5):
            with (fcol1 if _i % 2 == 0 else fcol2):
                components.finding_card(fd)

    # 4) RETORNO, RIESGO Y LO QUE PUEDES PERDER — tiles con termómetro.
    with components.card(f"an-metrics-{kp}"):
        components.card_head("◆", "Retorno, riesgo y lo que puedes perder")
        m = st.columns(3)
        with m[0]:
            components.kpi_tile("Retorno compuesto", components.fmt_pct(s["cagr"]), S.GREEN,
                                f"al año · promedio {components.fmt_pct(s['ann_return'])}",
                                help="La tasa a la que tu dinero REALMENTE capitaliza (CAGR). Es menor "
                                     f"que el promedio simple ({components.fmt_pct(s['ann_return'])}) porque el "
                                     "vaivén cobra un peaje: caer 50% exige subir 100% para volver.",
                                rating=rating.rate("cagr", s["cagr"]))
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


def _exposure_for(inputs: dict) -> dict | None:
    """Exposición por sector/clase del portafolio (cacheada por símbolos+montos)."""
    try:
        from data import sectors as sect
        items = [{"symbol": t, "weight": w} for t, w in zip(inputs["tickers"], inputs["weights"])]
        return sect.portfolio_exposure(items)
    except Exception:
        return None


def _currency_note(inputs: dict) -> str:
    """Aviso cuando la cartera tiene activos que no cotizan en dólares. Todas las
    series se llevan a USD antes de calcular, así que el resultado ya incluye el
    efecto divisa; conviene que el usuario lo sepa."""
    try:
        cur = market_data.currencies_of(inputs.get("tickers") or [])
        otras = sorted({c for c in cur.values() if c and c != "USD"})
        if not otras:
            return ""
        return ("Incluye activos que cotizan en " + ", ".join(otras) +
                ". Se convierten a dólares al tipo de cambio de mercado, así que la "
                "proyección ya incorpora el efecto divisa.")
    except Exception:
        return ""


def _sync_note(inputs: dict) -> str:
    """Aviso cuando la cartera opera en bolsas con horarios distintos. Ahí las
    correlaciones se miden en ventanas semanales: comparar cierres del mismo día
    entre Tokio y Nueva York las empujaría hacia cero y subestimaría el riesgo."""
    try:
        if not market_data._needs_sync_fix(inputs.get("tickers") or []):
            return ""
        return ("Tus activos cotizan en bolsas con horarios distintos. Las correlaciones "
                "se miden en ventanas semanales para no subestimar el riesgo ni exagerar "
                "la diversificación.")
    except Exception:
        return ""


# ── Sección "Comparación": tu portafolio vs S&P 500 (siempre disponible) ─────
def render_benchmark_section(result, inputs, benchmarks, kp) -> None:
    """Comparación de alto valor contra el S&P 500: overlay + métricas cara a cara +
    probabilidad de superarlo + lectura en lenguaje natural. Reusa datos ya calculados
    (el benchmark se simula una sola vez en main y trae su propio `analysis`)."""
    if not benchmarks:
        st.info("La comparación contra el S&P 500 estará disponible en el próximo análisis.")
        return
    bench = benchmarks[0]
    bres = bench["result"]
    years = inputs["horizon_years"]

    # Probabilidad estimada de terminar por encima del índice (entre distribuciones).
    fv, bfv = result["final_values"], bres["final_values"]
    m = min(len(fv), len(bfv))
    prob_beat = float(np.mean(fv[:m] > bfv[:m])) if m else None

    with components.card(f"cmp-fan-{kp}"):
        components.card_head("◆", f"Tu portafolio vs S&P 500", f"proyección a {years} años")
        scen = [{"label": "Tu portafolio", "percentiles": result["percentiles"]},
                {"label": "S&P 500", "percentiles": bres["percentiles"]}]
        st.plotly_chart(charts.comparison_fan_chart(scen, result["months"], inputs["target"]),
                        use_container_width=True, config={"displayModeBar": False}, key=f"cmpfan_{kp}")

    s = (result.get("analysis") or {}).get("structure", {})
    bs = (bres.get("analysis") or {}).get("structure", {})
    med = float(np.percentile(fv, 50))
    bmed = float(np.percentile(bfv, 50))
    with st.container(key=f"pair-cmp-{kp}"):
        cmpl, cmpr = st.columns([1.5, 1], gap="medium")
    with cmpl, components.card(f"cmp-kpis-{kp}"):
        components.card_head("◆", "Cara a cara", "tú vs el índice, con calificación")
        m1 = st.columns(3)
        with m1[0]:
            components.kpi_tile("Mediana proyectada", components.fmt_money(med), S.ORANGE,
                                f"S&P 500: {components.fmt_money(bmed)}",
                                help="El escenario central de cada uno a igual aporte y horizonte. "
                                     "Es la vara más directa: ¿tu mezcla proyecta más que el índice?",
                                rating=rating.rating(0.75 if med >= bmed else 0.3,
                                                     "Supera" if med >= bmed else "Debajo"))
        with m1[1]:
            cagr, bcagr = s.get("cagr"), bs.get("cagr")
            if cagr is not None and bcagr is not None:
                components.kpi_tile("Retorno compuesto", components.fmt_pct(cagr), S.GREEN,
                                    f"S&P 500: {components.fmt_pct(bcagr)}",
                                    help="La tasa real a la que capitaliza cada uno (ya descontado el "
                                         "peaje de la volatilidad).",
                                    rating=rating.rate("cagr", cagr))
        with m1[2]:
            vol, bvol = s.get("ann_vol"), bs.get("ann_vol")
            if vol is not None and bvol is not None:
                components.kpi_tile("Volatilidad", "±" + components.fmt_pct(vol), S.ORANGE,
                                    f"S&P 500: ±{components.fmt_pct(bvol)}",
                                    help="El vaivén anual de cada camino. Más volatilidad exige más "
                                         "estómago para no vender en pánico.",
                                    rating=rating.rate("volatility", vol or 0))
        m2 = st.columns(3)
        with m2[0]:
            components.kpi_tile("Caída típica", components.fmt_pct(result["max_drawdown_typical"]),
                                S.BLUE, f"S&P 500: {components.fmt_pct(bres['max_drawdown_typical'])}",
                                help="Cuánto retrocede cada uno en un mal momento. Es el precio "
                                     "emocional del camino elegido.",
                                rating=rating.rate("drawdown", result["max_drawdown_typical"]))
        with m2[1]:
            components.kpi_tile("Eficiencia", f"{result['expected_sharpe']:.2f}", S.GOLD,
                                f"S&P 500: {bres['expected_sharpe']:.2f}",
                                help="Sharpe: retorno por unidad de riesgo (con tasa libre 4%). "
                                     "Más alto = mejor pagado el vaivén que asumes.",
                                rating=rating.rate("sharpe", result["expected_sharpe"]))
        with m2[2]:
            if prob_beat is not None:
                components.kpi_tile("Supera al índice", components.fmt_pct(prob_beat), S.GREEN,
                                    "de los escenarios (estimado)",
                                    help="En qué fracción de los 10.000 futuros simulados tu portafolio "
                                         "termina por encima del S&P 500. Estimación, no garantía.",
                                    rating=rating.rate("prob_beat", prob_beat))

    with cmpr, components.card(f"cmp-read-{kp}"):
        components.card_head("◆", "¿Qué dice esta comparación?")
        st.markdown(_md_money(interpret.interpret_benchmark(result, inputs, bench, prob_beat)))


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

    # Secciones con estado PROPIO por portafolio (st.tabs no acepta `key` y se reinicia al
    # cambiar de portafolio). Con segmented_control keyed, cada portafolio recuerda en qué
    # sección estabas y son independientes entre sí.
    sections = ["Resumen", "Análisis", "¿Alcanzo mi meta?", "Riesgo", "Comparación"]
    sect_key = f"sect_{kp}"
    if st.session_state.get(sect_key) not in sections:
        st.session_state[sect_key] = sections[0]
    with st.container(key=f"sectbar_{kp}"):
        st.radio("Sección", sections, key=sect_key, horizontal=True, label_visibility="collapsed")
    sect = st.session_state.get(sect_key) or sections[0]

    if sect == "Resumen":
        # 1) Proyección primero de todo — con línea gris "Aportado" vs "Invertido".
        with components.card(f"res-fan-{kp}"):
            components.card_head("◆", f"Proyección a {years} años",
                                 "pasa el cursor: aportado vs invertido")
            st.plotly_chart(
                charts.fan_chart(result["percentiles"], result["months"], inputs["target"],
                                 initial_capital=inputs["initial_capital"],
                                 monthly_contribution=inputs["monthly_contribution"]),
                use_container_width=True, config={"displayModeBar": False}, key=f"fan_{kp}")
        # Composición: dona por activo + exposición por sector (fila 1) y por tipo (fila 2)
        with components.card(f"res-compo-{kp}"):
            components.card_head("◆", "Composición y exposición",
                                 "en qué está tu dinero, por activo y por sector")
            cc1, cc2 = st.columns(2, gap="medium")
            with cc1:
                st.markdown(f"<div class='dlp-side-title' style='margin:0 0 2px'>Por activo</div>",
                            unsafe_allow_html=True)
                st.plotly_chart(charts.allocation_donut(items), use_container_width=True,
                                config={"displayModeBar": False}, key=f"donut_res_{kp}")
            with cc2:
                st.markdown(f"<div class='dlp-side-title' style='margin:0 0 2px'>Por sector</div>",
                            unsafe_allow_html=True)
                exp = _exposure_for(inputs)
                if exp and exp["by_sector"]:
                    st.plotly_chart(charts.sector_bar(exp["by_sector"]), use_container_width=True,
                                    config={"displayModeBar": False}, key=f"sector_{kp}")
                else:
                    st.caption("No se pudo clasificar el sector de estos activos.")
            if exp and exp["by_class"]:
                st.markdown(f"<div class='dlp-side-title' style='margin:6px 0 0'>Por tipo de activo</div>",
                            unsafe_allow_html=True)
                st.plotly_chart(charts.asset_class_bar(exp["by_class"]), use_container_width=True,
                                config={"displayModeBar": False}, key=f"class_{kp}")
            _cnote = _currency_note(inputs)
            if _cnote:
                st.caption(_cnote)
            _snote = _sync_note(inputs)
            if _snote:
                st.caption(_snote)

        with st.container(key=f"pair-res-{kp}"):
            resl, resr = st.columns([1.25, 1], gap="medium")
        with resl, components.card(f"res-top-{kp}"):
            components.card_head("◆", "Tus escenarios a futuro", "de peor a mejor")
            # Los 3 escenarios en UNA fila horizontal, mismo alto y ancho
            k1, k2, k3 = st.columns(3, gap="small")
            with k1:
                components.kpi_tile("Si va mal", components.fmt_money(p5), S.RED, "1 de 20 (P5)",
                                    help="Percentil 5: solo 1 de cada 20 escenarios terminó peor que esto. "
                                         "Es tu 'si va mal' razonable, no el peor caso absoluto.",
                                    rating=rating.rating(0.13, "Pesimista"))
            with k2:
                components.kpi_tile("Lo más probable", components.fmt_money(p50), S.ORANGE, "el del medio",
                                    help="La mediana: la mitad de los escenarios terminó por encima y la "
                                         "mitad por debajo. El resultado más representativo.",
                                    rating=rating.rating(0.5, "Central"))
            with k3:
                components.kpi_tile("Si va bien", components.fmt_money(p95), S.GREEN, "1 de 20 (P95)",
                                    help="Percentil 95: solo 1 de cada 20 escenarios terminó mejor que esto. "
                                         "Tu 'si va bien' razonable, no el mejor caso absoluto.",
                                    rating=rating.rating(0.87, "Optimista"))
        with resr, components.card(f"res-interp-{kp}"):
            components.card_head("◆", "¿Qué significa esto?")
            _txt = interpret.interpret_locally(result, inputs, extras.get("stress"))
            _parts = _txt.split("\n\n")
            _fine = _parts[-1].strip("_ ") if _parts[-1].lstrip().startswith("_") else ""
            st.markdown(_md_money("\n\n".join(_parts[:-1] if _fine else _parts)))
            if _fine:
                st.markdown(f"<div class='dlp-fineprint'>{_fine}</div>",
                            unsafe_allow_html=True)

    if sect == "Análisis":
        render_analysis_panel(result, inputs, kp)

    if sect == "¿Alcanzo mi meta?":
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
                with g:
                    components.meter_stat("Probabilidad de ruina", f"{ruin*100:.0f}%", col,
                                          pos=1.0 - min(ruin / 0.4, 1.0),
                                          sub=f"escenarios donde el capital se agota antes de {years} años",
                                          ends=("frágil", "sólido"))
                with t:
                    _lectura_card(col, f"Retirando {components.fmt_money(abs(inputs['monthly_contribution']))}/mes, "
                                  f"tu capital se agotó antes de los {years} años en "
                                  f"<b style='color:{col}'>{ruin*100:.0f}%</b> de los escenarios.")
        elif inputs["target"]:
            prob = result["prob_target"] or 0.0
            with components.card(f"dist-meta-{kp}"):
                components.card_head("◆", "Probabilidad de alcanzar tu meta")
                g, t = st.columns([1, 1])
                with g:
                    components.meter_stat("Probabilidad de lograrla", f"{prob*100:.0f}%",
                                          _success_color(prob), pos=prob,
                                          sub=f"meta: {components.fmt_money(inputs['target'])} a {years} años",
                                          ends=("difícil", "probable"))
                with t:
                    _lectura_card(_success_color(prob),
                                  f"En <b style='color:{_success_color(prob)}'>{prob*100:.0f}%</b> de los 10.000 "
                                  f"escenarios alcanzaste {components.fmt_money(inputs['target'])} a {years} años. "
                                  f"No es garantía: los retornos futuros pueden diferir.")
        # Interpretación en lenguaje natural (haya o no meta) — indistinguible de IA.
        with components.card(f"meta-interp-{kp}"):
            components.card_head("◆", "¿Qué dice esta gráfica?")
            st.markdown(_md_money(interpret.interpret_goal(result, inputs)))

    if sect == "Riesgo":
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
        sd = extras.get("stress")
        if sd:
            # Pareja [lectura de riesgos | prueba de estrés]: media pantalla cada una.
            with st.container(key=f"pair-risk-{kp}"):
                rl, rr = st.columns([1, 1.45], gap="medium")
            with rl, components.card(f"risk-interp-{kp}"):
                components.card_head("◆", "Lectura de tus riesgos")
                st.markdown(_md_money(interpret.interpret_risks(result, inputs, result.get("analysis"))))
            with rr, components.card(f"risk-stress-{kp}"):
                components.card_head("◆", "Cuánto habría caído en un mal momento",
                                     "análisis de estrés real")
                st.plotly_chart(charts.stress_drop_bars(sd), use_container_width=True,
                                config={"displayModeBar": False}, key=f"stress_{kp}")
                # Separador + porcentaje bajo CADA barra, alineado con las columnas del chart
                st.markdown("<div class='dlp-stress-sep'></div>", unsafe_allow_html=True)
                cols = st.columns(len(sd["events"]))
                for col, ev in zip(cols, sd["events"]):
                    with col:
                        st.markdown(
                            f"<div class='dlp-stress-foot'>"
                            f"<div class='pct'>−{ev['portfolio_drawdown']*100:.0f}%</div></div>",
                            unsafe_allow_html=True)
                _lectura_card(S.ORANGE, interpret.interpret_stress(sd, result, inputs))
        else:
            with components.card(f"risk-interp-{kp}"):
                components.card_head("◆", "Lectura de tus riesgos")
                st.markdown(_md_money(interpret.interpret_risks(result, inputs, result.get("analysis"))))

    if sect == "Comparación":
        render_benchmark_section(result, inputs, benchmarks, kp)

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
    high, hcol = ("A", PCOLOR["A"]) if medA >= medB else ("B", PCOLOR["B"])
    low_dd, lcol = ("A", PCOLOR["A"]) if ddA <= ddB else ("B", PCOLOR["B"])
    m_high, m_low = (medA, medB) if high == "A" else (medB, medA)
    dd_low_val = min(ddA, ddB)
    dd_high_val = max(ddA, ddB)
    parts = [f"En la mediana, el {_b(_pname(high), hcol)} proyecta más "
             f"({components.fmt_money(m_high)} vs {components.fmt_money(m_low)})."]
    if low_dd == high:
        parts.append(f"Y además es el más estable (caída típica {dd_low_val:.0f}% vs {dd_high_val:.0f}%): "
                     f"luce mejor en crecimiento y en estabilidad — aunque no es garantía.")
        lead = hcol
    else:
        parts.append(f"Pero el {_b(_pname(low_dd), lcol)} es más estable (caída típica menor: "
                     f"{dd_low_val:.0f}% vs {dd_high_val:.0f}%). Es un trade-off entre crecimiento y "
                     f"estabilidad: depende de tu tolerancia al riesgo.")
        lead = S.GOLD
    if iA.get("target"):
        pA, pB = (rA["prob_target"] or 0) * 100, (rB["prob_target"] or 0) * 100
        bp, bpcol = ("A", PCOLOR["A"]) if pA >= pB else ("B", PCOLOR["B"])
        parts.append(f"Para tu meta, el {_b(_pname(bp), bpcol)} tiene mayor probabilidad de alcanzarla "
                     f"({max(pA, pB):.0f}% vs {min(pA, pB):.0f}%).")
    return " ".join(parts), lead


def _compo(inputs) -> str:
    """Resumen corto de composición: '60% SPY · 40% BND'."""
    pairs = sorted(zip(inputs["tickers"], inputs["weights"]), key=lambda x: -x[1])
    s = " · ".join(f"{round(w * 100)}% {t}" for t, w in pairs[:3])
    return s + (" …" if len(pairs) > 3 else "")


def _side_head(pid: str, med: float, compo: str) -> str:
    col = PCOLOR[pid]
    return (f"<div class='dlp-side'><div class='nm' style='color:{col}'>"
            f"<span style='color:{col}'>●</span> {_pname(pid)}</div>"
            f"<div class='big' style='color:{S.TEXT_HI}'>{components.fmt_money(med)}</div>"
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
            f"<div class='m-row'><span class='m-tag' style='color:{PCOLOR['A']}'>A</span>"
            f"<div class='m-track'><div class='m-fill' style='width:{wa:.0f}%;background:{PCOLOR['A']}'></div></div>"
            f"<span class='m-val{aw}'>{fmt(a, kind)}</span></div>"
            f"<div class='m-row'><span class='m-tag' style='color:{PCOLOR['B']}'>B</span>"
            f"<div class='m-track'><div class='m-fill' style='width:{wb:.0f}%;background:{PCOLOR['B']}'></div></div>"
            f"<span class='m-val{bw}'>{fmt(b, kind)}</span></div></div>")
    return html


def render_compare(rA, iA, exA, rB, iB, exB, benchmarks, elapsed=None) -> None:
    components.disclaimer_banner()
    medA = float(np.percentile(rA["final_values"], 50))
    medB = float(np.percentile(rB["final_values"], 50))
    itemsA = [{"symbol": t, "weight": w * 100} for t, w in zip(iA["tickers"], iA["weights"])]
    itemsB = [{"symbol": t, "weight": w * 100} for t, w in zip(iB["tickers"], iB["weights"])]

    # Pareja [cara a cara | veredicto]: el VS y el juicio conviven en una fila
    with st.container(key="pair-cmpvs"):
        pcl, pcr = st.columns([1.35, 1], gap="medium")
    with pcl, components.card("cmp-vs"):
        components.card_head("◆", "Cara a cara", "Portafolio A vs Portafolio B")
        ca, cv, cb = st.columns([1, 0.18, 1])
        with ca:
            st.markdown(_side_head("A", medA, _compo(iA)), unsafe_allow_html=True)
            st.plotly_chart(charts.allocation_donut(itemsA, lead_color=PCOLOR["A"]), use_container_width=True,
                            config={"displayModeBar": False}, key="vs_dA")
        with cv:
            st.markdown("<div class='dlp-vs-badge'><span>VS</span></div>", unsafe_allow_html=True)
        with cb:
            st.markdown(_side_head("B", medB, _compo(iB)), unsafe_allow_html=True)
            st.plotly_chart(charts.allocation_donut(itemsB, lead_color=PCOLOR["B"]), use_container_width=True,
                            config={"displayModeBar": False}, key="vs_dB")
    with pcr, components.card("cmp-verdict"):
        components.card_head("◆", "Veredicto", "¿cuál proyecta mejor?")
        verdict, lead = _compare_verdict(rA, iA, rB)
        components.verdict_card(lead, verdict)

    # Métrica a métrica (barras enfrentadas) en DOS columnas: mitad del scroll
    with components.card("cmp-bars"):
        components.card_head("◆", "Métrica a métrica", "◆ = mejor")
        _bars = _metric_bars(rA, rB, iA)
        st.markdown(f"<div class='dlp-vsm-grid'>{_bars}</div>", unsafe_allow_html=True)

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
            render_single(rA, iA, exA, benchmarks, "dA", with_hero=False, with_actions=False)
        with dtB:
            render_single(rB, iB, exB, benchmarks, "dB", with_hero=False, with_actions=False)

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
        st.download_button("⬇  Descargar Análisis en PDF", data=st.session_state["pdf_bytes"],
                           file_name="proyeccion_portafolio.pdf", mime="application/pdf",
                           use_container_width=True, key="pdfdl")
        if st.session_state.pop("_pdf_just", False):
            import streamlit.components.v1 as stc
            stc.html("<script>setTimeout(function(){var b=window.parent.document."
                     "querySelector('.st-key-pdfdl button'); if(b){b.click();}}, 250);</script>", height=0)
    else:
        if slot.button("▸  Descargar Análisis en PDF", use_container_width=True, key="pdfgo"):
            st.session_state["_pdf_loading"] = True
            st.rerun()


# ── Comparación de 3 portafolios (ranking + análisis completo de cada uno) ───
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


def render_multi(runs: list[dict], benchmarks=None, elapsed=None) -> None:
    """Comparación de 3 portafolios: ranking + overlay + ANÁLISIS COMPLETO de cada uno.

    Recibe los `runs` del pipeline único (mismos inputs/extras que el modo de 1 o 2), así
    que el análisis por portafolio es idéntico al del flujo principal.
    """
    results = [r for r in runs if r.get("result") is not None]
    if not results:
        st.error("No se pudo analizar ningún portafolio. Revisa que los tickers existan en el mercado.")
        return

    target = results[0]["inputs"].get("target")
    years = results[0]["inputs"]["horizon_years"]

    components.disclaimer_banner()
    rows = _cand_metric_rows(results, target)
    best = max(rows, key=lambda x: x["p50"])
    safest = min(rows, key=lambda x: x["dd"])

    with st.container(key="pair-candtop"):
        _ctl, _ctr = st.columns([1, 1.55], gap="medium")
    with _ctl, components.card("cand-verdict"):
        components.card_head("◆", "El mejor portafolio", "según la proyección")
        v = (f"El portafolio {_b(best['name'], S.ORANGE)} proyecta la mayor mediana a "
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
        components.verdict_card(S.GOLD, v)

    with _ctr, components.card("cand-board"):
        components.card_head("◆", "Ranking de portafolios", "◆ = mejor en cada métrica")
        _tbl = _candidates_table(rows, target, best["name"])
        st.markdown("<div class='dlp-table-scroll'>" + _tbl + "</div>", unsafe_allow_html=True)
        st.caption("Ordenados por mediana proyectada. 'Caída típica' y 'Eficiencia (Sharpe)' miden "
                   "el riesgo: menos caída y más Sharpe es mejor.")

    with components.card("cand-fan"):
        components.card_head("◆", "Proyección comparada", "mediana + rango P5–P95 de cada portafolio")
        scen = [{"label": r["name"], "percentiles": r["result"]["percentiles"]} for r in rows]
        st.plotly_chart(charts.comparison_fan_chart(scen, results[0]["result"]["months"], target),
                        use_container_width=True, config={"displayModeBar": False}, key="cand_fan_chart")

    with components.card("cand-compo"):
        components.card_head("◆", "Composición de cada portafolio", "qué activos tiene y con qué peso")
        # Un candidato por COLUMNA (dona arriba, lista debajo): 3 de ancho, sin dividers.
        _orden = sorted(rows, key=lambda x: -x["p50"])
        with st.container(key="pair-candcompo"):
            _ccols = st.columns(min(len(_orden), 3), gap="medium")
        for idx, r in enumerate(_orden):
            items = r["items"]
            is_best = r["name"] == best["name"]
            nmcol = S.ORANGE if is_best else S.TEXT_HI
            tag = " · mayor mediana" if is_best else ""
            with _ccols[idx % len(_ccols)]:
                st.markdown(
                    f"<div style='margin:2px 0 2px;'><b style='color:{nmcol};font-family:{S.MONO};"
                    f"font-size:13.5px;letter-spacing:.03em;'>{r['name'][:24]}</b>"
                    f"<span style='color:{S.TEXT_LO};font-size:11px;'> · {len(items)} activos{tag}</span></div>",
                    unsafe_allow_html=True)
                st.plotly_chart(charts.allocation_donut(items), use_container_width=True,
                                config={"displayModeBar": False}, key=f"cand_compo_donut_{idx}")
                st.markdown(_candidate_composition_html(items), unsafe_allow_html=True)

    # ANÁLISIS COMPLETO de cada portafolio (mismas pestañas que el modo de 1 portafolio).
    st.markdown("<div class='dlp-side-title' style='margin-top:18px'>Análisis completo de cada "
                "portafolio</div>", unsafe_allow_html=True)
    tabs = st.tabs([f"  {r['name'][:22]}  " for r in results])
    for i, (tab, r) in enumerate(zip(tabs, results)):
        with tab:
            render_single(r["result"], r["inputs"], r.get("extras") or {}, benchmarks,
                          f"m{i}", with_hero=False, with_actions=False)

    _render_pdf_button(results[0]["result"], results[0]["inputs"], benchmarks)
    if elapsed is not None:
        dist = "t-Student" if results[0]["inputs"]["distribution"] == "t-student" else "Normal"
        st.caption(f"◇ {len(results)} portafolios × {results[0]['inputs']['n_simulations']:,} escenarios · "
                   f"{dist} · {elapsed:.1f}s · ventana {results[0]['inputs']['historical_window_years']} años")


# ── App ──────────────────────────────────────────────────────────────────────
def _scroll_to_results() -> None:
    """Baja suavemente hasta la sección de resultados (una vez, al terminar de cargar).

    El componente corre en un iframe hijo → alcanza el documento de la app vía
    window.parent.document, donde vive el ancla '#dlp-results-anchor'.
    """
    import streamlit.components.v1 as stc

    stc.html(
        "<script>setTimeout(function(){try{var d=window.parent.document;"
        "var el=d.getElementById('dlp-results-anchor');"
        "if(el){el.scrollIntoView({behavior:'smooth',block:'start'});}}catch(e){}}, 180);</script>",
        height=0,
    )


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
    _prewarm_once()           # calienta el renderizador del PDF en segundo plano
    S.disable_context_menu()  # bloquea el menú de clic derecho en toda la app
    _require_fase2_access()   # portada con clave SOLO en el link ?fase2 (el normal no cambia)
    _require_password()
    components.page_hero()

    spec = render_inputs()
    just_computed = False

    if spec is not None:
        base = spec["base"]
        runs_spec = spec["portfolios"]

        # UN SOLO overlay a pantalla completa, continuo desde el clic: validar → simular.
        loader = st.empty()
        loader.markdown(components.progress_overlay(0, "Validando tickers…"), unsafe_allow_html=True)
        all_syms = list(dict.fromkeys([t for p in runs_spec for t in p["tickers"]]))
        _, invalid = market_data.validate_tickers(all_syms)
        if invalid:
            loader.empty()
            st.error(f"No se encontraron en el mercado: {', '.join(invalid)}. Quítalos o corrígelos.")
        else:
            # Suelo de tiempo del loader. El trabajo real ronda 2-3s (kaleido ya viene
            # caliente y las consultas de red van en paralelo); este objetivo deja que
            # el proceso se vea sin inventar espera de más. Antes eran 9-15s.
            target = random.uniform(5.0, 6.0)
            t0 = time.perf_counter()
            # PIPELINE ÚNICO: mismo `base` (Opciones avanzadas incluidas) + extras para TODOS
            # los portafolios, vengan del armador manual o de un archivo.
            runs: list[dict] = []
            n = len(runs_spec)
            for i, p in enumerate(runs_spec):
                loader.markdown(components.progress_overlay(
                    4 + round(i / max(n, 1) * 40),
                    f"Analizando {p['name']}…" if n > 1 else "Preparando tu análisis…"),
                    unsafe_allow_html=True)
                inputs = dict(base, tickers=p["tickers"], weights=p["weights"],
                              initial_capital=p["initial_capital"])
                result = compute(inputs)
                runs.append({"pid": p["pid"], "name": p["name"], "inputs": inputs,
                             "result": result, "extras": _build_extras(inputs, result)})
            benchmarks = run_benchmarks(runs[0]["inputs"])   # S&P 500: SIEMPRE
            # PDF pre-generado AQUÍ (dentro del tiempo del loader): al terminar el análisis,
            # la descarga es instantánea. Si kaleido fallara, cae al botón manual de siempre.
            loader.markdown(components.progress_overlay(52, "Preparando tu PDF…"), unsafe_allow_html=True)
            try:
                from dashboard import pdf_report
                pdf_bytes = pdf_report.generate_report(runs[0]["result"], runs[0]["inputs"], benchmarks)
            except Exception:
                pdf_bytes = None
            # Si el trabajo ya se pasó del objetivo, solo queda el cierre del anillo
            # hasta el 100% (antes se añadían 2s completos por encima).
            remaining = max(target - (time.perf_counter() - t0), 0.9)
            steps = max(int(remaining / 0.09), 20)
            for i in range(steps + 1):
                loader.markdown(components.progress_overlay(round(i / steps * 100), _loader_msg(round(i / steps * 100))),
                                unsafe_allow_html=True)
                time.sleep(remaining / steps)
            loader.empty()
            st.session_state.update(
                runs=runs, benchmarks=benchmarks, elapsed=time.perf_counter() - t0,
                pdf_bytes=pdf_bytes, _pdf_loading=False, _pdf_just=False)
            just_computed = True

    # Ancla para bajar automáticamente a los resultados al terminar de cargar.
    st.markdown("<div id='dlp-results-anchor' style='scroll-margin-top:6px'></div>", unsafe_allow_html=True)

    runs = st.session_state.get("runs") or []
    if runs:
        bench = st.session_state.get("benchmarks")
        elapsed = st.session_state.get("elapsed")
        with st.container(key="results-capsule"):   # cápsula metálica que encierra los resultados
            if len(runs) == 1:
                r = runs[0]
                render_single(r["result"], r["inputs"], r["extras"], bench, "A", elapsed=elapsed)
            elif len(runs) == 2:
                a, b = runs
                render_compare(a["result"], a["inputs"], a["extras"],
                               b["result"], b["inputs"], b["extras"], bench, elapsed)
            else:
                render_multi(runs, bench, elapsed)

    # Aviso legal: cierra SIEMPRE la pantalla principal, con o sin análisis hecho.
    components.legal_notice()

    if just_computed:
        _scroll_to_results()   # baja solo a la sección de análisis (una vez, tras cargar)


if __name__ == "__main__":
    main()
