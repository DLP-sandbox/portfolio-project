# assets/

Recursos visuales de la app.

## `club_dlp_logo.png` (lo dejás vos)

Logo de Club DLP que se muestra arriba del sidebar y, en Fase 3, en la página CTA del PDF
lead magnet (con rounded corners + glow halo + sombra procesados con PIL).

- Formato: PNG con fondo transparente.
- Tamaño sugerido: ≥ 512×512 px (cuadrado o apaisado funciona).
- La app degrada con elegancia si el archivo no existe (muestra "DLP" como texto).

## `fonts/` (opcional)

Fallback de tipografía para el PDF si Helvetica Neue no estuviera disponible en el sistema.
Dejá `Inter-Regular.ttf` (y variantes Bold/Medium) acá. En macOS la app usa Helvetica Neue
nativa desde `/System/Library/Fonts/HelveticaNeue.ttc`, así que esto es solo un seguro.
