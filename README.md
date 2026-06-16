# DLP Backtester & Planner

> **Visualiza los 10.000 futuros posibles de tu portafolio.**

App privada de **proyección probabilística** de portafolios de inversión a largo plazo,
para el ecosistema Diario Largo Plazo (DLP) / Club DLP. Corre simulaciones Montecarlo
del patrimonio futuro a partir de retornos históricos y muestra el rango estadístico de
escenarios — **no** una predicción ni una recomendación de inversión.

> ⚠️ Esta simulación NO es predicción ni recomendación de inversión. Proyecta escenarios
> estadísticos basados en retornos históricos. El comportamiento real del mercado puede
> diferir significativamente. Consulta a un asesor financiero antes de tomar decisiones.

---

## Stack

Python 3.11 (deploy) / 3.9+ (dev) · Streamlit · NumPy · SciPy · pandas · yfinance ·
Plotly · reportlab · kaleido. Ver [`requirements.txt`](requirements.txt).

## Estado del build

- **Fase 1 (MVP) — ✅:** password gate, formulario de inputs, motor Montecarlo
  vectorizado (n=10.000), fan chart con glow, 3 KPI tiles (P5/P50/P95), histograma del
  patrimonio final, persistencia local en `.history/`, disclaimer visible en cada vista.
- **Fase 2 (realista) — ✅:** distribución t-Student (colas gordas), portafolios predefinidas
  (S&P puro, 60/40, all-weather), comparación con benchmarks (overlay glow), gauge de
  probabilidad de meta, fees anuales + impuestos sobre ganancias, export PDF de 3 páginas
  (dashboard + análisis detallado + CTA), Sharpe esperado.
- **Fase 3 (premium) — ✅:** stress tests con eventos históricos (1929/1973/2000/2008/2020)
  escalados por beta, sequence-of-returns risk, modo retiro con probabilidad de ruina,
  portafolios favoritas (Supabase/local) + sidebar, PDF lead magnet con logo glow halo + QR
  clickeable, e **interpretación automática local (sin costo)**.

### Interpretación con IA — costo $0 por defecto

La interpretación de cada proyección es **local, basada en reglas, sin llamadas a la API**
(`core/interpret.interpret_locally`). Hay un modo opcional con Claude detrás de un toggle
apagado por defecto que solo corre si configuras `ANTHROPIC_API_KEY` y lo activas
explícitamente (con aviso de que consume créditos). Correr la app no gasta créditos.

> Nota de honestidad sobre t-Student: sobre horizontes largos con retornos i.i.d., las
> colas gordas afectan sobre todo los **drawdowns** y movimientos extremos de corto/mediano
> plazo; el efecto en el **patrimonio final** es modesto (convergencia tipo CLT). Los grandes
> riesgos de cola (crashes, secuencia de retornos) llegan con los stress tests de Fase 3.

## Arranque rápido (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Opcional: activar password gate
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
#   edita APP_PASSWORD en .streamlit/secrets.toml

python main.py            # o: streamlit run dashboard/app.py
```

Sin `APP_PASSWORD` configurado, la app corre en **modo dev** sin gate.

## Datos de mercado

La app baja precios en vivo de yfinance con caché de 1 hora. Si Yahoo falla o rate-limitea,
usa un **set de datos de muestra** empaquetado (`data/sample_data/`) y lo avisa en pantalla.
Los datos de muestra son ilustrativos y **no** son cotizaciones reales en vivo.

## Estructura

```
core/        motor Montecarlo + métricas estadísticas + presets
data/        wrapper yfinance (con fallback) + persistencia (Supabase/local)
dashboard/   app Streamlit, estilos, charts Plotly, componentes, PDF
assets/      logo Club DLP + fuentes opcionales
scripts/     utilidades (migración a Supabase)
```

## Nota local: kaleido + rutas con espacios

`kaleido==0.2.1` (export de imágenes para el PDF) tiene un launcher de shell que **falla
si la ruta del proyecto tiene espacios** (ej: `APP - PROYECCION PORTAFOLIO`). Esto **solo**
afecta el export server-side local (PDF Fase 2); la app en vivo y Streamlit Cloud
(`/mount/src/dlp-backtester`, sin espacios) no se ven afectados. Para export local: clona
el repo en una ruta sin espacios, o agrega comillas a la línea `cd "$DIR"` en
`.venv/.../kaleido/executable/kaleido`.

## Despliegue en Render.com

El repo incluye `render.yaml` (Blueprint) y `.python-version` (3.11.9). Pasos:

1. **Subí el repo a GitHub** (la carpeta `dlp-backtester/` debe ser la raíz del repo).
2. En **Render → New + → Blueprint**, conectá el repo. Render lee `render.yaml` solo.
   - O bien **New + → Web Service** (manual) con:
     - **Build:** `pip install -r requirements.txt`
     - **Start:** `streamlit run dashboard/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false`
     - **Env var:** `PYTHON_VERSION = 3.11.9`
     - **Health check path:** `/_stcore/health`
3. **Deploy.** Quedará en `https://<tu-app>.onrender.com`.

Notas:
- **No requiere secrets ni base de datos** (no guarda nada). La app corre abierta — ideal
  para un embed público. No configures `APP_PASSWORD` (un iframe pidiendo contraseña sería
  mala UX).
- **Plan free** se duerme tras 15 min de inactividad (cold start ~30-60s). Para un embed que
  cargue siempre rápido, usá el plan **Starter** (always-on) o mantené el free despierto con
  un pinger externo gratis (UptimeRobot / cron-job.org) apuntando a
  `https://<tu-app>.onrender.com/_stcore/health` cada ~10 min.
- Si el repo de GitHub tiene `dlp-backtester/` como subcarpeta (no como raíz), agregá
  `rootDir: dlp-backtester` en `render.yaml`.

## Embeber en una página (cuadrado 1:1)

La app está pensada para un contenedor 1:1. Usá `?embed=true` (oculta la barra de Streamlit):

```html
<!-- Cuadrado responsivo que escala con el ancho -->
<div style="position:relative;width:100%;max-width:800px;aspect-ratio:1/1;margin:0 auto;">
  <iframe src="https://TU-APP.onrender.com/?embed=true"
          style="position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:16px"
          loading="lazy" title="Proyección de Portafolio"></iframe>
</div>
```

O tamaño fijo: `<iframe src="https://TU-APP.onrender.com/?embed=true" width="800" height="800" style="border:0;border-radius:16px"></iframe>`.

El embed funciona porque `config.toml` tiene `enableCORS=false` y `enableXsrfProtection=false`
(también pasados en el Start command). Streamlit no bloquea iframes.
