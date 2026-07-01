# =============================================================
# NOTIFICACIONES.PY — Telegram, PDF y Email
# =============================================================
# Qué hay aquí:
#   - formatear_alerta_telegram(): construye el mensaje de texto
#   - enviar_telegram(): envía la alerta al móvil
#   - generar_grafica_precio(): gráfica matplotlib del precio
#   - generar_pdf(): genera el PDF profesional con tabla y fichas
#   - construir_resumen_desde_cache(): texto plano con todas las alertas
#   - formatear_resumen_email(): cuerpo del email
#   - enviar_email_pdf(): genera el PDF y lo envía por Gmail SMTP
#
# Dependencias:
#   - config.py   → credenciales Telegram y Email
#   - datos.py    → _cache_analisis, _cache_alertas
#   - alertas.py  → generar_alerta(), limpiar_texto()
# =============================================================

import datetime
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fpdf import FPDF

from config import (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
                    EMAIL_ORIGEN, EMAIL_PASSWORD, EMAIL_DESTINO)
from datos import _cache_analisis, _cache_alertas
from alertas import generar_alerta, limpiar_texto


# =============================================================
# TELEGRAM
# =============================================================

def formatear_alerta_telegram(ticker: str, alerta: dict) -> str:
    """
    Construye el mensaje de Telegram directamente desde los datos del caché.
    No depende del LLM para el formato — evita caracteres invisibles y texto confuso.
    """
    senal  = alerta.get('senal', 'MANTENER')
    precio = alerta.get('precio', 0)
    rsi    = alerta.get('rsi', 0)
    motivo = alerta.get('motivo', '')

    datos = _cache_analisis.get(ticker.upper(), {})
    ma50  = datos.get('ma50', '-')
    ma200 = datos.get('ma200', '-')
    var   = datos.get('variacion_pct', 0)
    fecha = datos.get('fecha', str(datetime.date.today()))

    iconos    = {'COMPRAR': '🟢 COMPRAR', 'VENDER': '🔴 VENDER', 'MANTENER': '🟡 MANTENER'}
    senal_txt = iconos.get(senal, senal)

    return (
        f"📊 *ALERTA SP500 — {ticker}*\n"
        f"{'='*30}\n"
        f"Señal:         *{senal_txt}*\n"
        f"Precio:        *${precio}*  ({'+' if var >= 0 else ''}{var}% hoy)\n"
        f"{'─'*30}\n"
        f"RSI (14):      {rsi}\n"
        f"MA50:          {ma50}\n"
        f"MA200:         {ma200}\n"
        f"{'─'*30}\n"
        f"Motivo: {motivo}\n"
        f"{'─'*30}\n"
        f"Fecha: {fecha}\n"
        f"⚠️ _Analisis orientativo. No es asesoramiento financiero._"
    )


def enviar_telegram(ticker: str) -> dict:
    """
    Construye y envía la alerta de Telegram para un ticker.
    Toma los datos directamente del caché — sin depender del texto del LLM.
    """
    ticker = ticker.upper()
    alerta = _cache_alertas.get(ticker)
    if not alerta:
        alerta = generar_alerta(ticker)

    mensaje = formatear_alerta_telegram(ticker, alerta)
    url     = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'

    try:
        r = requests.post(url, json={
            'chat_id':    TELEGRAM_CHAT_ID,
            'text':       mensaje,
            'parse_mode': 'Markdown'
        }, timeout=10)
        if r.status_code == 200:
            return {'estado': 'enviado', 'canal': 'telegram', 'ticker': ticker}
        return {'error': f'HTTP {r.status_code}', 'detalle': r.text}
    except Exception as e:
        return {'error': str(e)}


# =============================================================
# PDF
# =============================================================

def generar_grafica_precio(ticker: str) -> str:
    """
    Gráfica del último trimestre con MA20 y MA50 superpuestas.
    Devuelve la ruta del PNG generado o None si falla.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import yfinance as yf

    datos = yf.Ticker(ticker).history(period='3mo')
    if datos.empty:
        return None

    precios = datos['Close']
    fechas  = datos.index
    ma20    = precios.rolling(20).mean()
    ma50    = precios.rolling(50).mean()

    color_linea = '#1a5276' if precios.iloc[-1] >= precios.iloc[0] else '#c0392b'

    fig, ax = plt.subplots(figsize=(8, 3))
    fig.patch.set_facecolor('#f8f9fa')
    ax.set_facecolor('#f8f9fa')

    ax.plot(fechas, precios, color=color_linea, linewidth=2, label='Precio', zorder=3)
    ax.fill_between(fechas, precios, precios.min() * 0.99, alpha=0.08, color=color_linea)
    ax.plot(fechas, ma20, color='#e67e22', linewidth=1.2, linestyle='--', label='MA20', zorder=2)
    ax.plot(fechas, ma50, color='#8e44ad', linewidth=1.2, linestyle=':', label='MA50', zorder=2)

    ax.annotate(f'${precios.iloc[-1]:.2f}',
                xy=(fechas[-1], precios.iloc[-1]),
                xytext=(-45, 8), textcoords='offset points',
                fontsize=9, fontweight='bold', color=color_linea,
                arrowprops=dict(arrowstyle='->', color=color_linea, lw=1))

    var = ((precios.iloc[-1] - precios.iloc[0]) / precios.iloc[0]) * 100
    signo = '+' if var >= 0 else ''
    ax.set_title(f'{ticker}  |  Ultimo mes: {signo}{var:.1f}%',
                 fontsize=10, fontweight='bold', color='#2c3e50', pad=8)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    ax.tick_params(axis='x', labelsize=7, colors='#7f8c8d')
    ax.tick_params(axis='y', labelsize=7, colors='#7f8c8d')
    ax.yaxis.set_label_position('right')
    ax.yaxis.tick_right()
    ax.grid(axis='y', linestyle='--', alpha=0.3, color='#bdc3c7')
    ax.grid(axis='x', linestyle=':', alpha=0.2, color='#bdc3c7')
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(fontsize=7, loc='upper left', framealpha=0.6)
    plt.tight_layout(pad=0.5)

    ruta = f'grafica_{ticker}_{datetime.date.today()}.png'
    plt.savefig(ruta, dpi=140, bbox_inches='tight', facecolor='#f8f9fa')
    plt.close()
    return ruta


def generar_pdf(resumen: str, nombre_usuario: str) -> str:
    """
    Reporte PDF profesional con cabecera, tabla resumen y fichas por acción con gráficas.
    Lee los datos directamente de _cache_analisis y _cache_alertas.
    """
    AZUL      = (26,  82, 118)
    AZUL_CLAR = (52, 152, 219)
    VERDE     = (39, 174,  96)
    ROJO      = (192,  57,  43)
    AMARILLO  = (211,  84,   0)
    GRIS      = (127, 140, 149)
    FONDO     = (248, 249, 250)
    NEGRO     = (44,   62,  80)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ── Cabecera ──────────────────────────────────────────────
    pdf.set_fill_color(*AZUL)
    pdf.rect(0, 0, 210, 32, 'F')
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(6)
    pdf.cell(0, 10, 'FinAlertBot  |  Reporte SP500',
             align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(0, 8,
             f'Generado: {datetime.date.today()}   |   '
             f'Inversor: {limpiar_texto(nombre_usuario)}   |   '
             f'Acciones analizadas: {len(_cache_alertas)}',
             align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(14)

    # ── Tabla resumen ─────────────────────────────────────────
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 8, 'RESUMEN DE ALERTAS', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    COLS = [22, 32, 28, 20, 28, 28, 0]
    HDRS = ['Ticker', 'Señal', 'Precio', 'RSI', 'MA50', 'MA200', 'Motivo']
    pdf.set_fill_color(*AZUL_CLAR)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 9)
    for w, h in zip(COLS, HDRS):
        if w == 0:
            pdf.cell(0, 7, f'  {h}', fill=True)
        else:
            pdf.cell(w, 7, f'  {h}', fill=True)
    pdf.ln()

    pdf.set_font('Helvetica', '', 9)
    fila_par = False
    for ticker, alerta in _cache_alertas.items():
        datos  = _cache_analisis.get(ticker, {})
        senal  = alerta.get('senal', '-')
        precio = alerta.get('precio', '-')
        rsi    = alerta.get('rsi', '-')
        ma50   = datos.get('ma50', '-')
        ma200  = datos.get('ma200', '-')
        motivo = limpiar_texto(alerta.get('motivo', '-'))[:55]

        col_senal = VERDE if senal == 'COMPRAR' else (ROJO if senal == 'VENDER' else AMARILLO)
        bg = FONDO if fila_par else (255, 255, 255)
        fila_par = not fila_par

        pdf.set_fill_color(*bg)
        pdf.set_text_color(*NEGRO)
        pdf.cell(COLS[0], 7, f'  {ticker}', fill=True)
        pdf.set_text_color(*col_senal)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(COLS[1], 7, f'  {senal}', fill=True)
        pdf.set_text_color(*NEGRO)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(COLS[2], 7, f'  ${precio}', fill=True)
        pdf.cell(COLS[3], 7, f'  {rsi}', fill=True)
        pdf.cell(COLS[4], 7, f'  {ma50}', fill=True)
        pdf.cell(COLS[5], 7, f'  {ma200}', fill=True)
        pdf.set_fill_color(*bg)
        pdf.cell(0, 7, f'  {motivo}', fill=True)
        pdf.ln()

    pdf.ln(10)

    # ── Fichas detalladas por acción ──────────────────────────
    for ticker, alerta in _cache_alertas.items():
        datos  = _cache_analisis.get(ticker, {})
        senal  = alerta.get('senal', 'MANTENER')
        precio = alerta.get('precio', '-')
        rsi    = alerta.get('rsi', '-')
        ma50   = datos.get('ma50', '-')
        ma200  = datos.get('ma200', '-')
        var    = datos.get('variacion_pct', 0)
        max52  = datos.get('max_52w', '-')
        min52  = datos.get('min_52w', '-')
        vol    = datos.get('volumen', '-')
        motivo = limpiar_texto(alerta.get('motivo', '-'))
        fecha  = datos.get('fecha', str(datetime.date.today()))

        if senal == 'COMPRAR':
            col_badge, icono = VERDE, '[COMPRAR]'
        elif senal == 'VENDER':
            col_badge, icono = ROJO, '[VENDER]'
        else:
            col_badge, icono = AMARILLO, '[MANTENER]'

        if pdf.get_y() > 180:
            pdf.add_page()

        # Banda título acción
        pdf.set_fill_color(*col_badge)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(0, 10,
                 f'  {ticker}  {icono}   Precio: ${precio}  ({("+" if var >= 0 else "")}{var}% hoy)',
                 fill=True, new_x='LMARGIN', new_y='NEXT')
        pdf.ln(3)

        # Dos columnas: datos izquierda / gráfica derecha
        x_izq  = pdf.l_margin
        w_izq  = 75
        w_graf = 108
        x_graf = x_izq + w_izq + 4
        y_top  = pdf.get_y()

        def fila_dato(label, valor, bold=False):
            pdf.set_x(x_izq)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_text_color(*GRIS)
            pdf.cell(28, 6, label)
            pdf.set_font('Helvetica', 'B' if bold else '', 9)
            pdf.set_text_color(*NEGRO)
            pdf.cell(w_izq - 28, 6, str(valor), new_x='LMARGIN', new_y='NEXT')

        pdf.set_xy(x_izq, y_top)
        pdf.set_text_color(*NEGRO)
        fila_dato('RSI (14):', rsi,  bold=True)
        fila_dato('MA50:',    ma50)
        fila_dato('MA200:',   ma200)
        fila_dato('Max 52s:', f'${max52}')
        fila_dato('Min 52s:', f'${min52}')
        fila_dato('Volumen:', f'{vol:,}' if isinstance(vol, int) else vol)
        fila_dato('Fecha:',   fecha)

        pdf.ln(2)
        pdf.set_x(x_izq)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_text_color(*GRIS)
        pdf.cell(28, 5, 'Motivo:')
        pdf.set_font('Helvetica', '', 8)
        pdf.set_text_color(*NEGRO)
        pdf.multi_cell(w_izq - 28, 5, motivo)

        y_tras_datos = pdf.get_y()

        try:
            ruta_img = generar_grafica_precio(ticker)
            if ruta_img:
                pdf.image(ruta_img, x=x_graf, y=y_top, w=w_graf)
        except Exception:
            pass

        y_fin = max(y_tras_datos, y_top + 55)
        pdf.set_y(y_fin + 8)
        pdf.set_draw_color(*AZUL_CLAR)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
        pdf.ln(6)

    # ── Disclaimer ────────────────────────────────────────────
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(*GRIS)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5,
        'DISCLAIMER: Este informe es meramente orientativo y no constituye '
        'asesoramiento financiero profesional. Consulta a un asesor certificado '
        'antes de tomar decisiones de inversion. FinAlertBot no se responsabiliza '
        'de perdidas derivadas del uso de esta informacion.')

    nombre_archivo = f'reporte_sp500_{datetime.date.today()}.pdf'
    pdf.output(nombre_archivo)
    return nombre_archivo


# =============================================================
# EMAIL
# =============================================================

def construir_resumen_desde_cache(nombre_usuario: str) -> str:
    """Construye el texto del reporte directamente desde los cachés (sin depender del LLM)."""
    sep    = '-' * 40
    lineas = [f'REPORTE SEMANAL SP500 — {nombre_usuario}',
              f'Fecha: {datetime.date.today()}', '', sep]

    if not _cache_alertas:
        return 'Sin alertas generadas en esta sesion.'

    for ticker, alerta in _cache_alertas.items():
        datos  = _cache_analisis.get(ticker, {})
        var    = datos.get('variacion_pct', 0)
        signo  = '+' if var >= 0 else ''
        lineas += [
            f'ACCION  : {ticker}',
            f'SENAL   : {alerta.get("senal", "-")}',
            f'PRECIO  : ${alerta.get("precio", "-")}  ({signo}{var}% hoy)',
            f'RSI     : {alerta.get("rsi", "-")}',
            f'MA50    : {datos.get("ma50", "-")}',
            f'MA200   : {datos.get("ma200", "-")}',
            f'MOTIVO  : {alerta.get("motivo", "-")}',
            sep,
        ]
    return '\n'.join(lineas)


def formatear_resumen_email(resumen_alertas: str, nombre_usuario: str) -> str:
    """Formatea el resumen como cuerpo de email en texto plano."""
    sep = '-' * 45
    cuerpo = (
        f'Hola {nombre_usuario},\n\n'
        f'Adjunto encontraras el reporte semanal de tus acciones del S&P 500.\n\n'
        f'{sep}\n  RESUMEN DE ALERTAS\n{sep}\n\n'
    )
    for bloque in [b.strip() for b in resumen_alertas.split('\n\n') if b.strip()]:
        cuerpo += bloque + f'\n{sep}\n\n'
    cuerpo += 'DISCLAIMER: Analisis orientativo. No es asesoramiento financiero.\n\nFinAlertBot\n'
    return cuerpo


def enviar_email_pdf(nombre_usuario: str) -> dict:
    """Genera el PDF con datos reales del caché y lo envía por email (SSL 465 o STARTTLS 587)."""
    try:
        resumen  = construir_resumen_desde_cache(nombre_usuario)
        pdf_path = generar_pdf(resumen, nombre_usuario)
        print(f'   [Email] PDF generado: {pdf_path}')

        msg            = MIMEMultipart()
        msg['From']    = EMAIL_ORIGEN
        msg['To']      = EMAIL_DESTINO
        msg['Subject'] = f'FinAlertBot - Reporte Semanal SP500 ({datetime.date.today()})'
        msg.attach(MIMEText(formatear_resumen_email(resumen, nombre_usuario), 'plain', 'utf-8'))

        with open(pdf_path, 'rb') as f:
            adj = MIMEBase('application', 'octet-stream')
            adj.set_payload(f.read())
        encoders.encode_base64(adj)
        adj.add_header('Content-Disposition', 'attachment; filename=reporte_sp500.pdf')
        msg.attach(adj)

        # Intento 1 — SSL puerto 465
        try:
            print('   [Email] Conectando smtp.gmail.com:465 (SSL)...')
            with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as srv:
                srv.login(EMAIL_ORIGEN, EMAIL_PASSWORD)
                srv.send_message(msg)
            print('   [Email] Enviado por SSL:465 OK')
            return {'estado': 'enviado', 'canal': 'email', 'pdf': pdf_path}
        except Exception as e1:
            print(f'   [Email] SSL:465 fallo: {e1}')

        # Intento 2 — STARTTLS puerto 587
        print('   [Email] Intentando smtp.gmail.com:587 (STARTTLS)...')
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo()
            srv.login(EMAIL_ORIGEN, EMAIL_PASSWORD)
            srv.send_message(msg)
        print('   [Email] Enviado por STARTTLS:587 OK')
        return {'estado': 'enviado', 'canal': 'email', 'pdf': pdf_path}

    except Exception as e:
        print(f'   [Email] ERROR FINAL: {e}')
        return {'error': str(e)}
