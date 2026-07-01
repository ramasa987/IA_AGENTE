# =============================================================
# TOOLS.PY — Herramientas del agente (lo que ve el LLM)
# =============================================================
# Qué hay aquí:
#   - TOOLS: lista con los JSON Schema de cada herramienta
#     (esto es lo que el LLM recibe para saber qué puede llamar)
#   - HERRAMIENTAS_MAP: diccionario nombre → función Python real
#   - ejecutar_herramienta(): despachador que conecta el LLM
#     con las funciones Python
#
# Para añadir una nueva herramienta:
#   1. Escribe la función Python en el módulo correspondiente
#   2. Añade su JSON Schema en TOOLS
#   3. Añádela a HERRAMIENTAS_MAP
# =============================================================

import json

from datos          import obtener_perfil_inversor, buscar_acciones_por_perfil, analizar_accion_yfinance
from alertas        import generar_alerta, seleccionar_mejores_alertas
from notificaciones import enviar_telegram, enviar_email_pdf


# ── JSON Schema de las herramientas (lo que lee el LLM) ──────
# El LLM usa estos schemas para saber:
#   - Qué herramientas existen
#   - Qué parámetros acepta cada una
#   - Cuándo debe llamarlas

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'obtener_perfil_inversor',
            'description': (
                'Recoge el perfil inversor del usuario mediante preguntas: '
                'capital disponible, tolerancia al riesgo y sector de interés. '
                'Llama a esta herramienta SIEMPRE en primer lugar.'
            ),
            'parameters': {'type': 'object', 'properties': {}, 'required': []}
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'buscar_acciones_por_perfil',
            'description': (
                'Filtra la base de datos del SP500 y devuelve acciones que encajan '
                'con el perfil inversor del usuario (sector y riesgo). '
                'Llama después de obtener_perfil_inversor.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'sector': {'type': 'string',
                               'description': 'tecnologia | ia | materias_primas | salud | finanzas'},
                    'riesgo': {'type': 'string',
                               'description': 'bajo | medio | alto'},
                },
                'required': ['sector', 'riesgo']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'analizar_accion_yfinance',
            'description': (
                'Obtiene datos reales de una acción desde Yahoo Finance: '
                'precio actual, RSI, medias móviles MA50 y MA200, volumen y variación diaria. '
                'Es la herramienta más importante del análisis técnico. '
                'Úsala para cada acción seleccionada.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'ticker': {'type': 'string',
                               'description': 'Símbolo bursátil en mayúsculas. Ej: AAPL, NVDA'}
                },
                'required': ['ticker']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'generar_alerta',
            'description': (
                'Aplica las reglas de compra y venta sobre los datos ya analizados '
                'de una acción y devuelve la señal: COMPRAR, VENDER o MANTENER. '
                'Llama después de analizar_accion_yfinance pasando solo el ticker.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'ticker': {'type': 'string',
                               'description': 'Símbolo bursátil. Ej: AAPL, JPM'}
                },
                'required': ['ticker']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'seleccionar_mejores_alertas',
            'description': (
                'Tras generar alertas de todas las acciones, selecciona las N mejores '
                'segun calidad tecnica (prioriza COMPRAR con mas reglas y RSI mas bajo). '
                'Llama SIEMPRE despues de generar_alerta y ANTES de enviar_telegram.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'n': {'type': 'integer',
                          'description': 'Numero exacto de alertas a enviar. Usa el numero que pidio el usuario.'}
                },
                'required': ['n']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'enviar_telegram',
            'description': (
                'Envía la alerta de Telegram para una acción analizada. '
                'Pasa solo el ticker — el sistema construye el mensaje automáticamente.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'ticker': {'type': 'string',
                               'description': 'Símbolo bursátil. Ej: JPM, AAPL'}
                },
                'required': ['ticker']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'enviar_email_pdf',
            'description': (
                'Genera el informe PDF semanal con todas las alertas y graficas '
                'y lo envía por email. Llama al final del ciclo pasando solo el '
                'nombre del usuario.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'nombre_usuario': {'type': 'string',
                                      'description': 'Nombre del usuario para personalizar el PDF'}
                },
                'required': ['nombre_usuario']
            }
        }
    }
]


# ── Mapa nombre → función Python ──────────────────────────────
# Cuando el LLM devuelve un tool_call con nombre 'generar_alerta',
# este diccionario nos dice qué función Python ejecutar.
HERRAMIENTAS_MAP = {
    'obtener_perfil_inversor':     obtener_perfil_inversor,
    'buscar_acciones_por_perfil':  buscar_acciones_por_perfil,
    'analizar_accion_yfinance':    analizar_accion_yfinance,
    'generar_alerta':              generar_alerta,
    'seleccionar_mejores_alertas': seleccionar_mejores_alertas,
    'enviar_telegram':             enviar_telegram,
    'enviar_email_pdf':            enviar_email_pdf,
}


def ejecutar_herramienta(nombre: str, args: dict) -> str:
    """
    Despachador: recibe el nombre y los argumentos del LLM,
    ejecuta la función Python correspondiente y devuelve el
    resultado como JSON string para inyectarlo al historial.
    """
    if nombre not in HERRAMIENTAS_MAP:
        return json.dumps({'error': f"Herramienta '{nombre}' no existe"})
    try:
        return json.dumps(HERRAMIENTAS_MAP[nombre](**args), ensure_ascii=False)
    except Exception as e:
        return json.dumps({'error': str(e), 'herramienta': nombre})
