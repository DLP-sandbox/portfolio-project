"""Calificación de métricas → termómetro rojo→verde + palabra (Malo…Excelente).

Cada indicador de la app se traduce, con criterio de analista, a una posición 0-1 en una
escala roja→ámbar→verde y una palabra de una sola línea. `pos=0` es lo peor (rojo) y `pos=1`
lo mejor (verde); la dirección (más es mejor / menos es mejor) ya está incorporada por métrica.
Numpy/Streamlit-free y determinista.
"""
from __future__ import annotations

# Escala de color: rojo (#FF3B5C) → ámbar (#FFB84D) → verde (#00FF88)
_STOPS = [(0.0, (255, 59, 92)), (0.5, (255, 184, 77)), (1.0, (0, 255, 136))]

# Bandas de palabra (umbral superior → palabra). Escala universal de calidad.
_BANDS = [(0.22, "Malo"), (0.42, "Regular"), (0.62, "Bueno"), (0.82, "Muy bueno"), (1.01, "Excelente")]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def color_for_pos(pos: float) -> str:
    """Interpola el color de la escala roja→ámbar→verde en la posición `pos` (0-1)."""
    pos = _clamp(pos)
    for (p0, c0), (p1, c1) in zip(_STOPS, _STOPS[1:]):
        if pos <= p1:
            t = 0.0 if p1 == p0 else (pos - p0) / (p1 - p0)
            r = round(c0[0] + (c1[0] - c0[0]) * t)
            g = round(c0[1] + (c1[1] - c0[1]) * t)
            b = round(c0[2] + (c1[2] - c0[2]) * t)
            return f"#{r:02X}{g:02X}{b:02X}"
    return "#00FF88"


def word_for_pos(pos: float) -> str:
    pos = _clamp(pos)
    for thr, w in _BANDS:
        if pos < thr:
            return w
    return "Excelente"


def _pos(key: str, v: float) -> float:
    """Posición 0-1 (0=peor/rojo, 1=mejor/verde) por métrica, con umbrales de analista."""
    if key == "sharpe":         # eficiencia: >1 bueno, >2 excelente
        return _clamp(v / 2.0)
    if key == "drawdown":       # caída típica (frac): menos es mejor
        return _clamp(1.0 - v / 0.50)
    if key == "volatility":     # volatilidad anual (frac): menos es mejor
        return _clamp(1.0 - v / 0.40)
    if key == "prob_loss":      # prob. de pérdida (0-1): menos es mejor
        return _clamp(1.0 - v / 0.50)
    if key == "concentration":  # peso máx (0-1): menos es mejor
        return _clamp(1.0 - (v - 0.10) / 0.50)
    if key == "correlation":    # correlación media: menos es mejor (más diversificación)
        return _clamp(1.0 - (v - 0.10) / 0.70)
    if key in ("prob_meta", "prob_beat"):   # probabilidades a favor: más es mejor
        return _clamp(v)
    if key == "ruin":           # prob. de ruina: menos es mejor
        return _clamp(1.0 - v / 0.30)
    if key == "return":         # retorno anual esperado: más es mejor
        return _clamp(v / 0.15)
    if key == "eff_bets":       # apuestas independientes: más es mejor
        return _clamp((v - 1.0) / 6.0)
    return 0.5


def rate(key: str, value: float) -> dict:
    """Calificación estándar de una métrica → {pos, color, word}."""
    pos = _pos(key, float(value))
    return {"pos": pos, "color": color_for_pos(pos), "word": word_for_pos(pos)}


def rating(pos: float, word: str | None = None) -> dict:
    """Calificación explícita por posición (para montos/escenarios con criterio propio)."""
    pos = _clamp(pos)
    return {"pos": pos, "color": color_for_pos(pos), "word": word or word_for_pos(pos)}
