"""Importador de portafolios candidatos desde CSV (formato DLP multi-portafolio).

Formato esperado (una fila por activo, agrupado por el nombre del portafolio):

    Portafolio, Ticker, Nombre, Clase, Peso(%)
    Crecimiento Máximo, QQQ, Invesco NASDAQ-100, ETF tech, 25
    ...

El parser es TOLERANTE a propósito: acepta BOM, variantes de nombres de columna
(español/inglés), delimitador coma/;/tab, filas incompletas y pesos con '%' o coma
decimal. Es numpy/pandas-free y sin dependencias de Streamlit → fácil de testear y
no agrega peso de memoria a la app.
"""
from __future__ import annotations

import csv
import io

from data.market_data import sanitize_ticker

# Alias de columnas aceptados (normalizados: minúscula, sin espacios) → campo canónico
_PORT_KEYS = {"portafolio", "portfolio", "cartera", "grupo"}
_TICK_KEYS = {"ticker", "símbolo", "simbolo", "symbol"}
_NAME_KEYS = {"nombre", "name", "descripción", "descripcion"}
_WEIGHT_KEYS = {"peso(%)", "peso", "peso%", "weight", "weight(%)",
                "ponderación", "ponderacion", "%"}

# Tope defensivo: nunca importamos más de esto (evita CSV enormes accidentales).
MAX_PORTFOLIOS = 6
MAX_ASSETS_PER_PORTFOLIO = 20


def _norm(s: str) -> str:
    """Normaliza un encabezado: quita BOM, espacios y pasa a minúscula."""
    return (s or "").strip().lstrip("﻿").lower().replace(" ", "")


def _parse_weight(raw: str) -> float:
    """Convierte '25', '25%', '12,5' → float. Devuelve 0.0 si no se puede."""
    if raw is None:
        return 0.0
    s = str(raw).strip().replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _find_col(header: list[str], keys: set[str]) -> int | None:
    for i, h in enumerate(header):
        if h in keys:
            return i
    return None


def parse_portfolios_csv(text: str) -> list[dict]:
    """Parsea el CSV y devuelve una lista ordenada de portafolios candidatos:

        [{"name": str, "items": [{"symbol", "name", "weight"}, ...]}, ...]

    - Agrupa por el nombre del portafolio, preservando el orden de aparición.
    - Ignora filas sin ticker o sin nombre de portafolio.
    - Suma pesos si un mismo ticker aparece repetido en el mismo portafolio.
    - NO normaliza pesos (de eso se encarga la app al simular).

    Lanza ValueError con mensaje claro si el archivo no tiene el formato mínimo.
    """
    if not text or not text.strip():
        raise ValueError("El archivo está vacío.")

    # Detectar delimitador (coma, punto y coma o tab) de forma robusta.
    try:
        delimiter = csv.Sniffer().sniff(text[:2048], delimiters=",;\t").delimiter
    except Exception:
        delimiter = ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("El CSV no tiene filas de datos (solo encabezado o vacío).")

    header = [_norm(c) for c in rows[0]]
    i_port = _find_col(header, _PORT_KEYS)
    i_tick = _find_col(header, _TICK_KEYS)
    i_name = _find_col(header, _NAME_KEYS)
    i_weight = _find_col(header, _WEIGHT_KEYS)
    if i_port is None or i_tick is None:
        raise ValueError(
            "El CSV debe incluir al menos una columna de portafolio y otra de ticker "
            "(por ejemplo 'Portafolio' y 'Ticker').")

    grouped: dict[str, dict] = {}
    order: list[str] = []
    for r in rows[1:]:
        if len(r) <= max(i_port, i_tick):
            continue
        pname = (r[i_port] or "").strip()
        symbol = sanitize_ticker(r[i_tick])
        if not pname or not symbol:
            continue
        name = ""
        if i_name is not None and i_name < len(r):
            name = (r[i_name] or "").strip()
        name = name or symbol
        weight = _parse_weight(r[i_weight]) if (i_weight is not None and i_weight < len(r)) else 0.0

        if pname not in grouped:
            if len(order) >= MAX_PORTFOLIOS:
                continue  # ignora portafolios extra más allá del tope
            grouped[pname] = {"name": pname, "items": []}
            order.append(pname)
        items = grouped[pname]["items"]
        existing = next((it for it in items if it["symbol"] == symbol), None)
        if existing:
            existing["weight"] += weight
        elif len(items) < MAX_ASSETS_PER_PORTFOLIO:
            items.append({"symbol": symbol, "name": name, "weight": weight})

    result = [grouped[p] for p in order if grouped[p]["items"]]
    if not result:
        raise ValueError("No se encontraron portafolios con activos válidos en el CSV.")
    return result
