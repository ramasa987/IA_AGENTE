# 🤖 FinAlertBot — Agente de Alertas SP500

Agente de IA generativa que analiza acciones del índice **S&P 500** en tiempo real,
genera señales técnicas de COMPRAR / MANTENER / VENDER y envía alertas automáticas
por **Telegram** y **email con PDF**.

---

## ¿Qué hace el agente?

1. **Pregunta** al usuario su perfil inversor (capital, riesgo, sector)
2. **Analiza** todas las acciones del sector con datos reales de Yahoo Finance
3. **Selecciona** las N mejores según calidad técnica de la señal
4. **Espera confirmación** humana antes de enviar nada (Human-in-the-Loop)
5. **Envía** alertas instantáneas por Telegram
6. **Genera** un PDF profesional con gráficas y lo envía por email

---

## Stack Tecnológico

| Componente | Tecnología | Propósito |
|---|---|---|
| LLM | Groq API · `llama-3.3-70b-versatile` | Razonamiento y decisiones |
| Cliente API | `openai` Python SDK | Llamadas al LLM (compatible con Groq) |
| Datos financieros | `yfinance` | Precios, RSI, MA50, MA200, volumen |
| Alertas móvil | Telegram Bot API | Notificaciones instantáneas |
| Email | Gmail SMTP SSL (puerto 465) | Envío del reporte semanal |
| PDF | `fpdf2` | Generación del informe con tabla y gráficas |
| Gráficas | `matplotlib` | Evolución de precio + MA20 + MA50 |
| Memoria LP | JSON (`perfil_usuario.json`) | Persistencia del perfil entre sesiones |

---

## Instalación

```bash
# Clonar o descargar el proyecto
cd 10_proyecto

# Instalar dependencias
pip install openai yfinance fpdf2 requests matplotlib

# Verificar Python >= 3.9
python --version
```

---

## Configuración de credenciales

Edita las variables en `config.py`:

```python
# LLM — Groq (gratuito: https://console.groq.com)
GROQ_KEY = 'tu_clave_groq'
MODELO   = 'llama-3.3-70b-versatile'   # 100k tokens/día gratis

# Telegram (obtener en @BotFather)
TELEGRAM_TOKEN   = 'token_de_tu_bot'
TELEGRAM_CHAT_ID = 'tu_chat_id'

# Gmail (usar App Password, no la contraseña normal)
EMAIL_ORIGEN   = 'tu_email@gmail.com'
EMAIL_PASSWORD = 'xxxx xxxx xxxx xxxx'   # App Password de 16 caracteres
EMAIL_DESTINO  = 'destino@gmail.com'
```

> **Cómo obtener el App Password de Gmail:**
> Google Account → Seguridad → Verificación en 2 pasos → Contraseñas de aplicación

---

## Ejecución

```bash
cd C:\Users\data_\Desktop\AGENTE\10_proyecto
python main.py
```

El agente te guiará paso a paso:

```
======================================================
  BIENVENIDO A FINALERTBOT
  Agente de Alertas SP500 con IA Generativa
======================================================

FORMULARIO DE PERFIL INVERSOR
¿Cuál es tu nombre? Carlos
¿Cuánto capital tienes disponible?
  1. Menos de 1.000 €
  2. Entre 1.000 € y 10.000 €      ← Elige
  3. Más de 10.000 €
...

 Analizando acciones segun tu perfil...

[Iter 1] ACT -> buscar_acciones_por_perfil({'sector': 'tecnologia', 'riesgo': 'medio'})
[Iter 2] ACT -> analizar_accion_yfinance({'ticker': 'AAPL'})
[Iter 3] ACT -> generar_alerta({'ticker': 'AAPL'})
...
[Iter N] ACT -> seleccionar_mejores_alertas({'n': 2})
[Iter N] ACT -> enviar_telegram({'ticker': 'AAPL'})

======================================================
  RESUMEN DE ALERTAS GENERADAS
======================================================
  AAPL     | COMPRAR  | Precio: $281.74 | RSI: 35.3
  GOOGL    | COMPRAR  | Precio: $353.65 | RSI: 44.4

Confirmas el envio por Telegram y Email? (CONFIRMAR / no): CONFIRMAR

   Email: {'estado': 'enviado', 'canal': 'email', 'pdf': 'reporte_sp500_2026-06-30.pdf'}
   Notificaciones enviadas correctamente.
```

---

## Estructura del proyecto

```
10_proyecto/
│
├── main.py                          # Punto de entrada — bucle ReAct + Human-in-the-Loop
├── config.py                        # Credenciales, cliente Groq, SYSTEM_PROMPT
├── datos.py                         # SP500 por sector, caché, Yahoo Finance
├── alertas.py                       # Reglas compra/venta, ranking de señales
├── notificaciones.py                # Telegram, PDF (fpdf2), Email SMTP
├── tools.py                         # JSON schemas del LLM, despachador
│
├── agente_alertas_sp500.py          # Script monolítico original (referencia)
├── FinAlertBot_Ejercicio_Completo.ipynb  # Notebook con diseño y código documentado
├── README.md                        # Este archivo
│
├── perfil_usuario.json              # Perfil guardado (se crea al ejecutar)
├── reporte_sp500_YYYY-MM-DD.pdf     # PDF generado (se crea al ejecutar)
└── grafica_TICKER_YYYY-MM-DD.png    # Gráficas temporales (se crean al ejecutar)
```

### Dependencias entre módulos

Cada flecha significa "este módulo importa de":

```
                    ┌─────────────┐
                    │   main.py   │  ← python main.py
                    │  (entrada)  │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
     ┌──────────┐   ┌──────────┐   ┌─────────────────┐
     │ config.py│   │ tools.py │   │ notificaciones  │
     │ credenc. │   │ schemas  │   │     .py         │
     │ LLM·TG·  │   │ LLM +    │   │ Telegram·PDF·  │
     │ Gmail    │   │ dispatch │   │ Email SMTP      │
     └──────────┘   └────┬─────┘   └───────┬─────────┘
                         │                  │
                    ┌────┴────┐       ┌─────┴──────┐
                    ▼         ▼       ▼             │
              ┌──────────┐  ┌──────────────┐        │
              │ alertas  │  │   datos.py   │◄───────┘
              │   .py    │  │ SP500·cache  │
              │ reglas   │◄─│ Yahoo Finance│
              │ COMPRAR/ │  └──────┬───────┘
              │ VENDER   │         │
              └──────────┘         │
                    │              │
                    └──────┬───────┘
                           ▼
                 ┌──────────────────────┐
                 │  Caché compartido    │  (RAM, dura la sesión)
                 │  _cache_analisis     │
                 │  _cache_alertas      │
                 └──────────────────────┘
                           │
                           ▼
                 ┌──────────────────────┐
                 │ perfil_usuario.json  │  (disco, persiste entre sesiones)
                 └──────────────────────┘
```

**Regla de oro:** ningún módulo importa de `main.py`. El flujo de dependencias es siempre descendente: `main → tools → alertas/datos`, nunca al revés. Esto garantiza que no hay importaciones circulares.

---

## Arquitectura del Agente (Patrón ReAct)

```
Usuario
  │
  ▼
main()
  ├─► Cuestionario perfil ──────────────────► perfil_usuario.json
  │
  └─► Bucle ReAct (MAX 20 iteraciones)
        │
        ├─ THOUGHT ──► LLM (Groq llama-3.3-70b)
        │                    │
        │              tool_calls[]
        │                    │
        ├─ ACT ──────────────┤
        │    ├── buscar_acciones_por_perfil()   → lista de tickers
        │    ├── analizar_accion_yfinance()     → precio, RSI, MA50, MA200
        │    ├── generar_alerta()               → COMPRAR/VENDER/MANTENER
        │    ├── seleccionar_mejores_alertas()  → top N tickers
        │    └── enviar_telegram()              → mensaje Telegram
        │
        └─ OBSERVE ──► resultado inyectado en mensajes[]

  ⏸️  Human-in-the-Loop (pausa obligatoria)
        │
        └─► CONFIRMAR
              ├── enviar_email_pdf() → PDF + Gmail SMTP
              └── FIN
```

---

## Herramientas del agente (Tool Calling)

| Herramienta | Parámetros | Retorna |
|---|---|---|
| `obtener_perfil_inversor` | — | `{nombre, capital, riesgo, sector, n_acciones}` |
| `buscar_acciones_por_perfil` | `sector`, `riesgo` | `{acciones: [{ticker, nombre, riesgo}]}` |
| `analizar_accion_yfinance` | `ticker` | `{precio, rsi, ma50, ma200, variacion_pct, ...}` |
| `generar_alerta` | `ticker` | `{senal, motivo, precio, rsi, reglas_compra, ...}` |
| `seleccionar_mejores_alertas` | `n` | `{seleccionadas, descartadas}` |
| `enviar_telegram` | `ticker` | `{estado: 'enviado', canal: 'telegram'}` |
| `enviar_email_pdf` | `nombre_usuario` | `{estado: 'enviado', pdf: 'ruta.pdf'}` |

---

## Gestión de riesgos

| Riesgo | Solución implementada |
|---|---|
| Bucle infinito del LLM | `MAX_ITER = 20` + log de firmas de llamadas |
| Rate limit Groq (429) | Menú interactivo para cambiar de modelo |
| JSON malformado (400) | Reintento automático x3 con mensaje correctivo |
| Datos inventados | Todas las llamadas van a Yahoo Finance real |
| Envío accidental | Human-in-the-Loop obligatorio antes de notificar |
| Carácter especial en PDF | `limpiar_texto()` filtra a latin-1 |

---

## Modelos disponibles en Groq (plan gratuito)

| Modelo | Tokens/día | Recomendado para |
|---|---|---|
| `llama-3.3-70b-versatile` | 100.000 | Máxima capacidad (default) |
| `llama-3.1-8b-instant` | 500.000 | Si alcanzas el límite diario |
| `gemma2-9b-it` | 500.000 | Alternativa rápida |

---

## Disclaimer

> Este agente es un proyecto educativo de IA Generativa.  
> Las señales generadas son **orientativas** y **no constituyen asesoramiento financiero profesional**.  
> Consulta a un asesor certificado antes de tomar decisiones de inversión.
