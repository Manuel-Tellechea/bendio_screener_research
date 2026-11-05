# Bendio Screener Research

MVP de investigación para un universo configurable de acciones suizas. Descarga fundamentales y precios diarios ajustados de Yahoo Finance mediante `yfinance`, calcula tres puntuaciones y exporta un Excel auditable. No incluye datos inventados ni recomendaciones de compra.

## Instalación y ejecución

Requiere Python 3.10+ y acceso a Internet para descargar datos.

```bash
cd bendio-screener-research
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m bendio_screener.cli --universe universe.txt --output output/bendio_screener.xlsx
```

En Windows, activa el entorno con `.venv\Scripts\activate`. Para ejecutar las pruebas sin Internet ni dependencias externas:

```bash
python -m unittest discover -s tests -v
```

El archivo `universe.txt` contiene 23 símbolos iniciales, pero puedes añadir o sustituir títulos sin límite fijo: uno por línea, con o sin `.SW`. El libro contiene `Ranking` (todos los símbolos solicitados, incluidos fallos), `Top 10` (hasta diez elegibles) y `Methodology`. Se rechazan universos vacíos, símbolos inválidos o duplicados. Cada símbolo se consulta como `TICKER.SW`.

## Puntuación

Cada métrica se transforma linealmente a 0–100 dentro de los límites de `Methodology` y se recorta en los extremos. Se promedian las métricas disponibles dentro de cada pilar. La puntuación total es **40% Fundamental + 35% Factor + 25% Technical**; los tres pilares deben tener al menos una métrica válida. No se imputan faltantes. El Excel muestra cobertura e incidencias por título.

- **Fundamental:** ROE, crecimiento de beneficios, crecimiento de ingresos, margen operativo y deuda/capital. Para financieras (UBSG, ZURN, SREN, SLHN o sector `Financial Services` según Yahoo), se usa margen neto en lugar de margen operativo y se omite deuda/capital.
- **Factor:** P/E futuro, precio/valor en libros, rentabilidad por dividendo y EV/EBITDA. Se omite EV/EBITDA para financieras. Los múltiplos de valoración deben ser positivos.
- **Technical:** retorno de 126 sesiones y distancia respecto a la media simple de 200 sesiones, usando cierres ajustados. Se exigen 200 precios positivos y último precio de no más de 10 días.

Los límites exactos están en la hoja `Methodology` y en `bendio_screener/core.py`. Son reglas heurísticas transparentes, no parámetros optimizados ni percentiles sectoriales. Las empresas financieras y no financieras comparten escala final, pero sus métricas elegibles difieren.

## Limitaciones

Los campos de Yahoo pueden faltar, cambiar, estar desactualizados o ser inconsistentes entre empresas; se registran los errores y la cobertura. El sufijo `.SW` se aplica a los símbolos del universo elegido; la disponibilidad efectiva depende de Yahoo. Los fundamentales disponibles son actuales, sin histórico point-in-time, por lo que el resultado no sirve para backtests sin sesgo temporal. Se consulta cada título secuencialmente y no hay caché. La divisa y diferencias contables pueden afectar comparaciones. El `Top 10` puede tener menos de diez empresas si faltan datos.

Fuente de API: [documentación de yfinance](https://ranaroussi.github.io/yfinance/reference/yfinance.ticker_tickers.html). Revisa los términos de uso de Yahoo Finance antes de distribuir datos descargados.
