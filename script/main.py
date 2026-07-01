# =============================================================
# MAIN.PY — Punto de entrada del agente FinAlertBot
# =============================================================
# Qué hay aquí:
#   - agente_alertas_sp500(): el bucle ReAct (THOUGHT → ACT → OBSERVE)
#   - llamar_llm(): gestiona errores 429 (rate limit) y 400 (JSON malo)
#   - main(): orquesta el flujo completo con Human-in-the-Loop
#
# Para ejecutar el agente:
#   python main.py
#
# Dependencias:
#   config.py        → SYSTEM_PROMPT, MODELO, cliente
#   datos.py         → obtener_perfil_inversor(), _cache_alertas
#   tools.py         → TOOLS, ejecutar_herramienta()
#   notificaciones.py → enviar_email_pdf()
# =============================================================

import json
import time

from config          import SYSTEM_PROMPT, MODELO, cliente
from datos           import obtener_perfil_inversor, _cache_alertas
from tools           import TOOLS, ejecutar_herramienta
from notificaciones  import enviar_email_pdf


# =============================================================
# BUCLE REACT
# =============================================================

def agente_alertas_sp500(verbose: bool = True) -> str:
    """
    Bucle ReAct del agente FinAlertBot.
    El perfil ya fue recogido en main() — el agente solo analiza y genera alertas.

    Cada iteración:
      THOUGHT  → el LLM decide qué herramienta usar
      ACT      → ejecutamos la herramienta Python
      OBSERVE  → inyectamos el resultado al historial de mensajes
    """
    MAX_ITER        = 20
    log_herramientas = []   # historial de llamadas para detectar bucles

    # Cargar el perfil guardado en disco por obtener_perfil_inversor()
    try:
        import os
        with open('perfil_usuario.json', 'r', encoding='utf-8') as f:
            perfil = json.load(f)
    except Exception:
        perfil = {'sector': 'tecnologia', 'riesgo': 'medio',
                  'n_acciones': 3, 'capital': '1000_10000', 'nombre': 'Usuario'}

    n_acc      = int(perfil.get('n_acciones', 3))
    perfil_txt = (
        f"sector={perfil['sector']}, riesgo={perfil['riesgo']}, "
        f"capital={perfil['capital']}, n_acciones={n_acc}"
    )

    # Historial de conversación con el LLM
    # El LLM necesita ver siempre todos los mensajes anteriores para tomar
    # decisiones correctas — así funciona el patrón ReAct.
    mensajes = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': (
            f'El perfil del usuario ya ha sido recogido: {perfil_txt}. '
            f'NO llames a obtener_perfil_inversor. '
            f'Llama a buscar_acciones_por_perfil con sector={perfil["sector"]} y riesgo={perfil["riesgo"]}. '
            f'Analiza TODAS las acciones devueltas con analizar_accion_yfinance. '
            f'Llama a generar_alerta para cada una. '
            f'Luego llama a seleccionar_mejores_alertas con n={n_acc} para elegir las {n_acc} mejores. '
            f'Finalmente llama a enviar_telegram SOLO para los tickers seleccionados.'
        )}
    ]

    if verbose:
        print('\n' + '=' * 55)
        print('  FINALERTBOT — Sistema de Alertas SP500')
        print('=' * 55 + '\n')

    # ── Función auxiliar: llamada al LLM con gestión de errores ──
    def llamar_llm(modelo_actual: str):
        """
        Llama al LLM y gestiona los dos errores más comunes de Groq:
          429 → rate limit (demasiados tokens usados hoy)
          400 → JSON malformado (el modelo truncó los argumentos)
        """
        for intento in range(3):
            try:
                return cliente.chat.completions.create(
                    model=modelo_actual,
                    messages=mensajes,
                    tools=TOOLS,
                    tool_choice='auto'
                )
            except Exception as e:
                err = str(e)

                # ERROR 429 — Límite diario de tokens alcanzado
                if '429' in err or 'rate_limit' in err.lower():
                    print('\n' + '=' * 55)
                    print('  LIMITE DE TOKENS DIARIOS ALCANZADO')
                    print('=' * 55)
                    print(f'  Modelo actual : {modelo_actual}')
                    print('  Opciones:')
                    print('  1. llama-3.1-8b-instant  → 500.000 tokens/dia')
                    print('  2. gemma2-9b-it           → 500.000 tokens/dia')
                    print('  3. Esperar 5 minutos y reintentar')
                    print('  4. Salir\n')
                    op = input('  Elige (1/2/3/4): ').strip()
                    if op == '1':
                        return llamar_llm('llama-3.1-8b-instant')
                    elif op == '2':
                        return llamar_llm('gemma2-9b-it')
                    elif op == '3':
                        print('  Esperando 5 minutos...')
                        time.sleep(300)
                        continue
                    else:
                        raise SystemExit('Sesion cancelada por el usuario.')

                # ERROR 400 — El modelo generó JSON malformado en los argumentos
                elif '400' in err and 'tool_use_failed' in err:
                    print(f'\n  [Aviso] Llamada malformada (intento {intento+1}/3). Reintentando...')
                    mensajes.append({
                        'role': 'user',
                        'content': (
                            'Tu ultima llamada a herramienta tenia formato incorrecto. '
                            'Vuelve a intentarlo generando el JSON completo y bien cerrado.'
                        )
                    })
                    time.sleep(2)
                    continue

                else:
                    raise

        raise RuntimeError('No se pudo completar la llamada al LLM tras 3 intentos.')

    # ── Bucle principal ReAct ────────────────────────────────────
    for i in range(MAX_ITER):

        # THOUGHT — El LLM decide qué hacer
        resp = llamar_llm(MODELO)
        msg  = resp.choices[0].message
        mensajes.append(msg)

        if msg.tool_calls:
            for tc in msg.tool_calls:
                nombre = tc.function.name
                args   = json.loads(tc.function.arguments)

                # Control anti-bucle: si el LLM repite la misma llamada, la ignoramos
                firma = f'{nombre}:{json.dumps(args, sort_keys=True)}'
                if firma in log_herramientas:
                    mensajes.append({'role': 'user',
                                     'content': 'Ya ejecutaste esa herramienta. Avanza al siguiente paso.'})
                    continue
                log_herramientas.append(firma)

                if verbose:
                    print(f'[Iter {i+1}] ACT -> {nombre}({args})')

                # ACT — Ejecutar la herramienta Python
                resultado = ejecutar_herramienta(nombre, args)

                if verbose:
                    r       = json.loads(resultado)
                    preview = {k: v for k, v in r.items()
                               if k in ('ticker', 'senal', 'precio', 'rsi',
                                        'estado', 'error', 'nombre', 'sector')}
                    print(f'         OBSERVE -> {preview}\n')

                # OBSERVE — Inyectar el resultado en el historial del LLM
                mensajes.append({
                    'role':        'tool',
                    'tool_call_id': tc.id,
                    'content':     resultado
                })

        else:
            # Sin tool_calls → el LLM ha terminado su misión
            final = msg.content
            if verbose:
                print('\n' + '=' * 55)
                print('  ANALISIS COMPLETADO')
                print('=' * 55)
                print(final)
            return final

    return 'Limite de iteraciones alcanzado. Revisa los logs.'


# =============================================================
# PUNTO DE ENTRADA — Human-in-the-Loop
# =============================================================

def main():
    """
    Orquesta el flujo completo:
      1. Cuestionario de perfil (directo, no delegado al LLM)
      2. Bucle ReAct del agente
      3. Human-in-the-Loop: el usuario confirma antes de enviar
      4. Envío del email con PDF
    """
    print('\n' + '=' * 55)
    print('  BIENVENIDO A FINALERTBOT')
    print('  Agente de Alertas SP500 con IA Generativa')
    print('=' * 55)

    # PASO 1 — Cuestionario
    perfil         = obtener_perfil_inversor()
    nombre_usuario = perfil['nombre']

    # PASO 2 — El agente analiza y genera alertas (bucle ReAct)
    print('\n Analizando acciones segun tu perfil...\n')
    agente_alertas_sp500(verbose=True)

    # PASO 3 — Mostrar resumen
    if not _cache_alertas:
        print('\n Sin alertas generadas. Revisa la conexion a Yahoo Finance.')
        return

    print('\n' + '=' * 55)
    print('  RESUMEN DE ALERTAS GENERADAS')
    print('=' * 55)
    for ticker, alerta in _cache_alertas.items():
        senal  = alerta.get('senal', '-')
        precio = alerta.get('precio', '-')
        rsi    = alerta.get('rsi', '-')
        print(f'  {ticker:<8} | {senal:<8} | Precio: ${precio} | RSI: {rsi}')
    print('=' * 55)

    # PASO 4 — Human-in-the-Loop
    print('\nRevisa el analisis antes de enviar notificaciones.\n')
    confirmacion = input('Confirmas el envio por Telegram y Email? (CONFIRMAR / no): ')

    if confirmacion.strip().upper() == 'CONFIRMAR':
        print('\n Enviando notificaciones...\n')
        # Telegram ya fue enviado por el agente en el bucle ReAct
        # Solo enviamos el email con el PDF aquí
        eml = enviar_email_pdf(nombre_usuario)
        print(f'   Email: {eml}')
        print('\n Notificaciones enviadas correctamente.')
    else:
        print('\n Envio cancelado. No se ha enviado nada.')

    print('\n' + '=' * 55)
    print('  Sesion finalizada. Hasta la proxima.')
    print('=' * 55 + '\n')


if __name__ == '__main__':
    main()
