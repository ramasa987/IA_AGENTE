# =============================================================
# ALERTAS.PY — Reglas de compra/venta y ranking de señales
# =============================================================
# Qué hay aquí:
#   - limpiar_unicode(): elimina caracteres invisibles del LLM
#   - limpiar_texto(): convierte texto a latin-1 para el PDF
#   - generar_alerta(): aplica reglas técnicas a los datos del caché
#   - seleccionar_mejores_alertas(): elige las N mejores señales
#
# Dependencia: lee _cache_analisis y escribe en _cache_alertas (datos.py)
# =============================================================

from datos import _cache_analisis, _cache_alertas


def limpiar_unicode(texto: str) -> str:
    """Elimina espacios de ancho cero y caracteres invisibles que inyecta el LLM."""
    INVISIBLES = {'​', '‌', '‍', '‎', '‏',
                  '⁠', '⁡', '⁢', '⁣', '﻿'}
    texto = ''.join(c for c in texto if c not in INVISIBLES)
    texto = texto.replace('—', '-').replace('–', '-').replace('‒', '-')
    return texto.strip()


def limpiar_texto(texto: str) -> str:
    """Convierte el texto a latin-1 para compatibilidad con la fuente Helvetica de fpdf2."""
    texto = texto.replace('—', '-').replace('–', '-').replace('→', '->').replace('…', '...')
    return texto.encode('latin-1', errors='ignore').decode('latin-1')


def generar_alerta(ticker: str) -> dict:
    """
    Aplica las reglas de compra/venta usando los datos del análisis previo.
    Solo necesita el ticker — recupera precio, RSI y medias del caché interno.
    Esto evita que el LLM tenga que generar 7 parámetros (causa del error 400).
    """
    datos = _cache_analisis.get(ticker.upper())
    if not datos:
        return {'error': f'No hay datos analizados para {ticker}. '
                         f'Llama primero a analizar_accion_yfinance({ticker}).'}

    precio        = datos['precio_actual']
    rsi           = datos['rsi']
    ma50          = datos['ma50']
    ma200         = datos['ma200']
    variacion_pct = datos['variacion_pct']
    max_52w       = datos['max_52w']

    compra = []
    venta  = []
    caida  = round((precio - max_52w) / max_52w * 100, 1)

    # ── Reglas de COMPRA ─────────────────────────────────────
    if rsi < 40:
        compra.append(f'RSI={rsi} < 40 (sobrevendida)')
    if precio < ma50 and ma50 > ma200:
        compra.append('Precio bajo MA50 con tendencia alcista (MA50 > MA200)')
    if variacion_pct > 2:
        compra.append(f'Subida diaria +{variacion_pct}%')

    # ── Reglas de VENTA ──────────────────────────────────────
    if rsi > 70:
        venta.append(f'RSI={rsi} > 70 (sobrecomprada)')
    if caida < -8:
        venta.append(f'Caida {caida}% desde maximo anual')
    if ma50 < ma200:
        venta.append(f'Death Cross: MA50={ma50} < MA200={ma200}')
    if variacion_pct < -3:
        venta.append(f'Caida diaria {variacion_pct}%')

    # ── Decisión final ───────────────────────────────────────
    if len(compra) >= 2:
        senal, motivo = 'COMPRAR', ' | '.join(compra)
    elif len(venta) >= 2:
        senal, motivo = 'VENDER', ' | '.join(venta)
    else:
        senal  = 'MANTENER'
        motivo = 'Sin senal tecnica suficiente'

    resultado = {
        'ticker': ticker, 'senal': senal, 'motivo': motivo,
        'precio': precio, 'rsi': rsi,
        'reglas_compra': compra, 'reglas_venta': venta
    }
    _cache_alertas[ticker.upper()] = resultado
    return resultado


def seleccionar_mejores_alertas(n: int) -> dict:
    """
    Ordena todas las alertas generadas y conserva solo las N mejores en el caché.
    Criterio de ranking: COMPRAR > MANTENER > VENDER,
    luego más reglas activas, luego RSI más bajo (más oportunidad de rebote).
    """
    if not _cache_alertas:
        return {'error': 'No hay alertas. Llama antes a generar_alerta.'}

    n = max(1, min(5, int(n)))

    def puntuacion(item):
        _, alerta = item
        senal    = alerta.get('senal', 'MANTENER')
        n_compra = len(alerta.get('reglas_compra', []))
        rsi      = alerta.get('rsi', 50)
        if senal == 'COMPRAR':    return (2, n_compra, -rsi)
        elif senal == 'MANTENER': return (1, 0, 0)
        return (0, 0, 0)

    ordenadas     = sorted(_cache_alertas.items(), key=puntuacion, reverse=True)
    seleccionadas = [t for t, _ in ordenadas[:n]]
    descartadas   = [t for t, _ in ordenadas[n:]]

    # Limpiar del caché las alertas descartadas
    for t in descartadas:
        _cache_alertas.pop(t, None)
        _cache_analisis.pop(t, None)

    return {'seleccionadas': seleccionadas, 'descartadas': descartadas, 'n_pedidas': n}
