"""CLI entry point: `python main.py` lanza la app Streamlit.

Uso:
    python main.py            # abre el dashboard en el navegador
    python main.py --help     # ayuda

Mantiene el comando simple para no memorizar la ruta del entry de Streamlit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

APP_ENTRY = Path(__file__).parent / "dashboard" / "app.py"


def main() -> int:
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    # Pasamos cualquier flag extra directo a streamlit (ej: --server.port 8502)
    extra_args = [a for a in sys.argv[1:] if a not in ("--help", "-h")]
    cmd = [sys.executable, "-m", "streamlit", "run", str(APP_ENTRY), *extra_args]
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
