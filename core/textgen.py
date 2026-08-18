"""Motor de redacción por REGLAS — sin ninguna API de IA.

Portado del enfoque que ya usa DLP Analyzer en su versión sin IA
(`agents/code_engine.py`, `agents/etf_engine.py`): el juicio lo calcula Python y la prosa
se arma combinando variantes deterministas. El resultado se lee como un analista, no como
una plantilla, y es reproducible: el mismo portafolio produce SIEMPRE el mismo texto.

Tres piezas:
  * `seeded` / `compose`  — el compositor de pools (apertura / cuerpo / cierre).
  * `variant`             — variantes con índice DESPLAZADO por hueco, para que las
                            elecciones de distintos huecos no se sincronicen.
  * naturalizadores       — quitan los símbolos de máquina (`~`, `±`, `/mes`) y la jerga
                            inglesa, que es lo que delata que un texto es automático.
"""
from __future__ import annotations

import hashlib
import random as _rnd
import re

# ═════════════════════════════════════════════════════════════════════════════
# Semilla y composición
# ═════════════════════════════════════════════════════════════════════════════

def seed_key(inputs_or_key) -> str:
    """Clave estable de un portafolio + su plan.

    Frente a la versión anterior (solo `tickers|weights|horizon`) añadimos capital, aporte
    y meta: dos escenarios distintos del mismo portafolio ya no se leen idénticos. Sigue
    siendo determinista — al refrescar, el informe dice exactamente lo mismo.
    """
    if not isinstance(inputs_or_key, dict):
        return str(inputs_or_key)
    d = inputs_or_key
    return "|".join(str(d.get(k)) for k in (
        "tickers", "weights", "horizon_years", "initial_capital",
        "monthly_contribution", "target"))


def seeded(inputs_or_key, salt: str):
    """RNG sembrado por el contenido: estable entre reruns, distinto entre portafolios."""
    return _rnd.Random(f"{seed_key(inputs_or_key)}|{salt}")


def compose(rng, *pools) -> str:
    """Une una elección de cada pool. Los pools vacíos se descartan."""
    return " ".join(rng.choice(p) for p in pools if p)


def variant(seed, idx: int, *opciones: str) -> str:
    """Elige una variante de forma determinista para el hueco `idx`.

    OJO con la aritmética: un `(suma_de_caracteres + idx) % n` — que es lo que hace el
    motor del Analyzer — decide TODOS los huecos con el mismo número base. Dos carteras
    cuyas sumas sean congruentes módulo n eligen entonces la misma variante en cada hueco y
    sus textos salen calcados. Aquí se usa un hash independiente por (semilla, hueco), así
    que los huecos son de verdad independientes y no hay familias de carteras gemelas.
    """
    if not opciones:
        return ""
    key = seed if isinstance(seed, str) else (str(seed) if isinstance(seed, int) else seed_key(seed))
    h = hashlib.md5(f"{key}|{idx}".encode("utf-8")).digest()
    return opciones[int.from_bytes(h[:4], "big") % len(opciones)]


# ═════════════════════════════════════════════════════════════════════════════
# Naturalizadores: fuera los símbolos de máquina
# ═════════════════════════════════════════════════════════════════════════════
# El guion largo «—» NO está aquí a propósito: es la voz de la casa (dato — lectura),
# igual que en DLP Analyzer. Lo que se elimina son los símbolos de teclado técnico.

_APROX = ("cerca de", "alrededor de", "en torno a", "algo así como")


def approx(rng_or_idx, texto: str) -> str:
    """«~25%» → «alrededor de un 25%», variando la fórmula para que no cante."""
    if isinstance(rng_or_idx, int):
        pre = _APROX[rng_or_idx % len(_APROX)]
    else:
        pre = rng_or_idx.choice(_APROX)
    # Los porcentajes piden artículo en español: «alrededor de UN 25%», no «de 25%».
    art = "un " if re.match(r"^-?[\d.,]+%$", texto.strip()) else ""
    return f"{pre} {art}{texto}"


def plusminus(texto: str) -> str:
    """«±18%» → «que sube y baja alrededor de un 18%»."""
    return f"que sube y baja alrededor de un {texto}"


def per_month(texto: str) -> str:
    """«$3,000/mes» → «$3,000 al mes»."""
    return f"{texto} al mes"


def rango(a: str, b: str) -> str:
    """«$120,000–$980,000» → «entre $120,000 y $980,000»."""
    return f"entre {a} y {b}"


def natural_join(items: list[str]) -> str:
    """«A, B, C» → «A, B y C». Sin el «y» final la enumeración suena a máquina."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " y " + items[-1]


def plural(n: int, singular: str, plural_: str) -> str:
    """Concordancia: «1 activo» / «3 activos»."""
    return singular if abs(n) == 1 else plural_


# ═════════════════════════════════════════════════════════════════════════════
# Higiene del texto: símbolos de máquina y detección de jerga
# ═════════════════════════════════════════════════════════════════════════════
# La jerga NO se reescribe en caliente: sustituir «trade-off» por «hay que elegir» dentro
# de una frase ya escrita produce engendros («es un hay que elegir entre...»). Los textos
# se escriben bien de entrada y aquí solo se DETECTA, para que la verificación falle si
# alguien cuela un anglicismo nuevo.

JERGA: dict[str, str] = {
    "trade-off": "hay que elegir entre",
    "tradeoff": "hay que elegir entre",
    "drawdown": "caída desde máximos",
    "bullish": "alcista",
    "bearish": "bajista",
    "rally": "subida fuerte",
    "sell-off": "ola de ventas",
    "pullback": "retroceso",
    "momentum": "la inercia del precio",
    "timing": "el momento de entrada",
    "asset allocation": "reparto entre activos",
    "stock picking": "selección de acciones",
    "benchmark": "índice de referencia",
    "performance": "rendimiento",
    "headwind": "viento en contra",
    "tailwind": "viento a favor",
    "compounding": "interés compuesto",
    "buy and hold": "comprar y mantener",
    "hedge": "cobertura",
}

_JERGA_RE = [(k, re.compile(rf"\b{re.escape(k)}\b", re.IGNORECASE)) for k in JERGA]

# Símbolos que delatan que el texto salió de una plantilla. El guion largo «—» NO está
# aquí: es la voz de la casa (dato — lectura), igual que en DLP Analyzer.
# Símbolos que delatan que el texto salió de una plantilla. El guion largo «—» NO está
# aquí: es la voz de la casa (dato — lectura), igual que en DLP Analyzer.
SIMBOLOS_MAQUINA = ("~", "±", "…", "\\$", "/mes")


def find_jargon(texto: str) -> list[str]:
    """Anglicismos presentes en el texto (vacío si está limpio). Para la verificación."""
    return [k for k, rx in _JERGA_RE if rx.search(texto or "")]


def find_symbols(texto: str, html: bool = False) -> list[str]:
    """Símbolos de máquina presentes en el texto (vacío si está limpio).

    `html=True` para textos que se inyectan en HTML crudo (las tarjetas de hallazgo): ahí
    los asteriscos de markdown se verían literales, así que también son un fallo.
    """
    t = texto or ""
    found = [s for s in SIMBOLOS_MAQUINA if s in t]
    if re.search(r"\d\s*–\s*[\d$]", t):      # rango con guion corto: 10–20
        found.append("–")
    if html and ("**" in t or re.search(r"(?<!\*)\*(?!\*)", t)):
        found.append("* (markdown en HTML)")
    return found


def es_natural(texto: str) -> str:
    """Limpieza final de símbolos de máquina (no toca la jerga: eso se detecta, no se
    reescribe). Se aplica a la salida de los generadores como última red."""
    if not texto:
        return texto
    texto = texto.replace("…", "...")
    texto = re.sub(r"(?<=\d)\s*–\s*(?=[\d$])", " a ", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto)
    return texto
