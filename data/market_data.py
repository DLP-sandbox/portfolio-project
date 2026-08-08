"""Capa de datos de mercado: yfinance con caché + fallback de muestra.

Patrón 3 del spec: sanitizar y validar tickers ANTES de gastar llamadas de red.
Si yfinance falla o rate-limitea, se usa un set de datos de muestra empaquetado
en `data/sample_data/` y se marca `is_sample=True` para que la UI avise.

IMPORTANTE: los datos de muestra son ILUSTRATIVOS, no cotizaciones reales en vivo.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import streamlit as st

    # max_entries acota la caché: evita que el historial de precios de muchas
    # combinaciones de tickers se acumule sin límite en instancias con poca RAM.
    _cache = st.cache_data(ttl=3600, show_spinner=False, max_entries=64)
except Exception:  # pragma: no cover - permite usar el módulo fuera de Streamlit
    def _cache(func):
        return func

SAMPLE_DIR = Path(__file__).parent / "sample_data"
_TICKER_RE = re.compile(r"[^A-Za-z0-9.\-]")
TRADING_DAYS_PER_YEAR = 252


# ── Validación / sanitización (Patrón 3) ─────────────────────────────────────
def sanitize_ticker(raw: str) -> str:
    """strip + uppercase + solo letras/dígitos/./-  (acepta BRK-B, BRK.B, etc)."""
    return _TICKER_RE.sub("", (raw or "").strip()).upper()


def validate_tickers(tickers: list[str]) -> tuple[list[str], list[str]]:
    """Verifica existencia rápida con yfinance fast_info (≤1s, costo casi nulo).

    Returns (válidos, inválidos). Si la red falla para TODOS (no podemos verificar),
    asumimos problema de conectividad y devolvemos todos como válidos → el fallback
    de muestra se encarga después.
    """
    valid: list[str] = []
    invalid: list[str] = []
    try:
        import yfinance as yf
    except Exception:
        return list(tickers), []  # sin yfinance, dejamos pasar al fallback

    for sym in tickers:
        try:
            fi = yf.Ticker(sym).fast_info
            price = None
            for key in ("last_price", "lastPrice", "previous_close", "previousClose"):
                try:
                    price = fi[key] if not hasattr(fi, key) else getattr(fi, key)
                except Exception:
                    price = None
                if price:
                    break
            (valid if price and price > 0 else invalid).append(sym)
        except Exception:
            invalid.append(sym)

    # Si nada validó, casi seguro es la red caída → no bloqueamos al usuario.
    if not valid and invalid:
        return list(tickers), []
    return valid, invalid


# ── Descarga de precios + fallback ───────────────────────────────────────────
def _download_prices_live(tickers: tuple[str, ...], window_years: int) -> pd.DataFrame:
    """Descarga precios de cierre de yfinance. Puede lanzar excepción si falla la red."""
    import yfinance as yf

    raw = yf.download(
        list(tickers),
        period=f"{window_years}y",
        auto_adjust=True,
        progress=False,
    )
    if raw is None or len(raw) == 0:
        raise RuntimeError("yfinance devolvió datos vacíos")
    close = raw["Close"] if "Close" in raw else raw
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    # Reordenar columnas al orden pedido y limpiar
    cols = [t for t in tickers if t in close.columns]
    close = close[cols].dropna(how="all").ffill().dropna()
    if close.empty:
        raise RuntimeError("Series de precios vacía tras limpieza")
    return to_usd(close)


# ── Normalización de divisa a USD ────────────────────────────────────────────
# Un ETF europeo cotiza en EUR y una acción japonesa en JPY. Mezclarlos con activos
# en USD sin convertir da retornos, volatilidad y correlaciones INCORRECTOS: medido
# sobre IWDA.AS a 3 años, 13,0% de volatilidad anual en EUR frente a 14,5% real en
# USD. El efecto divisa es riesgo que el inversor asume de verdad, así que todas las
# series se llevan a USD (la divisa base de toda la app) antes de calcular nada.

# Yahoo distingue mayúsculas: "GBP" son libras y "GBp" son PENIQUES. Londres cotiza
# muchas acciones en peniques; sin dividir entre 100 entrarían con precios ×100.
_MINOR_UNITS = {"GBp": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ILA": ("ILS", 100.0)}


def _currency_of(symbol: str) -> str:
    """Divisa de cotización del activo. 'USD' si no se puede determinar."""
    # Atajo sin red: lo que está en el directorio de EE.UU. (NYSE/NASDAQ/Arca)
    # cotiza en dólares con certeza. Evita una consulta por activo en el caso más
    # común y deja las carteras estadounidenses exactamente igual de rápidas.
    try:
        from data import tickers as tdir

        df = tdir.load_directory()
        if bool((df["_sym_l"] == str(symbol).lower()).any()):
            return "USD"
    except Exception:
        pass
    try:
        import yfinance as yf

        t = yf.Ticker(symbol)
        cur = None
        try:  # fast_info es mucho más barato que .info
            cur = t.fast_info["currency"]
        except Exception:
            cur = None
        if not cur:
            cur = (t.info or {}).get("currency")
        return str(cur).strip() if cur else "USD"
    except Exception:
        return "USD"


def get_currency(symbol: str) -> str:
    """Divisa del activo, cacheada 24 h (cambia como mucho una vez en la vida)."""
    try:
        import streamlit as st

        return st.cache_data(ttl=86400, show_spinner=False)(_currency_of)(symbol)
    except Exception:
        return _currency_of(symbol)


@_cache
def _fx_raw(currency: str, start: str, end: str) -> pd.DataFrame:
    """Serie diaria {divisa}→USD (p.ej. EURUSD=X). DataFrame vacío si no existe."""
    import yfinance as yf

    raw = yf.download(f"{currency}USD=X", start=start, end=end,
                      auto_adjust=True, progress=False)
    if raw is None or len(raw) == 0:
        return pd.DataFrame()
    s = raw["Close"] if "Close" in raw else raw
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    return s.dropna().to_frame(name="fx")


def _fx_series(currency: str, index) -> pd.Series | None:
    """Tipo de cambio alineado al índice de precios (ffill: los festivos de cada
    plaza no coinciden). Devuelve None si no hay dato — nunca lanza."""
    try:
        start = (index.min() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        end = (index.max() + pd.Timedelta(days=2)).strftime("%Y-%m-%d")
        df = _fx_raw(currency, start, end)
        if df is None or df.empty:
            return None
        s = df["fx"]
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
        idx = index.tz_localize(None) if getattr(index, "tz", None) is not None else index
        s = s.reindex(s.index.union(idx)).ffill().bfill().reindex(idx)
        if s.isna().any():
            return None
        s.index = index
        return s
    except Exception:
        return None


def to_usd(close: pd.DataFrame) -> pd.DataFrame:
    """Lleva cada columna de precios a USD.

    Si TODO ya está en USD devuelve el DataFrame INTACTO: una cartera 100%
    estadounidense recorre exactamente el mismo camino de código que antes.
    Si falta el tipo de cambio de alguna divisa, esa columna se deja como está
    en vez de romper el análisis.
    """
    try:
        per_col = {c: _split_currency(get_currency(str(c))) for c in close.columns}
        if all(cur == "USD" and div == 1.0 for cur, div in per_col.values()):
            return close
        out = close.copy()
        rates = {}
        for cur in {c for c, _ in per_col.values() if c != "USD"}:
            rates[cur] = _fx_series(cur, close.index)
        for col, (cur, div) in per_col.items():
            if div != 1.0:
                out[col] = out[col] / div  # peniques → libras
            if cur == "USD":
                continue
            rate = rates.get(cur)
            if rate is not None:
                out[col] = out[col] * rate
        return out
    except Exception:
        return close


def _split_currency(cur: str) -> tuple[str, float]:
    """'GBp' → ('GBP', 100.0) · 'eur' → ('EUR', 1.0)."""
    if cur in _MINOR_UNITS:
        return _MINOR_UNITS[cur]
    return (str(cur).upper() or "USD", 1.0)


def currencies_of(tickers) -> dict[str, str]:
    """{ticker: divisa} para avisar en la UI. Silencioso ante cualquier fallo."""
    out: dict[str, str] = {}
    for t in tickers or []:
        try:
            out[str(t)] = _split_currency(get_currency(str(t)))[0]
        except Exception:
            out[str(t)] = "USD"
    return out


def _load_sample_prices(tickers: tuple[str, ...], window_years: int) -> pd.DataFrame:
    """Carga precios de muestra empaquetados. Para tickers sin archivo, sintetiza una
    serie determinística (semilla por ticker) claramente etiquetada como muestra."""
    series: dict[str, pd.Series] = {}
    for sym in tickers:
        f = SAMPLE_DIR / f"{sym}.csv"
        if f.exists():
            df = pd.read_csv(f, parse_dates=["Date"]).set_index("Date")
            series[sym] = df["Close"]
        else:
            series[sym] = _synthesize_series(sym, window_years)
    prices = pd.DataFrame(series).dropna(how="all").ffill().dropna()
    if window_years and not prices.empty:
        cutoff = prices.index.max() - pd.Timedelta(days=365 * window_years)
        prices = prices[prices.index >= cutoff]
    return prices


def _synthesize_series(sym: str, window_years: int) -> pd.Series:
    """Serie de precios SINTÉTICA (no real) para que la demo no se rompa con tickers
    sin datos de muestra. Parámetros plausibles por hash del ticker."""
    seed = abs(hash(sym)) % (2**32)
    rng = np.random.default_rng(seed)
    n = TRADING_DAYS_PER_YEAR * max(window_years, 1)
    mu = 0.0003 + (seed % 5) * 0.00005      # drift diario plausible
    sigma = 0.009 + (seed % 7) * 0.001       # vol diaria plausible
    rets = rng.normal(mu, sigma, n)
    prices = 100.0 * np.cumprod(1.0 + rets)
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    return pd.Series(prices, index=idx, name=sym)


@_cache
def get_price_history(tickers: tuple[str, ...], window_years: int = 10) -> tuple[pd.DataFrame, bool]:
    """Devuelve (precios_close, is_sample). Cacheado 1h. Cae a muestra si yfinance falla."""
    try:
        return _download_prices_live(tickers, window_years), False
    except Exception:
        return _load_sample_prices(tickers, window_years), True


# ── Sincronía entre bolsas (sesgo de cierres a distinta hora) ────────────────
# Ámsterdam cierra a las 11:30 de Nueva York y Tokio cierra antes de que Wall Street
# abra. Comparar cierres del MISMO día compara momentos distintos, y eso empuja las
# correlaciones hacia cero: la app creería que el inversor diversifica cuando repite
# la misma apuesta (IWDA vs SPY medía 0,48 cuando la real es 0,83). El remedio es
# medir la correlación en ventanas SEMANALES, donde el desfase de horas se diluye.
#
# Solo afecta a las correlaciones: las volatilidades y las medias individuales salen
# iguales en diario y en semanal (comprobado), así que esas se conservan tal cual.
MIN_WEEKLY_OBS = 60  # por debajo de esto la estimación semanal es demasiado ruidosa

_SUFFIX_REGION = {
    # Europa, Oriente Medio y África
    "L": "EMEA", "AS": "EMEA", "DE": "EMEA", "F": "EMEA", "MI": "EMEA", "MC": "EMEA",
    "PA": "EMEA", "SW": "EMEA", "BR": "EMEA", "LS": "EMEA", "VI": "EMEA", "ST": "EMEA",
    "OL": "EMEA", "CO": "EMEA", "HE": "EMEA", "IR": "EMEA", "WA": "EMEA", "AT": "EMEA",
    "IS": "EMEA", "JO": "EMEA", "TA": "EMEA", "SG": "EMEA", "MU": "EMEA", "DU": "EMEA",
    "HM": "EMEA", "BE": "EMEA", "XD": "EMEA", "XC": "EMEA", "PR": "EMEA", "BD": "EMEA",
    # Asia-Pacífico
    "T": "APAC", "HK": "APAC", "SS": "APAC", "SZ": "APAC", "TW": "APAC", "TWO": "APAC",
    "KS": "APAC", "KQ": "APAC", "AX": "APAC", "NZ": "APAC", "SI": "APAC", "KL": "APAC",
    "BK": "APAC", "JK": "APAC", "NS": "APAC", "BO": "APAC", "VN": "APAC",
    # América (sesión solapada con la de EE.UU.)
    "SA": "AMER", "MX": "AMER", "TO": "AMER", "V": "AMER", "NE": "AMER", "CN": "AMER",
    "BA": "AMER", "SN": "AMER", "LM": "AMER",
}

_CURRENCY_REGION = {
    "EUR": "EMEA", "GBP": "EMEA", "CHF": "EMEA", "SEK": "EMEA", "NOK": "EMEA",
    "DKK": "EMEA", "PLN": "EMEA", "ZAR": "EMEA", "TRY": "EMEA", "ILS": "EMEA",
    "HUF": "EMEA", "CZK": "EMEA", "RON": "EMEA",
    "JPY": "APAC", "HKD": "APAC", "CNY": "APAC", "TWD": "APAC", "KRW": "APAC",
    "AUD": "APAC", "NZD": "APAC", "SGD": "APAC", "INR": "APAC", "THB": "APAC",
    "IDR": "APAC", "MYR": "APAC", "PHP": "APAC",
}


def _region_of(symbol: str) -> str:
    """Huso de negociación del activo: AMER / EMEA / APAC. Sin llamadas de red.

    Las criptos cuentan como AMER a propósito: se midió que su desfase (cierre a
    medianoche UTC) va en dirección CONTRARIA al sesgo, así que no hay que corregirlas
    y las carteras con Bitcoin siguen dando exactamente lo mismo que antes.
    """
    s = str(symbol).upper().strip()
    try:
        from data import tickers as tdir

        df = tdir.load_directory()
        if bool((df["_sym_l"] == s.lower()).any()):
            return "AMER"  # NYSE/NASDAQ/Arca
    except Exception:
        pass
    if "." in s:
        suf = s.rsplit(".", 1)[-1]
        if suf in _SUFFIX_REGION:
            return _SUFFIX_REGION[suf]
    if s.endswith("-USD") or s.endswith("=X"):
        return "AMER"  # cripto y divisas: ver docstring
    try:
        cur = _split_currency(get_currency(s))[0]
        return _CURRENCY_REGION.get(cur, "AMER")
    except Exception:
        return "AMER"


def _needs_sync_fix(symbols) -> bool:
    """True si la cartera mezcla husos de negociación (único caso con sesgo)."""
    try:
        return len({_region_of(s) for s in symbols}) > 1
    except Exception:
        return False


def _weekly_returns(prices: pd.DataFrame) -> pd.DataFrame | None:
    """Retornos viernes-a-viernes, o None si no hay observaciones suficientes."""
    try:
        wk = prices.resample("W-FRI").last().pct_change().dropna()
        return wk if len(wk) >= MIN_WEEKLY_OBS else None
    except Exception:
        return None


def get_returns_frame(tickers: list[str], window_years: int = 10) -> tuple["pd.DataFrame", bool]:
    """DataFrame de retornos alineados + flag is_sample (para regresiones de beta).

    Si la cartera cruza husos de negociación devuelve retornos SEMANALES: la beta es
    un cociente cov/var, independiente de la frecuencia, así que queda corregida sin
    tocar `core/stress.py` (la beta de Toyota pasaba de 0,16 a 0,53, su valor real).
    """
    tkrs = tuple(sanitize_ticker(t) for t in tickers if sanitize_ticker(t))
    prices, is_sample = get_price_history(tkrs, window_years)
    if _needs_sync_fix(prices.columns):
        wk = _weekly_returns(prices)
        if wk is not None:
            return wk, is_sample
    return prices.pct_change().dropna(), is_sample


# ── Retorno esperado por CAPM (riesgo → retorno) ─────────────────────────────
# El retorno MEDIO histórico predice muy mal el futuro: proyectarlo tal cual hacía
# que NVDA (54,3% anual la última década) convirtiera $20.000 en $116 millones a 20
# años, y que cualquier cartera con el ganador reciente arrasara en la comparación.
# La volatilidad y las correlaciones sí son persistentes, así que esas se conservan
# del historial y solo se sustituye la ESPERANZA de retorno:
#
#     μ_activo = tasa_libre_de_riesgo + beta × prima_de_mercado
#
# La prima sale del propio mercado en la misma ventana, así que el mercado (beta 1)
# conserva exactamente su retorno histórico y solo se disciplina lo que se desvía de
# él. Es el estándar de la industria y usa la beta que ya calculamos.
MARKET_PROXY = "SPY"
RISK_FREE_FALLBACK = 0.04  # si no se puede leer la letra del Tesoro a 13 semanas


def _risk_free_annual() -> float:
    """Tasa libre de riesgo anual (letra del Tesoro a 13 semanas, ^IRX)."""
    try:
        import yfinance as yf

        h = yf.download("^IRX", period="1mo", progress=False, auto_adjust=True)["Close"].dropna()
        v = float(h.iloc[-1].iloc[0] if hasattr(h.iloc[-1], "iloc") else h.iloc[-1]) / 100.0
        return v if 0.0 <= v <= 0.20 else RISK_FREE_FALLBACK
    except Exception:
        return RISK_FREE_FALLBACK


def get_risk_free_annual() -> float:
    try:
        import streamlit as st

        return st.cache_data(ttl=86400, show_spinner=False)(_risk_free_annual)()
    except Exception:
        return _risk_free_annual()


def _capm_mean_daily(prices: pd.DataFrame, returns: pd.DataFrame, window_years: int):
    """Media diaria esperada por CAPM para cada columna. None si no se puede estimar.

    Las betas se miden en la MISMA frecuencia que las correlaciones: si la cartera
    cruza husos de negociación se usan retornos semanales, porque la beta diaria de
    un activo asiático o europeo sale sesgada hacia cero (Toyota: 0,16 frente a 0,53).
    """
    try:
        cols = list(prices.columns)
        mkt_px, mkt_sample = get_price_history((MARKET_PROXY,), window_years)
        if mkt_sample or mkt_px.empty:
            return None
        weekly = _needs_sync_fix(cols) and _weekly_returns(prices) is not None
        if weekly:
            pr = prices.resample("W-FRI").last()
            mk = mkt_px[MARKET_PROXY].reindex(pr.index).ffill().bfill()
            r_a, r_m = pr.pct_change().dropna(), mk.pct_change().dropna()
            per_year = 52.0
        else:
            mk = mkt_px[MARKET_PROXY].reindex(prices.index).ffill().bfill()
            r_a, r_m = returns, mk.pct_change().dropna()
            per_year = float(TRADING_DAYS_PER_YEAR)
        idx = r_a.index.intersection(r_m.index)
        r_a, r_m = r_a.loc[idx], r_m.loc[idx]
        if len(idx) < 30:
            return None
        var_m = float(np.var(r_m.to_numpy(), ddof=1))
        if var_m <= 0:
            return None
        # La PRIMA se mide sobre la ventana COMPLETA de SPY, nunca sobre el tramo
        # común de la cartera: un activo recién listado (IBIT, enero 2024) recortaba
        # el historial de TODA la cartera al último bull run y "el mercado" pasaba a
        # rendir 23,8% anual — con betas >1 eso proyectaba SOXX al 44% y AMD al 50%.
        # Además va acotada a [3%, 8%], la banda de consenso de la prima de riesgo de
        # EE.UU.: una década excepcional (buena o mala) no debe volverse "la expectativa".
        rf = get_risk_free_annual()
        full = mkt_px[MARKET_PROXY].dropna()
        yrs = max((full.index[-1] - full.index[0]).days / 365.25, 1.0)
        mkt_cagr = (float(full.iloc[-1]) / float(full.iloc[0])) ** (1.0 / yrs) - 1.0
        premium = float(np.clip(mkt_cagr - rf, 0.03, 0.08))
        out = []
        for c in cols:
            beta = float(np.cov(r_a[c].to_numpy(), r_m.to_numpy())[0, 1] / var_m)
            ann = rf + beta * premium
            ann = float(np.clip(ann, -0.50, 5.0))  # cordura ante datos degenerados
            out.append((1.0 + ann) ** (1.0 / TRADING_DAYS_PER_YEAR) - 1.0)
        arr = np.asarray(out, dtype=np.float64)
        return arr if np.all(np.isfinite(arr)) else None
    except Exception:
        return None


def get_market_stats(tickers: list[str], window_years: int = 10) -> dict:
    """μ (media diaria), Σ (covarianza diaria) y orden de tickers para el motor.

    Returns dict: {mean_daily, cov_daily, tickers, is_sample, n_days}.
    """
    tkrs = tuple(sanitize_ticker(t) for t in tickers if sanitize_ticker(t))
    prices, is_sample = get_price_history(tkrs, window_years)
    returns = prices.pct_change().dropna()
    cov = returns.cov().to_numpy()
    # Solo si la cartera cruza husos: Σ = D·C_semanal·D. Se conservan las volatilidades
    # diarias (insesgadas) y se sustituye la estructura de correlación, que es lo único
    # que el desfase de horarios distorsiona. Una cartera de EE.UU. no entra aquí.
    if _needs_sync_fix(prices.columns):
        wk = _weekly_returns(prices)
        if wk is not None:
            try:
                corr_w = wk[list(prices.columns)].corr().to_numpy()
                d = np.sqrt(np.diag(cov))
                fixed = np.outer(d, d) * corr_w
                if np.all(np.isfinite(fixed)):
                    cov = fixed
            except Exception:
                pass  # ante cualquier problema se mantiene la Σ diaria de siempre
    # Retorno esperado por CAPM. Si no se puede estimar (sin red, datos de muestra,
    # histórico insuficiente) se conserva la media histórica de siempre.
    mean_daily = returns.mean().to_numpy()
    expected_from = "historico"
    if not is_sample:
        capm = _capm_mean_daily(prices, returns, window_years)
        if capm is not None and len(capm) == len(mean_daily):
            mean_daily, expected_from = capm, "capm"
    return {
        "tickers": list(prices.columns),
        "mean_daily": mean_daily,
        "cov_daily": cov,
        "is_sample": is_sample,
        "n_days": int(len(returns)),
        "expected_from": expected_from,
    }
