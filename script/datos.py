# =============================================================
# DATOS.PY — Base de datos SP500 + Yahoo Finance + Caché
# =============================================================
# Qué hay aquí:
#   - SP500_POR_SECTOR: diccionario con las acciones por sector
#   - _cache_analisis / _cache_alertas: memoria temporal de la sesión
#   - obtener_perfil_inversor(): cuestionario al usuario
#   - buscar_acciones_por_perfil(): filtra acciones por sector y riesgo
#   - analizar_accion_yfinance(): descarga datos reales de Yahoo Finance
# =============================================================

import json
import datetime
import yfinance as yf


# ── Base de datos del S&P 500 por sector ─────────────────────
# Amplía esta lista para añadir más acciones a cada sector.
SP500_POR_SECTOR = {
    'tecnologia': [
        {'ticker': 'AAPL',  'nombre': 'Apple',            'riesgo': 'bajo'},
        {'ticker': 'MSFT',  'nombre': 'Microsoft',        'riesgo': 'bajo'},
        {'ticker': 'GOOGL', 'nombre': 'Alphabet',         'riesgo': 'medio'},
        {'ticker': 'META',  'nombre': 'Meta Platforms',   'riesgo': 'medio'},
        {'ticker': 'NVDA',  'nombre': 'NVIDIA',           'riesgo': 'alto'},
        {'ticker': 'AMD',   'nombre': 'AMD',              'riesgo': 'alto'},
    ],
    'ia': [
        {'ticker': 'NVDA',  'nombre': 'NVIDIA',              'riesgo': 'alto'},
        {'ticker': 'MSFT',  'nombre': 'Microsoft',           'riesgo': 'bajo'},
        {'ticker': 'PLTR',  'nombre': 'Palantir',            'riesgo': 'alto'},
        {'ticker': 'AMZN',  'nombre': 'Amazon (AWS)',        'riesgo': 'medio'},
        {'ticker': 'GOOGL', 'nombre': 'Alphabet (DeepMind)', 'riesgo': 'medio'},
    ],
    'materias_primas': [
        {'ticker': 'XOM',   'nombre': 'ExxonMobil',       'riesgo': 'bajo'},
        {'ticker': 'CVX',   'nombre': 'Chevron',          'riesgo': 'bajo'},
        {'ticker': 'FCX',   'nombre': 'Freeport-McMoRan', 'riesgo': 'medio'},
        {'ticker': 'NEM',   'nombre': 'Newmont (Oro)',    'riesgo': 'medio'},
        {'ticker': 'CF',    'nombre': 'CF Industries',    'riesgo': 'alto'},
    ],
    'salud': [
        {'ticker': 'JNJ',   'nombre': 'Johnson & Johnson', 'riesgo': 'bajo'},
        {'ticker': 'UNH',   'nombre': 'UnitedHealth',      'riesgo': 'bajo'},
        {'ticker': 'PFE',   'nombre': 'Pfizer',            'riesgo': 'medio'},
        {'ticker': 'MRNA',  'nombre': 'Moderna',           'riesgo': 'alto'},
    ],
    'finanzas': [
        {'ticker': 'JPM',   'nombre': 'JPMorgan Chase',     'riesgo': 'bajo'},
        {'ticker': 'BRK-B', 'nombre': 'Berkshire Hathaway', 'riesgo': 'bajo'},
        {'ticker': 'BAC',   'nombre': 'Bank of America',    'riesgo': 'medio'},
        {'ticker': 'GS',    'nombre': 'Goldman Sachs',      'riesgo': 'medio'},
    ],
}


# ── Caché interno (memoria de la sesión) ─────────────────────
# Estos diccionarios se comparten entre datos.py, alertas.py y
# notificaciones.py importándolos. Son mutables, así que todos
# los módulos ven los mismos datos en tiempo real.
_cache_analisis: dict = {}   # resultado de analizar_accion_yfinance por ticker
_cache_alertas:  dict = {}   # resultado de generar_alerta por ticker


# ── Funciones ─────────────────────────────────────────────────

def obtener_perfil_inversor() -> dict:
    """Hace preguntas al usuario por consola y devuelve su perfil inversor."""
    print('\n' + '=' * 55)
    print('  FORMULARIO DE PERFIL INVERSOR')
    print('=' * 55)

    nombre = input('\n¿Cuál es tu nombre? ').strip() or 'Usuario'

    print('\n¿Cuánto capital tienes disponible para invertir?')
    print('  1. Menos de 1.000 €')
    print('  2. Entre 1.000 € y 10.000 €')
    print('  3. Más de 10.000 €')
    op = input('Elige (1/2/3): ').strip()
    capital = {'1': 'menos_1000', '2': '1000_10000', '3': 'mas_10000'}.get(op, '1000_10000')

    print('\n¿Cuál es tu tolerancia al riesgo?')
    print('  1. Bajo   — Prefiero seguridad')
    print('  2. Medio  — Acepto algo de riesgo')
    print('  3. Alto   — Busco máxima rentabilidad')
    op = input('Elige (1/2/3): ').strip()
    riesgo = {'1': 'bajo', '2': 'medio', '3': 'alto'}.get(op, 'medio')

    print('\n¿Qué sector te interesa?')
    print('  1. Tecnología       (Apple, Microsoft, Google...)')
    print('  2. IA               (NVIDIA, Palantir, Amazon...)')
    print('  3. Materias Primas  (ExxonMobil, Newmont, Chevron...)')
    print('  4. Salud            (Johnson & Johnson, Pfizer...)')
    print('  5. Finanzas         (JPMorgan, Goldman Sachs...)')
    op = input('Elige (1/2/3/4/5): ').strip()
    sector = {'1': 'tecnologia', '2': 'ia', '3': 'materias_primas',
              '4': 'salud', '5': 'finanzas'}.get(op, 'tecnologia')

    print('\n¿Cuántas acciones quieres monitorizar? (2-5)')
    try:
        n = max(2, min(5, int(input('Número: ').strip())))
    except ValueError:
        n = 3

    perfil = {'nombre': nombre, 'capital': capital, 'riesgo': riesgo,
              'sector': sector, 'n_acciones': n}

    # Memoria a largo plazo: guardar en disco para futuras sesiones
    with open('perfil_usuario.json', 'w', encoding='utf-8') as f:
        json.dump(perfil, f, ensure_ascii=False, indent=2)

    print(f'\nPerfil guardado: {perfil}')
    return perfil


def buscar_acciones_por_perfil(sector: str, riesgo: str) -> dict:
    """Devuelve TODAS las acciones del sector/riesgo para analizarlas todas."""
    acciones = SP500_POR_SECTOR.get(sector, SP500_POR_SECTOR['tecnologia'])
    if riesgo == 'bajo':
        filtradas = [a for a in acciones if a['riesgo'] == 'bajo']
    elif riesgo == 'medio':
        filtradas = [a for a in acciones if a['riesgo'] in ('bajo', 'medio')]
    else:
        filtradas = acciones  # alto: todas
    if not filtradas:
        filtradas = acciones
    return {'sector': sector, 'riesgo': riesgo, 'acciones': filtradas}


def analizar_accion_yfinance(ticker: str) -> dict:
    """
    Descarga datos reales de Yahoo Finance y calcula RSI y medias móviles.
    Guarda el resultado en _cache_analisis para que generar_alerta lo use.
    """
    try:
        hist = yf.Ticker(ticker).history(period='1y')

        if hist.empty:
            return {'error': f'Sin datos para {ticker}', 'ticker': ticker}

        precio  = round(hist['Close'].iloc[-1], 2)
        ayer    = round(hist['Close'].iloc[-2], 2)
        var_pct = round((precio - ayer) / ayer * 100, 2)
        ma50    = round(hist['Close'].rolling(50).mean().iloc[-1], 2)
        ma200   = round(hist['Close'].rolling(200).mean().iloc[-1], 2)
        max_52w = round(hist['Close'].max(), 2)
        min_52w = round(hist['Close'].min(), 2)
        volumen = int(hist['Volume'].iloc[-1])

        delta   = hist['Close'].diff()
        ganancia = delta.clip(lower=0).rolling(14).mean()
        perdida  = (-delta.clip(upper=0)).rolling(14).mean()
        rsi     = round(100 - (100 / (1 + ganancia.iloc[-1] / perdida.iloc[-1])), 1)

        resultado = {
            'ticker': ticker, 'precio_actual': precio, 'variacion_pct': var_pct,
            'rsi': rsi, 'ma50': ma50, 'ma200': ma200,
            'max_52w': max_52w, 'min_52w': min_52w, 'volumen': volumen,
            'fecha': str(hist.index[-1].date())
        }
        _cache_analisis[ticker.upper()] = resultado
        return resultado

    except Exception as e:
        return {'error': str(e), 'ticker': ticker}
